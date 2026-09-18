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
MARGIN = 22

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msjhbd.ttc",
    r"C:\Windows\Fonts\msjh.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _vertical_gradient(size, top_color, bottom_color) -> Image.Image:
    w, h = size
    top = _hex_to_rgb(top_color)
    bottom = _hex_to_rgb(bottom_color)
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        row = tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3))
        grad.putpixel((0, y), row)
    return grad.resize((w, h))


def _draw_cross_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str):
    """Medical cross inside a white circle badge."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#FFFFFF")
    bar = r * 0.24
    draw.rounded_rectangle([cx - bar, cy - r * 0.62, cx + bar, cy + r * 0.62], radius=bar * 0.6, fill=color)
    draw.rounded_rectangle([cx - r * 0.62, cy - bar, cx + r * 0.62, cy + bar], radius=bar * 0.6, fill=color)


def _draw_bell_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str):
    """Alarm bell inside a white circle badge."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#FFFFFF")
    body_top = cy - r * 0.5
    body_bottom = cy + r * 0.35
    draw.pieslice([cx - r * 0.55, body_top - r * 0.15, cx + r * 0.55, body_top + r * 0.85], 180, 360, fill=color)
    draw.rectangle([cx - r * 0.55, body_top + r * 0.35, cx + r * 0.55, body_bottom], fill=color)
    draw.polygon(
        [(cx - r * 0.6, body_bottom), (cx + r * 0.6, body_bottom), (cx, body_bottom + r * 0.28)], fill=color
    )
    draw.ellipse([cx - r * 0.12, cy - r * 0.85, cx + r * 0.12, cy - r * 0.62], fill=color)
    draw.ellipse([cx - r * 0.15, body_bottom + r * 0.18, cx + r * 0.15, body_bottom + r * 0.48], fill=color)


def _draw_info_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str):
    """Info 'i' inside a white circle badge."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#FFFFFF")
    draw.ellipse([cx - r * 0.14, cy - r * 0.62, cx + r * 0.14, cy - r * 0.34], fill=color)
    draw.rounded_rectangle([cx - r * 0.14, cy - r * 0.18, cx + r * 0.14, cy + r * 0.55], radius=r * 0.14, fill=color)


def build_menu_image() -> bytes:
    """Draws a 3-button rich menu with gradient cards, icon badges, and larger text."""
    img = Image.new("RGB", (WIDTH, HEIGHT), "#F7F8FA")

    buttons = [
        ("#22D07A", "#06A85A", _draw_cross_icon, "過敏資料登記", "登記過敏原"),
        ("#FFC24B", "#F08A1F", _draw_bell_icon, "服藥提醒", "設定/取消提醒"),
        ("#5FA8F5", "#2E6FD9", _draw_info_icon, "使用說明", "查看完整說明"),
    ]

    title_font = _load_font(90)
    sub_font = _load_font(52)

    for i, (top_color, bottom_color, icon_fn, title, subtitle) in enumerate(buttons):
        x0 = i * COLUMN_WIDTH + MARGIN
        x1 = (i + 1) * COLUMN_WIDTH - MARGIN
        y0, y1 = MARGIN, HEIGHT - MARGIN

        card = _vertical_gradient((x1 - x0, y1 - y0), top_color, bottom_color)
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, card.size[0], card.size[1]], radius=40, fill=255)
        img.paste(card, (x0, y0), mask)

        draw = ImageDraw.Draw(img)
        badge_color = bottom_color
        icon_cx = x0 + (x1 - x0) // 2
        icon_cy = y0 + int((y1 - y0) * 0.32)
        icon_r = 70
        icon_fn(draw, icon_cx, icon_cy, icon_r, badge_color)

        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(
            (x0 + (x1 - x0 - title_w) / 2, icon_cy + icon_r + 30),
            title,
            font=title_font,
            fill="#FFFFFF",
        )

        sub_bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text(
            (x0 + (x1 - x0 - sub_w) / 2, icon_cy + icon_r + 30 + (title_bbox[3] - title_bbox[1]) + 22),
            subtitle,
            font=sub_font,
            fill="#FFFFFF",
        )

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
