"""Shared restricted client key for Supabase factory gateway functions."""

import os
import tempfile
from pathlib import Path


DEFAULT_SHARE_KEY_FILE = Path(r"\\192.168.11.28\dtf\.automatic-print\ydwx-gateway.key")


def gateway_client_key():
    packaged_key = ""
    try:
        from .s2b.deployment import S2B_BATCH_INFO_KEY
        packaged_key = str(S2B_BATCH_INFO_KEY).strip()
    except ImportError:
        pass
    return os.environ.get("AUTOMATIC_PRINT_S2B_BATCH_INFO_KEY", "").strip() or packaged_key


def shared_client_key(*, refresh_share=False, packaged_key=None):
    """Use a packaged key or the factory share cached per Windows user."""
    if refresh_share:
        shared = _read_key(share_key_file())
        if shared:
            _cache_key(shared)
        return shared
    explicit = os.environ.get("AUTOMATIC_PRINT_YDWX_KEY", "").strip()
    packaged = gateway_client_key() if packaged_key is None else str(packaged_key).strip()
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
        "工厂共享服务密钥不可用：本机缓存尚未建立，"
        f"且无法读取工厂共享盘 {share_key_file()}。"
        "请确认共享盘连接与该文件的读取权限；已有缓存的电脑可离线继续使用。"
    )


def share_key_file():
    override = os.environ.get("AUTOMATIC_PRINT_YDWX_SHARE_KEY_FILE", "").strip()
    return Path(override) if override else DEFAULT_SHARE_KEY_FILE


def cache_key_file():
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "AutomaticPrint" / "credentials" / "ydwx-gateway.key"
    return Path.home() / ".automatic-print" / "credentials" / "ydwx-gateway.key"


def cached_client_key_available():
    """Report whether the current Windows user has a valid local key."""
    return bool(_read_key(cache_key_file()))


def store_local_client_key(value):
    """Validate and atomically store a manually supplied restricted key."""
    value = str(value or "").strip()
    if len(value) < 32 or "\n" in value or "\r" in value:
        raise ValueError("工厂服务密钥格式不正确；请粘贴完整的单行密钥。")
    target = cache_key_file()
    temporary = None
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".gateway-", dir=target.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass
    return target


def _read_key(path):
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
    return value if len(value) >= 32 and "\n" not in value else ""


def _cache_key(value):
    try:
        store_local_client_key(value)
    except OSError:
        return
