from pathlib import Path
from dataclasses import dataclass
import math
import sqlite3

from PIL import Image
from automatic_print.layout_engine.measurement.measurement_timing import substep


@dataclass(frozen=True)
class PrintDimensions:
    width_mm: float
    height_mm: float
    x_dpi: float
    y_dpi: float
    embedded_dpi: bool


def print_dimensions(path: Path, fallback_dpi: int) -> PrintDimensions:
    from automatic_print.layout_engine.measurement.measurement_session import SESSION, identity, persistent_cache
    session = SESSION.get()
    file_key = identity(path) if session else None
    embedded_key = (file_key, None) if session else None
    fallback_key = (file_key, fallback_dpi) if session else None
    if session and embedded_key in session.dimensions:
        return session.dimensions[embedded_key]
    if session and fallback_key in session.dimensions:
        return session.dimensions[fallback_key]
    persistent, persistent_key = None, None
    if session:
        try:
            from automatic_print.layout_engine.measurement.measurement_cache import dimension_key
            persistent = persistent_cache()
            persistent_key = dimension_key(file_key, None)
            cached = persistent.load('dimensions', persistent_key)
            if cached is None:
                persistent_key = dimension_key(file_key, fallback_dpi)
                cached = persistent.load('dimensions', persistent_key)
            if cached is not None:
                result = PrintDimensions(**cached)
                cache_key = embedded_key if result.embedded_dpi else fallback_key
                session.dimensions[cache_key] = result
                return result
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            persistent = persistent_key = None
    with substep('尺寸与DPI文件信息读取'):
        with Image.open(path) as image:
            source = image.info.get("dpi")
            try:
                x_dpi, y_dpi = float(source[0]), float(source[1])
                valid = all(math.isfinite(v) and v > 0 for v in (x_dpi, y_dpi))
            except (TypeError, ValueError, IndexError):
                valid = False
            if not valid:
                x_dpi = y_dpi = float(fallback_dpi)
            result = PrintDimensions(
                image.width * 25.4 / x_dpi,
                image.height * 25.4 / y_dpi,
                x_dpi, y_dpi, valid,
            )
    if session:
        cache_key = embedded_key if result.embedded_dpi else fallback_key
        session.dimensions[cache_key] = result
        if persistent is not None and persistent_key is not None:
            try:
                from dataclasses import asdict
                persistent_key = dimension_key(
                    file_key, None if result.embedded_dpi else fallback_dpi,
                )
                persistent.save('dimensions', persistent_key, asdict(result))
            except (OSError, ValueError, TypeError, sqlite3.Error):
                pass
    return result


def target_size(path: Path, target_dpi: int) -> tuple[int, int]:
    size = print_dimensions(path, target_dpi)
    return (
        max(1, round(size.width_mm * target_dpi / 25.4)),
        max(1, round(size.height_mm * target_dpi / 25.4)),
    )


def normalized_image(
    path: Path, target_size_px: tuple[int, int]
) -> Image.Image:
    image = Image.open(path)
    image.load()
    image = image.convert("RGBA")
    if image.size != target_size_px:
        image = image.resize(target_size_px, Image.Resampling.LANCZOS)
    return image
