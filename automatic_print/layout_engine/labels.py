from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import mm_to_px


def _font(size: int):
    candidates = (
        "DejaVuSans-Bold.ttf",
        "arialbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def label_badge(text: str, dpi: int, size_mm: float) -> Image.Image:
    size = max(10, mm_to_px(size_mm, dpi))
    font = _font(size)
    text = text or " "
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    stroke = max(1, size // 25)
    bounds = measure.textbbox((0, 0), text, font=font, stroke_width=stroke)
    padding = max(4, round(size * 0.28))
    width = bounds[2] - bounds[0] + padding * 2
    height = bounds[3] - bounds[1] + padding * 2
    badge = Image.new("RGBA", (width, height), (255, 255, 255, 235))
    draw = ImageDraw.Draw(badge)
    draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=max(3, height // 5),
        fill=(255, 255, 255, 235),
        outline=(0, 0, 0, 255),
        width=max(2, size // 18),
    )
    draw.text(
        (
            (width - (bounds[2] - bounds[0])) / 2 - bounds[0],
            (height - (bounds[3] - bounds[1])) / 2 - bounds[1],
        ),
        text,
        font=font,
        fill=(0, 0, 0, 255),
        stroke_width=stroke,
        stroke_fill=(255, 255, 255, 255),
    )
    return badge


def format_label(
    template: str,
    number: int,
    path: Path,
    created_at: datetime,
    date_format: str,
) -> str:
    aliases = {
        "{编号}": "{number}",
        "{日期}": "{date}",
        "{完整文件名}": "{filename}",
        "{文件名}": "{stem}",
    }
    for chinese, internal in aliases.items():
        template = template.replace(chinese, internal)
    values = {
        "number": str(number),
        "date": created_at.strftime(date_format),
        "filename": path.name,
        "stem": path.stem,
    }
    try:
        return template.format_map(values)
    except (KeyError, ValueError) as error:
        raise ValueError(
            "标签文字模板无效。可用内容："
            "{编号}、{日期}、{完整文件名}、{文件名}。"
        ) from error


def label_layout(
    image_size: tuple[int, int],
    label_size: tuple[int, int],
    position: str,
    gap: int,
    offset_x: int,
    offset_y: int,
) -> tuple[int, int, int, int, int, int]:
    width, height = image_size
    label_width, label_height = label_size
    positions = {
        "top_left": (offset_x, -gap - label_height + offset_y),
        "top_right": (
            width - label_width + offset_x,
            -gap - label_height + offset_y,
        ),
        "bottom_left": (offset_x, height + gap + offset_y),
        "bottom_right": (
            width - label_width + offset_x,
            height + gap + offset_y,
        ),
        "top": (
            (width - label_width) // 2 + offset_x,
            -gap - label_height + offset_y,
        ),
        "left": (
            -gap - label_width + offset_x,
            (height - label_height) // 2 + offset_y,
        ),
        "right": (
            width + gap + offset_x,
            (height - label_height) // 2 + offset_y,
        ),
        "bottom": (
            (width - label_width) // 2 + offset_x,
            height + gap + offset_y,
        ),
    }
    label_x, label_y = positions.get(position, positions["bottom"])
    min_x, min_y = min(0, label_x), min(0, label_y)
    max_x = max(width, label_x + label_width)
    max_y = max(height, label_y + label_height)
    return (
        -min_x,
        -min_y,
        label_x - min_x,
        label_y - min_y,
        max_x - min_x,
        max_y - min_y,
    )
