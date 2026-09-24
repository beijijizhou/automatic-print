from __future__ import annotations

import time
from urllib.parse import urlsplit

from .chrome import CDP_URL, ensure_debug_chrome


def connect_debug_chrome(
    playwright, start_url: str, check_cancel=None, progress=None
):
    check = check_cancel or (lambda: None)
    report = progress or (lambda _message: None)
    ensure_debug_chrome(start_url, check, report)
    check()
    report("正在连接 Chrome 自动化会话…")
    browser = playwright.chromium.connect_over_cdp(CDP_URL, timeout=30_000)
    check()
    report("Chrome 自动化会话连接完成。")
    return browser


def show_debug_browser(start_url: str, check_cancel=None, progress=None) -> str:
    """Open or foreground one Playwright Chrome tab without waiting for login."""
    from playwright.sync_api import sync_playwright

    check = check_cancel or (lambda: None)
    report = progress or (lambda _message: None)
    with sync_playwright() as playwright:
        browser = connect_debug_chrome(playwright, start_url, check, report)
        check()
        host = urlsplit(start_url).netloc
        pages = [
            page for context in browser.contexts for page in context.pages
            if host in page.url
        ]
        if pages:
            page = pages[-1]
            report(f"正在显示已打开的 {host} 页面…")
        else:
            context = browser.contexts[0]
            page = context.new_page()
            report(f"正在打开 {host}…")
            page.goto(start_url, wait_until="domcontentloaded", timeout=30_000)
        page.bring_to_front()
        report("Playwright 浏览器已显示；可先完成登录，再点击读取预览。")
        return page.url


def open_authenticated_page(
    browser,
    target_url: str,
    ready_selector: str,
    login_timeout_ms: int = 180_000,
    progress=None,
    ready_state="visible",
    check_cancel=None,
):
    """Open an ERP route, waiting for the user to finish login if required."""
    report = progress or (lambda _message: None)
    check = check_cancel or (lambda: None)
    check()
    host = urlsplit(target_url).netloc
    report(f"正在查找 {host} 已打开的目标页面…")
    exact_pages = [
        page
        for context in browser.contexts
        for page in context.pages
        if host in page.url
        and urlsplit(target_url).path in page.url
        and "/login" not in page.url
    ]
    if exact_pages:
        page = exact_pages[-1]
        report(f"已找到目标页面，正在核对登录和数据区：{page.url}")
    else:
        authenticated_pages = [
            page
            for context in browser.contexts
            for page in context.pages
            if host in page.url and "/login" not in page.url
        ]
        if authenticated_pages:
            report("已找到登录有效的页面，正在新建目标页签…")
            page = authenticated_pages[-1].context.new_page()
        else:
            host_pages = [
                page
                for context in browser.contexts
                for page in context.pages
                if host in page.url
            ]
            context = (
                host_pages[-1].context
                if host_pages
                else browser.contexts[0]
            )
            page = host_pages[-1] if host_pages else context.new_page()
            report(
                "正在复用平台页签…" if host_pages
                else "正在新建平台页签…"
            )
        report(f"正在打开 {host}…")
        check()
        page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)
        check()

    page.bring_to_front()
    report("Playwright 自动化浏览器已显示为当前平台浏览器。")

    return _wait_for_authenticated_target(
        page, target_url, ready_selector, ready_state,
        login_timeout_ms, report, check,
    )


def _wait_for_authenticated_target(
    page, target_url, ready_selector, ready_state,
    login_timeout_ms, report, check_cancel,
):
    """Follow delayed login redirects without making the user restart the task."""
    host = urlsplit(target_url).netloc
    target_path = urlsplit(target_url).path
    login_deadline = time.monotonic() + login_timeout_ms / 1000
    ready_deadline = time.monotonic() + 30
    login_reported = False
    was_login = False
    last_wait_report = time.monotonic()
    report(f"页面已打开，正在等待 ERP 数据区域：{page.url}")
    while True:
        check_cancel()
        try:
            locator = page.locator(ready_selector).first
            ready = locator.count() > 0 and (
                ready_state == "attached" or locator.is_visible()
            )
        except Exception:
            # A redirect can destroy the old DOM between the two checks.
            ready = False
        if ready:
            report("ERP 数据区域已加载。")
            return page

        now = time.monotonic()
        on_login = "/login" in page.url
        if on_login:
            was_login = True
            if not login_reported:
                report(f"请在已打开的 {host} 页面完成登录…")
                login_reported = True
            if now >= login_deadline:
                raise TimeoutError("等待 ERP 登录超时，请登录后重试。")
        else:
            if was_login:
                report("登录成功，正在进入生产项管理页面…")
                if target_path not in page.url:
                    check_cancel()
                    page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)
                    check_cancel()
                ready_deadline = time.monotonic() + 30
                was_login = False
            if now >= ready_deadline:
                raise RuntimeError(
                    "ERP 页面已打开，但数据区域在 30 秒内没有加载完成。\n"
                    f"当前页面：{page.url}\n"
                    "请确认页面没有验证码、登录提示或错误弹窗。"
                )
            if now - last_wait_report >= 5:
                report(f"仍在等待 ERP 数据区域：{page.url}")
                last_wait_report = now
        page.wait_for_timeout(250)
