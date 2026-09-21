"""LINE Messaging API integration for MediSafe.

Wires the existing agent pipeline (backend.agents.agent_system) up to a LINE
Official Account:
- User sends a photo of a medicine  -> Vision Agent OCR -> Data Fetcher Agents
  (OpenFDA / PubMed / ClinicalTrials) -> Medical Translator Agent -> a Flex
  Message "traffic light" card pushed back with a link into the LIFF report page.
- User sends a text message -> treated as a follow-up question answered by the
  AI Pharmacist logic, using the last analyzed report as context.
- POST /line/send-reminders is meant to be hit by a Cloud Scheduler job once
  an hour. Each user can register their own dose time(s) by texting e.g.
  "提醒 08:00" or "提醒 早上"/"提醒 中午"/"提醒 晚上"; times are rounded to the
  nearest hour, and only users whose reminder matches the current hour
  (Asia/Taipei) get pushed on a given run.
"""
import base64
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    FlexSendMessage,
    ImageMessage,
    MessageAction,
    MessageEvent,
    QuickReply,
    QuickReplyButton,
    TextMessage,
    TextSendMessage,
    URIAction,
)
from pydantic import BaseModel

from backend.agents.agent_system import (
    analyze_ingredient,
    answer_followup_question,
    extract_ingredients_from_image,
    summarize_drug_interactions,
)
from backend.line_store import (
    add_reminder,
    clear_reminders,
    create_family_link_code,
    get_dose_history,
    get_family_members,
    get_latest_report,
    get_profile,
    get_reminders,
    list_all_reminders,
    log_dose_taken,
    redeem_family_link_code,
    save_profile,
    save_report_batch,
)

router = APIRouter(prefix="/line", tags=["line"])

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
LIFF_REPORT_URL = os.environ.get("LIFF_REPORT_URL", "https://liff.line.me/REPLACE_ME")
LIFF_PROFILE_URL = os.environ.get("LIFF_PROFILE_URL", "https://liff.line.me/REPLACE_ME")

_line_bot_api = None
_parser = None


def get_line_bot_api() -> LineBotApi:
    global _line_bot_api
    if _line_bot_api is None:
        if not LINE_CHANNEL_ACCESS_TOKEN:
            raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN environment variable not set.")
        _line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    return _line_bot_api


def get_parser() -> WebhookParser:
    global _parser
    if _parser is None:
        if not LINE_CHANNEL_SECRET:
            raise RuntimeError("LINE_CHANNEL_SECRET environment variable not set.")
        _parser = WebhookParser(LINE_CHANNEL_SECRET)
    return _parser


SAFETY_LABELS = {
    "safe": ("🟢", "安全"),
    "warning": ("🟡", "注意"),
    "danger": ("🔴", "危險"),
}

REMINDER_PATTERN = re.compile(r"(?:提醒|remind)\D*(\d{1,2}):?(\d{2})", re.IGNORECASE)
REMINDER_KEYWORD_TIMES = {
    "早上": "08:00", "早": "08:00", "morning": "08:00",
    "中午": "12:00", "noon": "12:00",
    "晚上": "18:00", "晚": "18:00", "evening": "18:00", "night": "18:00",
    "睡前": "22:00", "bedtime": "22:00",
}
REMINDER_KEYWORD_PATTERN = re.compile(
    r"(?:提醒|remind)\D*(" + "|".join(REMINDER_KEYWORD_TIMES.keys()) + r")", re.IGNORECASE
)
TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def _round_to_hour(time_str: str) -> str:
    """Rounds an 'HH:MM' string to the nearest hour, e.g. '08:37' -> '09:00'."""
    hour, minute = map(int, time_str.split(":"))
    if minute >= 30:
        hour = (hour + 1) % 24
    return f"{hour:02d}:00"


HELP_TRIGGERS = {"選單", "menu", "使用方法", "說明", "help", "提醒設定"}
FAMILY_BIND_PATTERN = re.compile(r"(?:綁定|bind)\D*(\d{6})", re.IGNORECASE)
FAMILY_CODE_TRIGGERS = {"家屬通知", "家屬綁定", "產生代碼", "通知代碼"}
DOSE_LOG_PATTERN = re.compile(r"^(?:打卡|已服藥|服藥打卡|已吃藥)\s*(\d{2}:00)?$")
DOSE_HISTORY_TRIGGERS = {"打卡紀錄", "服藥紀錄", "漏吃", "漏吃紀錄", "查詢紀錄"}


def reminder_quick_reply() -> QuickReply:
    """Buttons for setting/canceling reminders, plus a shortcut to the allergy
    profile form, without the user having to type anything."""
    return QuickReply(
        items=[
            QuickReplyButton(action=MessageAction(label="🌅 早上提醒", text="提醒 早上")),
            QuickReplyButton(action=MessageAction(label="☀️ 中午提醒", text="提醒 中午")),
            QuickReplyButton(action=MessageAction(label="🌙 晚上提醒", text="提醒 晚上")),
            QuickReplyButton(action=MessageAction(label="😴 睡前提醒", text="提醒 睡前")),
            QuickReplyButton(action=MessageAction(label="✅ 已服藥打卡", text="打卡")),
            QuickReplyButton(action=MessageAction(label="📋 服藥紀錄", text="服藥紀錄")),
            QuickReplyButton(action=MessageAction(label="❌ 取消全部提醒", text="取消提醒")),
            QuickReplyButton(action=URIAction(label="📋 過敏資料登記", uri=LIFF_PROFILE_URL)),
            QuickReplyButton(action=MessageAction(label="👨‍👩‍👧 家屬通知代碼", text="家屬通知")),
        ]
    )


def build_dose_history_text(user_id: str, days: int = 7) -> str:
    history = get_dose_history(user_id, days)
    if not any(d["expected"] for d in history):
        return "您還沒有設定服藥提醒，設定後才能記錄每次是否有吃藥。請先點「早上／中午／晚上／睡前提醒」。"
    lines = [f"📋 最近 {days} 天服藥紀錄"]
    missed_total = 0
    for d in history:
        month_day = d["date"][5:].replace("-", "/")
        parts = [f"✅{s}" for s in d["taken"]] + [f"❌{s}" for s in d["missed"]] + [f"⏳{s}" for s in d["upcoming"]]
        missed_total += len(d["missed"])
        lines.append(f"{month_day}  " + ("　".join(parts) if parts else "—"))
    lines.append(f"\n漏吃共 {missed_total} 次" + ("，要記得按時吃藥喔！" if missed_total else "，全部都有吃，太棒了！"))
    lines.append("（✅已吃　❌漏吃　⏳時間未到）")
    return "\n".join(lines)


def build_help_message() -> TextSendMessage:
    text = (
        "📖 MediSafe 使用方法\n\n"
        "1️⃣ 傳一張藥品照片或藥袋照片給我，我會幫您分析用藥安全並回傳報告（藥單上有多種藥也會一起分析）\n"
        "2️⃣ 收到報告後，可以直接打字追問（例如：可以跟感冒藥一起吃嗎？）\n"
        "3️⃣ 點「過敏資料登記」填寫過敏原，之後分析會自動比對並示警\n"
        "4️⃣ 點按鈕設定每日服藥提醒，或打「取消提醒」全部取消\n"
        "5️⃣ 點「家屬通知代碼」產生代碼，請家屬在對話框輸入「綁定 該代碼」，之後過敏示警會同步通知家屬\n"
        "6️⃣ 吃完藥點「已服藥打卡」按鈕（或收到提醒時點「我吃了」），點「服藥紀錄」可查哪一次沒吃\n\n"
        "隨時輸入「選單」可以再叫出這個說明。"
    )
    return TextSendMessage(text=text, quick_reply=reminder_quick_reply())


def _display_name(report: dict) -> str:
    ingredient = report.get("ingredient", "未知藥品")
    ingredient_zh = report.get("ingredient_zh") or ingredient
    if ingredient_zh == ingredient or ingredient.lower() in ingredient_zh.lower():
        return ingredient_zh
    return f"{ingredient_zh}（{ingredient}）"


def _report_bubble(report: dict) -> dict:
    """One 'traffic light' bubble for a single medicine's safety report."""
    emoji, label = SAFETY_LABELS.get(report.get("safety_level", "warning"), ("🟡", "注意"))
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": f"{emoji} {label}", "weight": "bold", "size": "xl"},
                {"type": "text", "text": _display_name(report), "weight": "bold", "size": "lg", "wrap": True},
                {
                    "type": "text",
                    "text": "已完成用藥安全分析，點擊下方按鈕查看完整白話報告。",
                    "size": "sm",
                    "color": "#666666",
                    "wrap": True,
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#06C755",
                    "action": {"type": "uri", "label": "查看完整報告", "uri": LIFF_REPORT_URL},
                }
            ],
        },
    }


def _triage_bubble(ingredient: str, allergies: str) -> dict:
    """Red bubble for a medicine that was blocked by the allergy triage gate."""
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "🔴 過敏警示", "weight": "bold", "size": "xl", "color": "#C62F28"},
                {"type": "text", "text": ingredient, "weight": "bold", "size": "lg", "wrap": True},
                {
                    "type": "text",
                    "text": f"與您登記的過敏原（{allergies}）相關，已攔下自動分析，請先諮詢醫師或藥師。",
                    "size": "sm",
                    "color": "#666666",
                    "wrap": True,
                },
            ],
        },
    }


def build_result_flex(bubbles: list, alt_text: str) -> FlexSendMessage:
    """A single bubble for one medicine, or a carousel (LINE allows up to 12) for several."""
    contents = bubbles[0] if len(bubbles) == 1 else {"type": "carousel", "contents": bubbles[:12]}
    return FlexSendMessage(alt_text=alt_text[:390], contents=contents, quick_reply=reminder_quick_reply())


def build_traffic_light_flex(report: dict) -> FlexSendMessage:
    """Flex Message 'traffic light' card for a single safety report."""
    emoji, _ = SAFETY_LABELS.get(report.get("safety_level", "warning"), ("🟡", "注意"))
    return build_result_flex([_report_bubble(report)], f"{emoji} {_display_name(report)} 用藥安全報告")


def _notify_family_of_alert(line_bot_api: LineBotApi, patient_user_id: str, ingredient: str, allergies: str):
    """Pushes the same allergy-conflict warning to every family member linked
    to this patient via a redeemed linking code."""
    family_ids = get_family_members(patient_user_id)
    if not family_ids:
        return
    try:
        patient_name = line_bot_api.get_profile(patient_user_id).display_name
    except LineBotApiError:
        patient_name = "您登記關注的使用者"
    for family_id in family_ids:
        try:
            line_bot_api.push_message(
                family_id,
                TextSendMessage(
                    text=f"⚠️ 用藥安全通知\n{patient_name} 剛剛掃描的藥品「{ingredient}」"
                    f"可能與登記的過敏原（{allergies}）相關，系統已擋下自動分析，請主動關心並協助確認用藥安全。"
                ),
            )
        except LineBotApiError as e:
            print(f"[LINE Warning] Failed to notify family member {family_id}: {e}")


def _analyze_one(ingredient: str, user_allergies) -> dict:
    try:
        return analyze_ingredient(ingredient, lang="zh", user_allergies=user_allergies)
    except Exception as e:
        print(f"[MediSafe Warning] Analysis failed for {ingredient}: {e}")
        return {"error": str(e)}


def process_image_message(user_id: str, message_id: str):
    """Vision -> Data Fetcher -> Translator pipeline for every medicine in the photo
    (a prescription can list several), pushed back as one Flex message."""
    line_bot_api = get_line_bot_api()
    try:
        content = line_bot_api.get_message_content(message_id)
        image_bytes = b"".join(chunk for chunk in content.iter_content())
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # Vision Agent: every medicine name visible in the photo
        ingredients = extract_ingredients_from_image(image_base64, "image/jpeg")

        # HITL Triage Gate: check against this user's own registered allergy profile
        # (falls back to the shared demo MCP profile if they haven't registered one)
        profile = get_profile(user_id)
        user_allergies = profile.get("allergies") if profile else None

        # Data Fetcher Agents + Medical Translator Agent, one medicine per worker; the
        # cross-medicine interaction note is generated in parallel.
        with ThreadPoolExecutor(max_workers=3) as pool:
            interaction_future = pool.submit(summarize_drug_interactions, ingredients) if len(ingredients) > 1 else None
            results = list(pool.map(lambda name: _analyze_one(name, user_allergies), ingredients))
        interactions = interaction_future.result() if interaction_future else ""

        reports, conflicts, failed = [], [], []
        for name, result in zip(ingredients, results):
            if result.get("status") == "requires_triage":
                conflicts.append((name, "、".join(result.get("allergies", []))))
            elif "error" in result:
                failed.append(name)
            else:
                reports.append(result)

        if conflicts:
            names = "、".join(n for n, _ in conflicts)
            allergies = "、".join(dict.fromkeys(a for _, al in conflicts for a in al.split("、") if a))
            line_bot_api.push_message(
                user_id,
                TextSendMessage(
                    text=f"⚠️ 系統偵測到「{names}」可能與您登記的過敏原（{allergies}）相關，"
                    "請務必先諮詢醫師或藥師，暫不提供自動分析。"
                ),
            )
            for name, allergy_text in conflicts:
                _notify_family_of_alert(line_bot_api, user_id, name, allergy_text)

        if reports:
            save_report_batch(user_id, reports, interactions)
            bubbles = [_triage_bubble(n, al) for n, al in conflicts] + [_report_bubble(r) for r in reports]
            alt = "用藥安全報告：" + "、".join(_display_name(r) for r in reports)
            line_bot_api.push_message(user_id, build_result_flex(bubbles, alt))
            if len(reports) > 1 and interactions:
                line_bot_api.push_message(user_id, TextSendMessage(text="🔎 多種藥物同時服用的注意事項\n" + interactions))

        if failed:
            line_bot_api.push_message(
                user_id, TextSendMessage(text="以下藥品分析失敗，請稍後再傳一次照片試試：" + "、".join(failed))
            )
    except LineBotApiError as e:
        print(f"[LINE Warning] Failed to push analysis result: {e}")
    except Exception as e:
        print(f"[MediSafe Warning] Image pipeline failed: {e}")
        try:
            line_bot_api.push_message(user_id, TextSendMessage(text=f"分析發生錯誤：{str(e)}"))
        except LineBotApiError:
            pass


def process_text_message(user_id: str, reply_token: str, text: str):
    line_bot_api = get_line_bot_api()
    stripped = text.strip()

    if stripped.lower() in HELP_TRIGGERS:
        line_bot_api.reply_message(reply_token, build_help_message())
        return

    dose_match = DOSE_LOG_PATTERN.match(stripped)
    if dose_match:
        _, slot = log_dose_taken(user_id, dose_match.group(1))
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=f"✅ 已記錄今天 {slot} 的服藥打卡，做得很好！", quick_reply=reminder_quick_reply()),
        )
        return

    if stripped in DOSE_HISTORY_TRIGGERS:
        line_bot_api.reply_message(
            reply_token, TextSendMessage(text=build_dose_history_text(user_id), quick_reply=reminder_quick_reply())
        )
        return

    if stripped in FAMILY_CODE_TRIGGERS:
        code = create_family_link_code(user_id)
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(
                text=f"👨‍👩‍👧 您的家屬通知代碼是：{code}\n"
                "請家屬將本帳號加為好友後，在對話框輸入「綁定 " + code + "」\n"
                "（代碼 10 分鐘內有效，之後偵測到過敏原衝突時會同步通知已綁定的家屬）"
            ),
        )
        return

    bind_match = FAMILY_BIND_PATTERN.search(stripped)
    if bind_match:
        code = bind_match.group(1)
        patient_user_id = redeem_family_link_code(code, user_id)
        if patient_user_id:
            line_bot_api.reply_message(
                reply_token, TextSendMessage(text="✅ 綁定成功！之後這位使用者的過敏原衝突警示會同步通知您。")
            )
        else:
            line_bot_api.reply_message(reply_token, TextSendMessage(text="❌ 代碼無效或已過期，請對方重新產生一次。"))
        return

    if "取消" in stripped and ("提醒" in stripped or "remind" in stripped.lower()):
        clear_reminders(user_id)
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="✅ 已取消您所有的服藥提醒。", quick_reply=reminder_quick_reply()),
        )
        return

    keyword_match = REMINDER_KEYWORD_PATTERN.search(stripped)
    reminder_match = REMINDER_PATTERN.search(stripped)
    if keyword_match or reminder_match:
        if keyword_match:
            raw_time = REMINDER_KEYWORD_TIMES[keyword_match.group(1).lower()]
        else:
            raw_time = f"{int(reminder_match.group(1)):02d}:{reminder_match.group(2)}"
        time_str = _round_to_hour(raw_time)
        add_reminder(user_id, time_str)
        registered = ", ".join(sorted(e["time"] for e in get_reminders(user_id)))
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(
                text=f"✅ 已為您登記每日 {time_str} 的服藥提醒（會自動取整點）。\n目前已登記：{registered}",
                quick_reply=reminder_quick_reply(),
            ),
        )
        return

    latest = get_latest_report(user_id)
    if not latest:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(
                text="請先傳一張藥品照片給我分析，之後就可以針對報告內容繼續追問囉！輸入「選單」可以看使用說明。",
                quick_reply=reminder_quick_reply(),
            ),
        )
        return

    try:
        batch = latest.get("batch") or [latest]
        names = [r.get("ingredient_zh") or r.get("ingredient", "") for r in batch]
        report_text = "\n\n".join(f"【{n}】\n{r.get('report', '')}" for n, r in zip(names, batch))
        if latest.get("interactions"):
            report_text += "\n\n【藥物之間的注意事項】\n" + latest["interactions"]
        answer = answer_followup_question(
            ingredient="、".join(names),
            report=report_text,
            question=text,
            lang="zh",
        )
        line_bot_api.reply_message(reply_token, TextSendMessage(text=answer))
    except Exception as e:
        line_bot_api.reply_message(reply_token, TextSendMessage(text=f"回答時發生錯誤：{str(e)}"))


@router.post("/webhook")
async def line_webhook(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        events = get_parser().parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    line_bot_api = get_line_bot_api()

    for event in events:
        if not isinstance(event, MessageEvent):
            continue

        user_id = event.source.user_id

        if isinstance(event.message, ImageMessage):
            # Reply immediately so the user isn't left waiting on a slow OCR+lookup pipeline
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="📷 收到照片了，正在為您分析用藥安全，請稍候...")
            )
            background_tasks.add_task(process_image_message, user_id, event.message.id)

        elif isinstance(event.message, TextMessage):
            background_tasks.add_task(process_text_message, user_id, event.reply_token, event.message.text)

    return "OK"


@router.get("/report/{user_id}")
async def get_report(user_id: str):
    """Used by the LIFF report page to fetch a user's most recent analysis."""
    report = get_latest_report(user_id)
    if not report:
        raise HTTPException(status_code=404, detail="No report found for this user yet.")
    return report


class ProfileUpdate(BaseModel):
    user_id: str
    allergies: list[str] = []
    medications: list[str] = []


@router.get("/profile/{user_id}")
async def get_profile_endpoint(user_id: str):
    """Used by the LIFF profile page to pre-fill the form with what's already saved."""
    profile = get_profile(user_id) or {"allergies": [], "medications": []}
    return profile


@router.post("/profile")
async def update_profile(payload: ProfileUpdate):
    """Used by the LIFF profile page to save a user's allergy/medication list."""
    profile = save_profile(payload.user_id, payload.allergies, payload.medications)
    return profile


class FamilyCodeRequest(BaseModel):
    user_id: str


@router.post("/family/generate-code")
async def generate_family_code(payload: FamilyCodeRequest):
    """Used by the LIFF profile page's 'generate family code' button."""
    code = create_family_link_code(payload.user_id)
    return {"code": code, "expires_in_seconds": 600}


class DoseLogRequest(BaseModel):
    user_id: str
    slot: str | None = None


@router.post("/dose-log")
async def check_in_dose(payload: DoseLogRequest):
    """Used by the LIFF page's '今天已服藥' button. Idempotent per Asia/Taipei day."""
    date, slot = log_dose_taken(payload.user_id, payload.slot)
    return {"date": date, "slot": slot}


@router.get("/dose-log/{user_id}")
async def get_dose_log_endpoint(user_id: str, days: int = 7):
    """Used by the LIFF page to render the last N days' check-in history."""
    return {"days": get_dose_history(user_id, min(max(days, 1), 30))}


@router.post("/send-reminders")
async def send_reminders():
    """Meant to be triggered by Cloud Scheduler once an hour. Only pushes to users
    whose registered reminder time matches the current hour in Asia/Taipei, so
    each user effectively gets their own schedule (e.g. morning/noon/evening)."""
    line_bot_api = get_line_bot_api()
    current_hour_slot = datetime.now(TAIPEI_TZ).strftime("%H:00")
    reminders = list_all_reminders()
    sent, failed = 0, 0

    for user_id, entries in reminders.items():
        for entry in entries:
            if entry.get("time") != current_hour_slot:
                continue
            try:
                line_bot_api.push_message(
                    user_id,
                    TextSendMessage(
                        text=f"⏰ 該吃藥囉！這是您登記的 {entry['time']} 服藥提醒。吃完請點下方按鈕打卡。",
                        quick_reply=QuickReply(
                            items=[
                                QuickReplyButton(
                                    action=MessageAction(label="✅ 我吃了", text=f"打卡 {entry['time']}")
                                ),
                                QuickReplyButton(action=MessageAction(label="📋 服藥紀錄", text="服藥紀錄")),
                            ]
                        ),
                    ),
                )
                sent += 1
            except LineBotApiError as e:
                print(f"[LINE Warning] Failed to push reminder to {user_id}: {e}")
                failed += 1

    return {"hour_slot": current_hour_slot, "sent": sent, "failed": failed}
