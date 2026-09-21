"""Source-mode gateway key from the factory share, cached per Windows user."""

import os
import tempfile
from pathlib import Path

from automatic_print.automation.api.gateway_credentials import gateway_client_key


DEFAULT_SHARE_KEY_FILE = Path(r"\\192.168.11.28\dtf\.automatic-print\ydwx-gateway.key")


def share_key_file():
    override = os.environ.get("AUTOMATIC_PRINT_YDWX_SHARE_KEY_FILE", "").strip()
    return Path(override) if override else DEFAULT_SHARE_KEY_FILE


def cache_key_file():
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "AutomaticPrint" / "credentials" / "ydwx-gateway.key"
    return Path.home() / ".automatic-print" / "credentials" / "ydwx-gateway.key"


def _read_key(path):
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
    return value if len(value) >= 32 and "\n" not in value else ""


def _cache_key(value):
    target = cache_key_file()
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".ydwx-", dir=target.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
        os.replace(temporary, target)
    except OSError:
        # Shared access remains usable even when the local profile is read-only.
        return
    finally:
        if temporary:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass


def client_key(*, refresh_share=False):
    """Keep packaged builds unchanged; source installs use one factory key file."""
    if refresh_share:
        shared = _read_key(share_key_file())
        if shared:
            _cache_key(shared)
        return shared
    explicit = os.environ.get("AUTOMATIC_PRINT_YDWX_KEY", "").strip()
    packaged = gateway_client_key()
    if explicit or packaged:
        return explicit or packaged
    cached = _read_key(cache_key_file())
    if cached:
        return cached
    shared = _read_key(share_key_file())
    if shared:
        _cache_key(shared)
        return shared
    raise RuntimeError(
        "亿点万象共享服务密钥不可用：本机缓存尚未建立，"
        f"且无法读取工厂共享盘 {share_key_file()}。"
        "请确认共享盘连接与该文件的读取权限；已有本机缓存的电脑可在共享盘断开时继续使用。"
    )
