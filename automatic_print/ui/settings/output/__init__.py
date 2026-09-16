"""Output section of the print settings page."""

from .dpi import build_output_dpi
from .format import build_output_settings
from .location import build_output_location, output_base
from .segmentation import SegmentedOutputSettings

__all__ = [
    "SegmentedOutputSettings",
    "build_output_dpi",
    "build_output_location",
    "build_output_settings",
    "output_base",
]
