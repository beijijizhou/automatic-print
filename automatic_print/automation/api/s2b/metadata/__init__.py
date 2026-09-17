"""S2B batch identity, gateway metadata, and local-image matching."""

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

_MODULES = {
    "S2BBatchFolder": ".batch_name",
    "find_s2b_batch_folder": ".batch_name",
    "parse_s2b_batch_name": ".batch_name",
    "S2BBatchInfoError": ".client",
    "fetch_s2b_batch_info": ".client",
    "color_for_path": ".store",
    "register_batch_records": ".store",
}


def __getattr__(name):
    module_name = _MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value
