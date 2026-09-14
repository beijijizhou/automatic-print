from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from threading import local
from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFont

from .models import mm_to_px
from .decorations import combined_footprint, outside_position


_FONTS = local()


def _font(size: int):
    if not hasattr(_FONTS, 'cache'):
        _FONTS.cache = OrderedDict()
    cache = _FONTS.cache
    if size not in cache:
        cache[size] = _load_font(size)
        if len(cache) > 32:
            cache.popitem(last=False)
    cache.move_to_end(size)
    return cache[size]


def _load_font(size: int):
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


def label_badge(text: str, dpi: int, size_mm: float, max_width_px=None) -> Image.Image:
    size = max(1, mm_to_px(size_mm, dpi))
    font = _font(size)
    text = text or " "
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    stroke = max(1, size // 25)
    bounds = measure.textbbox((0, 0), text, font=font, stroke_width=stroke)
    padding = max(2, round(size * 0.05))
    spacing = max(1, size // 10)
    if max_width_px is not None:
        text = _wrap_text(text, measure, font, max_width_px - padding * 2, stroke)
        bounds = measure.multiline_textbbox(
            (0, 0), text, font=font, stroke_width=stroke, spacing=spacing
        )
    width = bounds[2] - bounds[0] + padding * 2
    height = bounds[3] - bounds[1] + padding * 2
    badge = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge)
    draw.multiline_text(
        (
            (width - (bounds[2] - bounds[0])) / 2 - bounds[0],
            (height - (bounds[3] - bounds[1])) / 2 - bounds[1],
        ),
        text,
        font=font,
        fill=(0, 0, 0, 255),
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, 255),
        spacing=spacing,
    )
    return badge


def settings_label_badge(text, settings):
    if settings.label_fit_height:
        target = mm_to_px(settings.label_reference_height_mm, settings.dpi)
        low, high, best = 0.5, settings.number_font_size_mm, None
        for _ in range(14):
            size = (low + high) / 2
            badge = label_badge(text, settings.dpi, size)
            if badge.height <= target:
                if best is not None:
                    best.close()
                best, low = badge, size
            else:
                badge.close()
                high = size
        if best is None:
            raise ValueError("文字无法在膜标签高度内保持可读字号，请减少文字或换行。")
        return best
    maximum = (
        mm_to_px(settings.color_block_width_mm, settings.dpi)
        if settings.label_position == "block_below" else None
    )
    return label_badge(text, settings.dpi, settings.number_font_size_mm, maximum)


def compact_label_text(text):
    return re.sub(r"_{2,}", "", text)


def _wrap_text(text, measure, font, maximum, stroke):
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for character in paragraph:
            candidate = line + character
            bounds = measure.textbbox((0, 0), candidate, font=font, stroke_width=stroke)
            if line and bounds[2] - bounds[0] > maximum:
                lines.append(line.rstrip())
                line = character.lstrip()
            else:
                line = candidate
        lines.append(line.rstrip())
    return "\n".join(lines)


def format_label(
    template: str,
    number: int,
    path: Path,
    created_at: datetime,
    date_format: str,
    machine_number: str = "M1",
) -> str:
    machine_number = normalize_machine_number(machine_number)
    aliases = {
        "{编号}": "{number}",
        "{日期}": "{date}",
        "{完整文件名}": "{filename}",
        "{文件名}": "{stem}",
        "{机器号}": "{machine}",
    }
    for chinese, internal in aliases.items():
        template = template.replace(chinese, internal)
    values = {
        "number": str(number),
        "date": created_at.strftime(date_format),
        "filename": path.name,
        "stem": path.stem,
        "machine": machine_number,
    }
    try:
        return compact_label_text(template.format_map(values))
    except (KeyError, ValueError) as error:
        raise ValueError(
            "标签文字模板无效。可用内容："
            "{编号}、{日期}、{完整文件名}、{文件名}、{机器号}。"
        ) from error


def normalize_machine_number(value):
    value = value.upper()
    if value not in {f"M{i}" for i in range(1, 12)}:
        raise ValueError("机器号必须是 M1 到 M11。")
    return value


def label_layout(
    image_size: tuple[int, int],
    label_size: tuple[int, int],
    position: str,
    gap: int,
    offset_x: int,
    offset_y: int,
) -> tuple[int, int, int, int, int, int]:
    label_width, label_height = label_size
    label_x, label_y = outside_position(
        image_size, label_size, position, gap, offset_x, offset_y
    )
    image_rx, image_ry, footprint_width, footprint_height = (
        combined_footprint(
            image_size,
            [(label_x, label_y, label_width, label_height)],
        )
    )
    return (
        image_rx,
        image_ry,
        label_x + image_rx,
        label_y + image_ry,
        footprint_width,
        footprint_height,
    )
