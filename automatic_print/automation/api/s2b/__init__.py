"""S2B batch metadata facade."""

from .metadata import (
    S2BBatchFolder,
    S2BBatchInfoError,
    color_for_path,
    fetch_s2b_batch_info,
    find_s2b_batch_folder,
    parse_s2b_batch_name,
    register_batch_records,
)

__all__ = [
    "S2BBatchFolder",
    "S2BBatchInfoError",
    "color_for_path",
    "fetch_s2b_batch_info",
    "find_s2b_batch_folder",
    "parse_s2b_batch_name",
    "register_batch_records",
]
