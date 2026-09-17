"""LINE Messaging API integration for MediSafe.

Wires the existing agent pipeline (backend.agents.agent_system) up to a LINE
Official Account:
- User sends a photo of a medicine  -> Vision Agent OCR -> Data Fetcher Agents
  (OpenFDA / PubMed / ClinicalTrials) -> Medical Translator Agent -> a Flex
  Message "traffic light" card pushed back with a link into the LIFF report page.
- User sends a text message -> treated as a follow-up question answered by the
  AI Pharmacist logic, using the last analyzed report as context.
- POST /line/send-reminders is meant to be hit by a Cloud Scheduler job and
  pushes a reminder text to every user who has registered a dose time
  (send a message like "提醒 08:00" to register one).
"""
import base64
import os
import re

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    FlexSendMessage,
    ImageMessage,
    MessageEvent,
    TextMessage,
    TextSendMessage,
)

from backend.agents.agent_system import (
    analyze_ingredient,
    answer_followup_question,
    extract_ingredient_from_image,
)
from backend.line_store import add_reminder, get_latest_report, list_all_reminders, save_report

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
    return FlexSendMessage(alt_text=f"{emoji} {ingredient} 用藥安全報告", contents=bubble)


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

    reminder_match = REMINDER_PATTERN.search(text)
    if reminder_match:
        time_str = f"{int(reminder_match.group(1)):02d}:{reminder_match.group(2)}"
        add_reminder(user_id, time_str)
        line_bot_api.reply_message(
            reply_token, TextSendMessage(text=f"✅ 已為您登記每日 {time_str} 的服藥提醒。")
        )
        return

    latest = get_latest_report(user_id)
    if not latest:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="請先傳一張藥品照片給我分析，之後就可以針對報告內容繼續追問囉！"),
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
    """Meant to be triggered by Cloud Scheduler. Pushes a reminder to every registered user."""
    line_bot_api = get_line_bot_api()
    reminders = list_all_reminders()
    sent, failed = 0, 0

    for user_id, entries in reminders.items():
        for entry in entries:
            try:
                line_bot_api.push_message(
                    user_id,
                    TextSendMessage(text=f"⏰ 該吃藥囉！這是您登記的 {entry['time']} 服藥提醒。"),
                )
                sent += 1
            except LineBotApiError as e:
                print(f"[LINE Warning] Failed to push reminder to {user_id}: {e}")
                failed += 1

    return {"sent": sent, "failed": failed}
