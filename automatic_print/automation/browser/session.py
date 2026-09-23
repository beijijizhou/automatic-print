from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.error import URLError
from urllib.request import urlopen


DEBUG_PORT = 9222
CDP_URL = f"http://127.0.0.1:{DEBUG_PORT}"


def _chrome_candidates() -> tuple[Path, ...]:
    system = platform.system()
    if system == "Windows":
        roots = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        return tuple(
            Path(root) / "Google/Chrome/Application/chrome.exe"
            for root in roots
            if root
        )
    if system == "Darwin":
        return (
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        )
    return (
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/google-chrome-stable"),
        Path("/usr/bin/chromium"),
    )


def _profile_dir() -> Path:
    if platform.system() == "Windows" and os.environ.get("LOCALAPPDATA"):
        root = Path(os.environ["LOCALAPPDATA"])
    elif platform.system() == "Darwin":
        root = Path.home() / "Library/Application Support"
    else:
        root = Path.home() / ".local/share"
    return root / "AutomaticPrint/browser-profile"


def find_chrome() -> Path:
    for candidate in _chrome_candidates():
        if candidate.exists():
            return candidate
    raise FileNotFoundError("未找到 Google Chrome，请先安装 Chrome。")


def chrome_is_connectable() -> bool:
    try:
        with urlopen(f"{CDP_URL}/json/list", timeout=1) as response:
            targets = json.load(response)
        return any(target.get("type") == "page" for target in targets)
    except (json.JSONDecodeError, OSError, URLError, TimeoutError):
        return False


def ensure_debug_chrome(start_url: str) -> None:
    if chrome_is_connectable():
        return
    profile = _profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            str(find_chrome()),
            f"--remote-debugging-port={DEBUG_PORT}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            start_url,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(150):
        if chrome_is_connectable():
            return
        time.sleep(0.1)
    raise TimeoutError("Chrome 启动超时。")


def connect_debug_chrome(playwright, start_url: str):
    ensure_debug_chrome(start_url)
    return playwright.chromium.connect_over_cdp(CDP_URL, timeout=30_000)


def open_authenticated_page(
    browser,
    target_url: str,
    ready_selector: str,
    login_timeout_ms: int = 180_000,
    progress=None,
    ready_state="visible",
):
    """Open an ERP route, waiting for the user to finish login if required."""
    report = progress or (lambda _message: None)
    host = urlsplit(target_url).netloc
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
    else:
        authenticated_pages = [
            page
            for context in browser.contexts
            for page in context.pages
            if host in page.url and "/login" not in page.url
        ]
        if authenticated_pages:
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
        report(f"正在打开 {host}…")
        page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)

    return _wait_for_authenticated_target(
        page, target_url, ready_selector, ready_state,
        login_timeout_ms, report,
    )


def _wait_for_authenticated_target(
    page, target_url, ready_selector, ready_state,
    login_timeout_ms, report,
):
    """Follow delayed login redirects without making the user restart the task."""
    host = urlsplit(target_url).netloc
    target_path = urlsplit(target_url).path
    login_deadline = time.monotonic() + login_timeout_ms / 1000
    ready_deadline = time.monotonic() + 30
    login_reported = False
    was_login = False
    report(f"页面已打开，正在等待 ERP 数据区域：{page.url}")
    while True:
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
                    page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)
                ready_deadline = time.monotonic() + 30
                was_login = False
            if now >= ready_deadline:
                raise RuntimeError(
                    "ERP 页面已打开，但数据区域在 30 秒内没有加载完成。\n"
                    f"当前页面：{page.url}\n"
                    "请确认页面没有验证码、登录提示或错误弹窗。"
                )
        page.wait_for_timeout(250)
