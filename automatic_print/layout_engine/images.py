from pathlib import Path
from dataclasses import dataclass
import math

from PIL import Image


@dataclass(frozen=True)
class PrintDimensions:
    width_mm: float
    height_mm: float
    x_dpi: float
    y_dpi: float
    embedded_dpi: bool


def print_dimensions(path: Path, fallback_dpi: int) -> PrintDimensions:
    from .measurement_session import SESSION, identity
    session = SESSION.get()
    key = (identity(path), fallback_dpi) if session else None
    if session and key in session.dimensions:
        return session.dimensions[key]
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
        session.dimensions[key] = result
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
