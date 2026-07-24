from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import groupby
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable

from PIL import Image, ImageDraw, ImageFont

try:
    import pyvips
except (ImportError, OSError):  # Pillow remains a safe fallback for old installs.
    pyvips = None


SUPPORTED_EXTENSIONS = {
    ".png",
    ".tif",
    ".tiff",
    ".jpg",
    ".jpeg",
    ".jfif",
    ".webp",
    ".bmp",
}
ProgressCallback = Callable[[str, int, int, str], None]


def png_engine_name() -> str:
    return "libvips" if pyvips is not None else "Pillow（兼容模式）"


@dataclass(frozen=True)
class LayoutSettings:
    media_width_mm: float = 600
    spacing_mm: float = 3
    margin_mm: float = 3
    dpi: int = 300
    png_compression_level: int = 1
    png_engine: str = "pillow"
    worker_threads: int = 8
    number_images: bool = True
    number_gap_mm: float = 5
    number_font_size_mm: float = 10
    label_text_template: str = "{number}"
    label_position: str = "bottom"
    label_offset_x_mm: float = 0
    label_offset_y_mm: float = 0
    label_date_format: str = "%Y-%m-%d"


@dataclass(frozen=True)
class Placement:
    source: str
    sequence_number: int
    x_px: int
    y_px: int
    width_px: int
    height_px: int
    number_x_px: int
    number_y_px: int
    number_width_px: int
    number_height_px: int
    row_y_px: int
    footprint_width_px: int
    footprint_height_px: int


def mm_to_px(value: float, dpi: int) -> int:
    return max(0, round(value * dpi / 25.4))


def discover_images(folder: Path) -> list[Path]:
    return sorted(
        path for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def discovered_extensions(folder: Path) -> list[str]:
    return sorted(
        {path.suffix.lower() or "(no extension)" for path in folder.rglob("*") if path.is_file()}
    )


def _target_size(path: Path, target_dpi: int) -> tuple[int, int]:
    with Image.open(path) as image:
        source_dpi = image.info.get("dpi", (target_dpi, target_dpi))
        x_dpi = float(source_dpi[0] or target_dpi)
        y_dpi = float(source_dpi[1] or target_dpi)
        return (
            max(1, round(image.width * target_dpi / x_dpi)),
            max(1, round(image.height * target_dpi / y_dpi)),
        )


def _normalized_image(
    path: Path, target_dpi: int, target_size: tuple[int, int]
) -> Image.Image:
    image = Image.open(path)
    image.load()
    image = image.convert("RGBA")
    if image.size != target_size:
        image = image.resize(target_size, Image.Resampling.LANCZOS)
    return image


def _number_font(font_size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = (
        "DejaVuSans-Bold.ttf",
        "arialbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, font_size_px)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=font_size_px)
    except TypeError:  # Compatibility with older Pillow releases.
        return ImageFont.load_default()


def _label_badge(text: str, dpi: int, font_size_mm: float) -> Image.Image:
    font_size_px = max(10, mm_to_px(font_size_mm, dpi))
    font = _number_font(font_size_px)
    label = text or " "
    measuring = ImageDraw.Draw(Image.new("L", (1, 1)))
    stroke_width = max(1, font_size_px // 25)
    bounds = measuring.textbbox(
        (0, 0), label, font=font, stroke_width=stroke_width
    )
    padding = max(4, round(font_size_px * 0.28))
    text_width = bounds[2] - bounds[0]
    text_height = bounds[3] - bounds[1]
    badge_width = text_width + (padding * 2)
    badge_height = text_height + (padding * 2)
    badge = Image.new("RGBA", (badge_width, badge_height), (255, 255, 255, 235))
    draw = ImageDraw.Draw(badge)
    outline_width = max(2, font_size_px // 18)
    draw.rounded_rectangle(
        (0, 0, badge_width - 1, badge_height - 1),
        radius=max(3, badge_height // 5),
        fill=(255, 255, 255, 235),
        outline=(0, 0, 0, 255),
        width=outline_width,
    )
    draw.text(
        (
            (badge_width - text_width) / 2 - bounds[0],
            (badge_height - text_height) / 2 - bounds[1],
        ),
        label,
        font=font,
        fill=(0, 0, 0, 255),
        stroke_width=stroke_width,
        stroke_fill=(255, 255, 255, 255),
    )
    return badge


def _format_label(
    template: str, number: int, path: Path, created_at: datetime, date_format: str
) -> str:
    for chinese, internal in {
        "{编号}": "{number}",
        "{日期}": "{date}",
        "{完整文件名}": "{filename}",
        "{文件名}": "{stem}",
    }.items():
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


def _label_layout(
    image_width: int,
    image_height: int,
    label_width: int,
    label_height: int,
    position: str,
    gap: int,
    offset_x: int,
    offset_y: int,
) -> tuple[int, int, int, int, int, int]:
    if position == "top_left":
        label_x = offset_x
        label_y = -gap - label_height + offset_y
    elif position == "top_right":
        label_x = image_width - label_width + offset_x
        label_y = -gap - label_height + offset_y
    elif position == "bottom_left":
        label_x = offset_x
        label_y = image_height + gap + offset_y
    elif position == "bottom_right":
        label_x = image_width - label_width + offset_x
        label_y = image_height + gap + offset_y
    elif position == "top":
        label_x = (image_width - label_width) // 2 + offset_x
        label_y = -gap - label_height + offset_y
    elif position == "left":
        label_x = -gap - label_width + offset_x
        label_y = (image_height - label_height) // 2 + offset_y
    elif position == "right":
        label_x = image_width + gap + offset_x
        label_y = (image_height - label_height) // 2 + offset_y
    else:
        label_x = (image_width - label_width) // 2 + offset_x
        label_y = image_height + gap + offset_y

    min_x = min(0, label_x)
    min_y = min(0, label_y)
    max_x = max(image_width, label_x + label_width)
    max_y = max(image_height, label_y + label_height)
    return (
        -min_x,
        -min_y,
        label_x - min_x,
        label_y - min_y,
        max_x - min_x,
        max_y - min_y,
    )


def _prepare_image(
    item: tuple[Path, Placement], dpi: int
) -> tuple[Image.Image, Placement]:
    path, placement = item
    image = _normalized_image(path, dpi, (placement.width_px, placement.height_px))
    return image, placement


def _vips_rgba(path: Path, width: int, height: int):
    """Build a lazy, exactly-sized 8-bit RGBA libvips image."""
    image = pyvips.Image.new_from_file(str(path), access="sequential")
    interpretation = str(image.interpretation)

    # Convert colour-managed formats such as CMYK before interpreting band 4 as
    # alpha. Standard RGB/RGBA and greyscale files can be handled directly.
    if interpretation not in {
        "srgb",
        "rgb",
        "b-w",
        "grey16",
        "multiband",
    }:
        image = image.colourspace("srgb")

    image = image.thumbnail_image(
        width,
        height=height,
        size="force",
        no_rotate=True,
    )
    if image.format != "uchar":
        image = image.cast("uchar")

    if image.bands == 1:
        grey = image[0]
        image = grey.bandjoin([grey, grey, 255])
    elif image.bands == 2:
        grey = image[0]
        image = grey.bandjoin([grey, grey, image[1]])
    elif image.bands == 3:
        image = image.bandjoin(255)
    elif image.bands > 4:
        image = image.extract_band(0, n=4)

    return image.copy(interpretation="srgb")


def _build_vips_canvas(
    planned: list[tuple[Path, Placement]],
    canvas_width: int,
    canvas_height: int,
    dpi: int,
    number_images: bool,
    number_font_size_mm: float,
    labels: dict[int, str],
    progress: ProgressCallback | None,
):
    margin = min(
        min(
            placement.x_px,
            placement.number_x_px if number_images else placement.x_px,
        )
        for _, placement in planned
    )
    usable_width = canvas_width - (2 * margin)
    rows = []
    total = len(planned)
    completed = 0

    # Composite only the images that occupy the same shelf row. A single
    # hundreds-of-layers composite makes every output strip inspect every source
    # image; row-sized composites keep the streaming pipeline small and local.
    for row_y, row_items_iter in groupby(
        planned, key=lambda item: item[1].row_y_px
    ):
        row_items = list(row_items_iter)
        row_height = max(
            placement.footprint_height_px for _, placement in row_items
        )
        row_canvas = pyvips.Image.black(
            usable_width, row_height, bands=4
        ).copy(interpretation="srgb")
        layers = []
        x_positions = []
        y_positions = []
        for path, placement in row_items:
            layers.append(_vips_rgba(path, placement.width_px, placement.height_px))
            x_positions.append(placement.x_px - margin)
            y_positions.append(placement.y_px - row_y)
            if number_images:
                badge = _label_badge(
                    labels[placement.sequence_number], dpi, number_font_size_mm
                )
                layers.append(
                    pyvips.Image.new_from_memory(
                        badge.tobytes(), badge.width, badge.height, 4, "uchar"
                    ).copy(interpretation="srgb")
                )
                x_positions.append(placement.number_x_px - margin)
                y_positions.append(placement.number_y_px - row_y)
                badge.close()
            completed += 1
            if progress:
                progress("合成图片", completed, total, placement.source)
        row_canvas = row_canvas.composite(
            layers,
            ["over"] * len(layers),
            x=x_positions,
            y=y_positions,
        )
        rows.append((row_y, row_height, row_canvas))

    _, previous_height, canvas = rows[0]
    previous_y = rows[0][0]
    for row_y, row_height, row_canvas in rows[1:]:
        gap = row_y - (previous_y + previous_height)
        canvas = canvas.join(
            row_canvas,
            "vertical",
            expand=True,
            shim=gap,
            background=[0, 0, 0, 0],
            align="low",
        )
        previous_y = row_y
        previous_height = row_height

    canvas = canvas.embed(
        margin,
        margin,
        canvas_width,
        canvas_height,
        extend="background",
        background=[0, 0, 0, 0],
    )
    pixels_per_mm = dpi / 25.4
    return canvas.copy(xres=pixels_per_mm, yres=pixels_per_mm)


def generate_layout(
    image_paths: Iterable[Path],
    output_dir: Path,
    settings: LayoutSettings,
    progress: ProgressCallback | None = None,
) -> dict:
    total_started = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    canvas_width = mm_to_px(settings.media_width_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    number_gap = mm_to_px(settings.number_gap_mm, settings.dpi)
    offset_x = mm_to_px(abs(settings.label_offset_x_mm), settings.dpi)
    if settings.label_offset_x_mm < 0:
        offset_x = -offset_x
    offset_y = mm_to_px(abs(settings.label_offset_y_mm), settings.dpi)
    if settings.label_offset_y_mm < 0:
        offset_y = -offset_y
    usable_width = canvas_width - (2 * margin)
    if usable_width <= 0:
        raise ValueError("外边距过大，画布没有可打印区域。")

    paths = list(image_paths)
    planned: list[tuple[Path, Placement]] = []
    x = y = margin
    row_height = 0

    # First pass only reads metadata and calculates the exact required height.
    reading_started = perf_counter()
    total = len(paths)
    created_at = datetime.now().astimezone()
    labels: dict[int, str] = {}
    for index, path in enumerate(paths, start=1):
        width, height = _target_size(path, settings.dpi)
        if settings.number_images:
            label_text = _format_label(
                settings.label_text_template,
                index,
                path,
                created_at,
                settings.label_date_format,
            )
            labels[index] = label_text
            badge = _label_badge(
                label_text, settings.dpi, settings.number_font_size_mm
            )
            number_width, number_height = badge.size
            badge.close()
            (
                image_relative_x,
                image_relative_y,
                number_relative_x,
                number_relative_y,
                footprint_width,
                footprint_height,
            ) = _label_layout(
                width,
                height,
                number_width,
                number_height,
                settings.label_position,
                number_gap,
                offset_x,
                offset_y,
            )
        else:
            number_width = number_height = 0
            image_relative_x = image_relative_y = 0
            number_relative_x = number_relative_y = 0
            footprint_width, footprint_height = width, height
        if footprint_width > usable_width:
            raise ValueError(f"图片 {path.name} 的宽度超过了材料可打印宽度。")
        if x > margin and x + footprint_width > canvas_width - margin:
            x = margin
            y += row_height + spacing
            row_height = 0
        image_x = x + image_relative_x
        image_y = y + image_relative_y
        number_x = x + number_relative_x
        number_y = y + number_relative_y
        placement = Placement(
            path.name,
            index,
            image_x,
            image_y,
            width,
            height,
            number_x,
            number_y,
            number_width,
            number_height,
            y,
            footprint_width,
            footprint_height,
        )
        planned.append((path, placement))
        x += footprint_width + spacing
        row_height = max(row_height, footprint_height)
        if progress:
            progress("读取图片尺寸", index, total, path.name)
    reading_seconds = perf_counter() - reading_started

    if not planned:
        raise ValueError("没有可供排版的图片。")

    canvas_height = y + row_height + margin
    combining_started = perf_counter()
    use_libvips = settings.png_engine == "libvips" and pyvips is not None
    if use_libvips:
        canvas = _build_vips_canvas(
            planned,
            canvas_width,
            canvas_height,
            settings.dpi,
            settings.number_images,
            settings.number_font_size_mm,
            labels,
            progress,
        )
        png_engine = "libvips"
    else:
        canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
        workers = max(1, min(settings.worker_threads, total))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            prepared = executor.map(
                lambda item: _prepare_image(item, settings.dpi),
                planned,
            )
            for index, (image, placement) in enumerate(prepared, start=1):
                canvas.paste(image, (placement.x_px, placement.y_px))
                image.close()
                if settings.number_images:
                    badge = _label_badge(
                        labels[placement.sequence_number],
                        settings.dpi,
                        settings.number_font_size_mm,
                    )
                    canvas.alpha_composite(
                        badge, (placement.number_x_px, placement.number_y_px)
                    )
                    badge.close()
                if progress:
                    progress("合成图片", index, total, placement.source)
        png_engine = "Pillow"
    combining_seconds = perf_counter() - combining_started

    filename = "print.png"
    if progress:
        progress("保存 PNG", 0, canvas_width * canvas_height, filename)
    saving_started = perf_counter()
    output_path = output_dir / filename
    if use_libvips:
        canvas.pngsave(
            str(output_path),
            compression=settings.png_compression_level,
            interlace=False,
        )
    else:
        canvas.save(
            output_path,
            dpi=(settings.dpi, settings.dpi),
            compress_level=settings.png_compression_level,
        )
    saving_seconds = perf_counter() - saving_started
    if not use_libvips:
        canvas.close()
    file_size_bytes = output_path.stat().st_size
    return {
        "filename": filename,
        "width_px": canvas_width,
        "height_px": canvas_height,
        "width_mm": round(canvas_width * 25.4 / settings.dpi, 1),
        "height_mm": round(canvas_height * 25.4 / settings.dpi, 1),
        "file_size_bytes": file_size_bytes,
        "png_compression_level": settings.png_compression_level,
        "png_engine": png_engine,
        "output_megabytes_per_second": round(
            file_size_bytes / 1_000_000 / max(saving_seconds, 0.001), 1
        ),
        "output_megapixels_per_second": round(
            canvas_width * canvas_height
            / 1_000_000
            / max(saving_seconds, 0.001),
            1,
        ),
        "placements": [asdict(item) for _, item in planned],
        "timings_seconds": {
            "reading": round(reading_seconds, 3),
            "combining": round(combining_seconds, 3),
            "saving_png": round(saving_seconds, 3),
            "total": round(perf_counter() - total_started, 3),
        },
    }
