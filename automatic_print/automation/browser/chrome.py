"""Managed Chrome process used by Playwright production workflows."""

import json
import os
import platform
import subprocess
import time
from pathlib import Path
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
            for root in roots if root
        )
    if system == "Darwin":
        return (Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),)
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


def ensure_debug_chrome(start_url: str, check_cancel=None, progress=None) -> None:
    check = check_cancel or (lambda: None)
    report = progress or (lambda _message: None)
    check()
    report("正在检查 Chrome 自动化连接…")
    if chrome_is_connectable():
        report("Chrome 自动化连接可用。")
        return
    report("未检测到自动化浏览器，正在启动 Chrome…")
    profile = _profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            str(find_chrome()), f"--remote-debugging-port={DEBUG_PORT}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", start_url,
        ],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )
    for _ in range(150):
        check()
        if chrome_is_connectable():
            report("Chrome 已启动，自动化端口可以连接。")
            return
        time.sleep(0.1)
    raise TimeoutError("Chrome 启动超时。")
