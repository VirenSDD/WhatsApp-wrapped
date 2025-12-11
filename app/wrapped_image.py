from __future__ import annotations

from io import BytesIO
from textwrap import wrap
from typing import Iterable, Literal, Tuple, TypedDict, cast

from PIL import Image, ImageDraw, ImageFont


class WrappedStat(TypedDict):
    label: str
    value: str
    emoji: str


class WrappedPayload(TypedDict):
    chat_name: str
    year: int
    user_initials: str
    stats: list[WrappedStat]


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Attempt to load a high-quality font, falling back to Pillow's default."""
    candidates = [
        "/usr/share/fonts/truetype/inter/Inter-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
        "/usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/montserrat/Montserrat-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return cast(ImageFont.ImageFont, ImageFont.truetype(path, size=size))
        except Exception:  # noqa: BLE001
            continue
    return cast(ImageFont.ImageFont, ImageFont.load_default())


def _create_gradient(size: Tuple[int, int]) -> Image.Image:
    width, height = size
    gradient = Image.new("RGBA", size, (0, 0, 0, 255))
    draw = ImageDraw.Draw(gradient)
    colors = [
        (95, 33, 245),
        (253, 75, 146),
        (255, 168, 64),
    ]
    segments = len(colors) - 1
    for y in range(height):
        pos = y / max(height - 1, 1)
        idx = min(int(pos * segments), segments - 1)
        start = colors[idx]
        end = colors[idx + 1]
        local_t = (pos * segments) - idx
        r = int(start[0] + (end[0] - start[0]) * local_t)
        g = int(start[1] + (end[1] - start[1]) * local_t)
        b = int(start[2] + (end[2] - start[2]) * local_t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return gradient


def _draw_centered_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, x: int, y: int
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((x - w // 2, y - h // 2), text, font=font, fill="white")


def _draw_rounded_rectangle(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    radius: int,
    fill: Tuple[int, int, int, int],
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _scale_dimensions(target: Tuple[int, int], upscale: float) -> Tuple[int, int]:
    return int(target[0] * upscale), int(target[1] * upscale)


def generate_wrapped_image(data: WrappedPayload, size: Literal["vertical", "square"]) -> BytesIO:
    sizes = {
        "vertical": (1080, 1920),
        "square": (1080, 1080),
    }
    if size not in sizes:
        raise ValueError("size must be 'vertical' or 'square'")

    final_width, final_height = sizes[size]
    upscale = 2.0
    canvas_width, canvas_height = _scale_dimensions((final_width, final_height), upscale)

    base = _create_gradient((canvas_width, canvas_height))
    draw = ImageDraw.Draw(base, "RGBA")

    title_font = _load_font(int(150 * upscale), bold=True)
    subtitle_font = _load_font(int(80 * upscale))
    card_title_font = _load_font(int(110 * upscale), bold=True)
    card_value_font = _load_font(int(70 * upscale))
    emoji_font = _load_font(int(130 * upscale))

    top_margin = int(120 * upscale)
    draw.text(
        (
            canvas_width // 2 - draw.textlength("Your WhatsApp Wrapped", font=title_font) / 2,
            top_margin,
        ),
        "Your WhatsApp Wrapped",
        font=title_font,
        fill="white",
    )

    subtitle = f"Chat: {data['chat_name']} · {data['year']}"
    subtitle_width = draw.textlength(subtitle, font=subtitle_font)
    draw.text(
        (canvas_width // 2 - subtitle_width / 2, top_margin + int(90 * upscale)),
        subtitle,
        font=subtitle_font,
        fill=(230, 230, 230),
    )

    avatar_radius = int(220 * upscale)
    avatar_center_y = top_margin + int(330 * upscale)
    avatar_bbox = (
        canvas_width // 2 - avatar_radius,
        avatar_center_y - avatar_radius,
        canvas_width // 2 + avatar_radius,
        avatar_center_y + avatar_radius,
    )
    draw.ellipse(
        avatar_bbox, fill=(255, 255, 255, 80), outline=(255, 255, 255, 180), width=int(8 * upscale)
    )
    initials_font = _load_font(int(200 * upscale), bold=True)
    avatar_text = data["user_initials"].upper()
    _draw_centered_text(draw, avatar_text, initials_font, canvas_width // 2, avatar_center_y)

    cards_top = avatar_center_y + avatar_radius + int(140 * upscale)
    card_height = int(220 * upscale)
    card_width = int(canvas_width * 0.88)
    card_x1 = (canvas_width - card_width) // 2
    card_x2 = card_x1 + card_width
    card_padding = int(45 * upscale)
    card_radius = int(45 * upscale)
    card_fill = (255, 255, 255, 90)

    stats: Iterable[WrappedStat] = data["stats"]
    for index, stat in enumerate(stats):
        y1 = cards_top + index * (card_height + int(25 * upscale))
        y2 = y1 + card_height
        _draw_rounded_rectangle(draw, (card_x1, y1, card_x2, y2), card_radius, card_fill)
        emoji_x = card_x1 + card_padding
        emoji_bbox = emoji_font.getbbox(stat["emoji"])
        emoji_height = emoji_bbox[3] - emoji_bbox[1]
        emoji_y = y1 + card_height // 2 - emoji_height // 2
        draw.text((emoji_x, emoji_y), stat["emoji"], font=emoji_font, fill=(255, 255, 255))

        text_x = emoji_x + int(140 * upscale)
        text_y = y1 + int(40 * upscale)
        draw.text((text_x, text_y), stat["label"], font=card_title_font, fill="white")

        value = stat["value"]
        max_chars = 28 if size == "vertical" else 22
        lines = wrap(value, width=max_chars) or [value]
        for idx, line in enumerate(lines[:2]):
            line_y = text_y + int(120 * upscale) + idx * int(70 * upscale)
            draw.text((text_x, line_y), line, font=card_value_font, fill=(230, 230, 230))

    resized = base.resize((final_width, final_height), Image.Resampling.LANCZOS)
    output = BytesIO()
    resized.save(output, format="PNG")
    output.seek(0)
    return output
