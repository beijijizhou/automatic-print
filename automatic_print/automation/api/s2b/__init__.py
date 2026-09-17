"""S2B batch metadata facade."""

from importlib import import_module

__all__ = [
    "S2BBatchFolder",
    "S2BBatchInfoError",
    "color_for_path",
    "fetch_s2b_batch_info",
    "find_s2b_batch_folder",
    "parse_s2b_batch_name",
    "register_batch_records",
]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(".metadata", __name__), name)
    globals()[name] = value
    return value
