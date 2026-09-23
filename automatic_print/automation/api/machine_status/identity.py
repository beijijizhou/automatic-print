"""Stable installation identity without exposing Windows account details."""

import os
import re
import tempfile
from pathlib import Path
from uuid import UUID, uuid4


def identity_file():
    root = os.environ.get("LOCALAPPDATA")
    base = Path(root) if root else Path.home() / ".automatic-print"
    return base / "AutomaticPrint" / "machine-id" if root else base / "machine-id"


def machine_id():
    target = identity_file()
    try:
        return str(UUID(target.read_text(encoding="utf-8").strip()))
    except (OSError, UnicodeError, ValueError):
        value = str(uuid4())
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".machine-", dir=target.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
        os.replace(temporary, target)
    except OSError:
        pass
    finally:
        if temporary:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass
    return value


def machine_name():
    saved = saved_machine_number()
    configured = os.environ.get("AUTOMATIC_PRINT_MACHINE_NAME", "").strip().upper()
    configured = configured if re.fullmatch(r"M(?:[1-9]|1[01])", configured) else ""
    return saved or configured or "未设置机器号"


def saved_machine_number():
    """Read the M1-M11 value saved by the desktop app without importing Qt."""
    if os.name != "nt":
        return ""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\AutomaticPrint\AutomaticPrint\layout",
        ) as key:
            value = str(winreg.QueryValueEx(key, "machine_number")[0]).strip().upper()
    except (ImportError, OSError, TypeError, ValueError):
        return ""
    return value if re.fullmatch(r"M(?:[1-9]|1[01])", value) else ""
