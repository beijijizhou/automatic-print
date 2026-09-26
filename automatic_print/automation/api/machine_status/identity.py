"""Stable installation identity without exposing Windows account details."""

import logging
import os
import re
import tempfile
from pathlib import Path
from uuid import UUID, uuid4


def identity_file():
    root = os.environ.get("LOCALAPPDATA")
    base = Path(root) if root else Path.home() / ".automatic-print"
    return base / "AutomaticPrint" / "machine-id" if root else base / "machine-id"


def machine_name_file():
    return identity_file().with_name("machine-name")


def machine_slot_file():
    """V2 identity store unknown to legacy settings and background processes."""
    return identity_file().with_name("machine-slot-v2")


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
    return bound_machine_number() or "未设置机器号"


def bound_machine_number():
    try:
        value = machine_slot_file().read_text(encoding="utf-8").strip().upper()
        if re.fullmatch(r"M(?:[1-9]|1[01])", value):
            return value
    except (OSError, UnicodeError):
        pass
    return ""


def saved_machine_number():
    """Read the M1-M11 value saved by the desktop app without importing Qt."""
    try:
        value = machine_name_file().read_text(encoding="utf-8").strip().upper()
        if re.fullmatch(r"M(?:[1-9]|1[01])", value):
            return value
    except (OSError, UnicodeError):
        pass
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


def bind_machine_slot(value):
    """Bind this agent only after an explicit user machine-slot selection."""
    normalized = str(value or "").strip().upper()
    if not re.fullmatch(r"M(?:[1-9]|1[01])", normalized):
        raise ValueError("机器号必须是 M1-M11。")
    _write_machine_number(machine_slot_file(), normalized)
    return normalized


def _write_machine_number(target, normalized):
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".machine-name-", dir=target.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(normalized)
        os.replace(temporary, target)
    except OSError as error:
        logging.getLogger("automatic-print.machine-identity").warning(
            "Unable to persist machine number: %s", error,
        )
    finally:
        if temporary:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass
