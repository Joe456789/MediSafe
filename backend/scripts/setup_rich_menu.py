"""One-off script to create and set MediSafe's default LINE Rich Menu.

This is account-level configuration, not part of the request/response cycle,
so it isn't wired into the FastAPI app: run it once (and again whenever the
menu should change) with:

    python -m backend.scripts.setup_rich_menu

Requires Pillow (pip install pillow) and these env vars:
    LINE_CHANNEL_ACCESS_TOKEN
    LIFF_REPORT_URL
    LIFF_PROFILE_URL
"""
import io
import os

from dotenv import load_dotenv
from linebot import LineBotApi
from linebot.models import MessageAction, RichMenu, RichMenuArea, RichMenuBounds, RichMenuSize, URIAction
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

WIDTH, HEIGHT = 2500, 843
COLUMN_WIDTH = WIDTH // 3

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msjh.ttc",
    r"C:\Windows\Fonts\msjhbd.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def build_menu_image() -> bytes:
    """Draws a simple 3-button green/white rich menu image in memory."""
    img = Image.new("RGB", (WIDTH, HEIGHT), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    title_font = _load_font(56)
    sub_font = _load_font(34)

    buttons = [
        ("#06C755", "過敏資料登記", "填寫過敏原/家屬通知"),
        ("#F5A623", "服藥提醒", "設定/取消提醒"),
        ("#4A90D9", "使用說明", "查看完整功能選單"),
    ]

    for i, (color, title, subtitle) in enumerate(buttons):
        x0 = i * COLUMN_WIDTH
        x1 = x0 + COLUMN_WIDTH
        draw.rectangle([x0, 0, x1, HEIGHT], fill=color)
        # Thin white separators between columns
        if i > 0:
            draw.rectangle([x0 - 4, 0, x0 + 4, HEIGHT], fill="#FFFFFF")

        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text((x0 + (COLUMN_WIDTH - title_w) / 2, HEIGHT / 2 - 70), title, font=title_font, fill="#FFFFFF")

        sub_bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text((x0 + (COLUMN_WIDTH - sub_w) / 2, HEIGHT / 2 + 10), subtitle, font=sub_font, fill="#FFFFFF")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main():
    access_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    liff_profile_url = os.environ["LIFF_PROFILE_URL"]
    line_bot_api = LineBotApi(access_token)

    rich_menu = RichMenu(
        size=RichMenuSize(width=WIDTH, height=HEIGHT),
        selected=True,
        name="MediSafe main menu",
        chat_bar_text="開啟 MediSafe 選單",
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(x=0, y=0, width=COLUMN_WIDTH, height=HEIGHT),
                action=URIAction(label="過敏資料登記", uri=liff_profile_url),
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=COLUMN_WIDTH, y=0, width=COLUMN_WIDTH, height=HEIGHT),
                action=MessageAction(label="服藥提醒", text="提醒設定"),
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=COLUMN_WIDTH * 2, y=0, width=WIDTH - COLUMN_WIDTH * 2, height=HEIGHT),
                action=MessageAction(label="使用說明", text="選單"),
            ),
        ],
    )

    rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu)
    print(f"Created rich menu: {rich_menu_id}")

    image_bytes = build_menu_image()
    line_bot_api.set_rich_menu_image(rich_menu_id, "image/png", image_bytes)
    print("Uploaded rich menu image.")

    line_bot_api.set_default_rich_menu(rich_menu_id)
    print("Set as default rich menu for all users.")


if __name__ == "__main__":
    main()
