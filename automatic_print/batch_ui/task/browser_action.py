"""Playwright browser action used by the batch worker."""

from ...automation.browser.session import show_debug_browser
from ...automation.providers.registry import get_erp_platform


def open_platform_browser(platform_name, check_cancel, progress):
    url = get_erp_platform(platform_name).production_items_url
    current = show_debug_browser(url, check_cancel, progress)
    return {
        "type": "browser_opened",
        "platform": platform_name,
        "url": current,
    }
