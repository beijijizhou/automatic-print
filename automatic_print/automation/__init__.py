"""Browser automation for receiving and downloading production images.

The layout engine imports provider-specific metadata below this package.  Keep
the package root cheap: importing S2B metadata must not also initialise browser
automation and unrelated ERP providers.
"""

from importlib import import_module

__all__ = [
    "BatchPreview",
    "ShippingBatchPlan",
    "download_production_images",
    "extract_production_archives",
    "preview_filtered_batch",
    "preview_shipping_split",
    "select_batch_filters",
]

_DOWNLOAD_EXPORTS = {
    "download_production_images",
    "extract_production_archives",
}
_LONGFENG_EXPORTS = set(__all__) - _DOWNLOAD_EXPORTS


def __getattr__(name):
    if name in _DOWNLOAD_EXPORTS:
        module = import_module(".transfer.downloads", __name__)
    elif name in _LONGFENG_EXPORTS:
        module = import_module(".providers.longfeng", __name__)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(module, name)
    globals()[name] = value
    return value
