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
)

from backend.agents.agent_system import (
    analyze_ingredient,
    answer_followup_question,
    extract_ingredient_from_image,
)
from backend.line_store import (
    add_reminder,
    clear_reminders,
    get_latest_report,
    get_reminders,
    list_all_reminders,
    save_report,
)

router = APIRouter(prefix="/line", tags=["line"])

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
LIFF_REPORT_URL = os.environ.get("LIFF_REPORT_URL", "https://liff.line.me/REPLACE_ME")

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


def reminder_quick_reply() -> QuickReply:
    """Buttons for setting/canceling reminders without having to type anything."""
    return QuickReply(
        items=[
            QuickReplyButton(action=MessageAction(label="🌅 早上提醒", text="提醒 早上")),
            QuickReplyButton(action=MessageAction(label="☀️ 中午提醒", text="提醒 中午")),
            QuickReplyButton(action=MessageAction(label="🌙 晚上提醒", text="提醒 晚上")),
            QuickReplyButton(action=MessageAction(label="❌ 取消全部提醒", text="取消提醒")),
        ]
    )


def build_help_message() -> TextSendMessage:
    text = (
        "📖 MediSafe 使用方法\n\n"
        "1️⃣ 傳一張藥品照片或藥袋照片給我，我會幫您分析用藥安全並回傳報告\n"
        "2️⃣ 收到報告後，可以直接打字追問（例如：可以跟感冒藥一起吃嗎？）\n"
        "3️⃣ 點下方按鈕設定每日服藥提醒，或打「取消提醒」全部取消\n\n"
        "隨時輸入「選單」可以再叫出這個說明。"
    )
    return TextSendMessage(text=text, quick_reply=reminder_quick_reply())


def build_traffic_light_flex(report: dict) -> FlexSendMessage:
    """Builds a Flex Message 'traffic light' card summarizing a safety report."""
    emoji, label = SAFETY_LABELS.get(report.get("safety_level", "warning"), ("🟡", "注意"))
    ingredient = report.get("ingredient", "未知藥品")

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": f"{emoji} {label}",
                    "weight": "bold",
                    "size": "xl",
                },
                {
                    "type": "text",
                    "text": ingredient,
                    "weight": "bold",
                    "size": "lg",
                    "wrap": True,
                },
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
                    "action": {
                        "type": "uri",
                        "label": "查看完整報告",
                        "uri": LIFF_REPORT_URL,
                    },
                }
            ],
        },
    }
    return FlexSendMessage(
        alt_text=f"{emoji} {ingredient} 用藥安全報告",
        contents=bubble,
        quick_reply=reminder_quick_reply(),
    )


def process_image_message(user_id: str, message_id: str):
    """Runs the full Vision -> Data Fetcher -> Translator pipeline and pushes the result."""
    line_bot_api = get_line_bot_api()
    try:
        content = line_bot_api.get_message_content(message_id)
        image_bytes = b"".join(chunk for chunk in content.iter_content())
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # Vision Agent: OCR the medicine name from the photo
        ingredient = extract_ingredient_from_image(image_base64, "image/jpeg")

        # Data Fetcher Agents (OpenFDA / PubMed / ClinicalTrials) + Medical Translator Agent
        report = analyze_ingredient(ingredient, lang="zh")

        if report.get("status") == "requires_triage":
            allergies = "、".join(report.get("allergies", []))
            line_bot_api.push_message(
                user_id,
                TextSendMessage(
                    text=f"⚠️ 系統偵測到「{ingredient}」可能與您登記的過敏原（{allergies}）相關，"
                    "請務必先諮詢醫師或藥師，暫不提供自動分析。"
                ),
            )
            return

        if "error" in report:
            line_bot_api.push_message(user_id, TextSendMessage(text=f"分析失敗：{report['error']}"))
            return

        save_report(user_id, report)
        line_bot_api.push_message(user_id, build_traffic_light_flex(report))
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
        answer = answer_followup_question(
            ingredient=latest.get("ingredient", ""),
            report=latest.get("report", ""),
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
                    TextSendMessage(text=f"⏰ 該吃藥囉！這是您登記的 {entry['time']} 服藥提醒。"),
                )
                sent += 1
            except LineBotApiError as e:
                print(f"[LINE Warning] Failed to push reminder to {user_id}: {e}")
                failed += 1

    return {"hour_slot": current_hour_slot, "sent": sent, "failed": failed}
