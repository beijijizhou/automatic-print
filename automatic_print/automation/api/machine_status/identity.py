"""Stable installation identity without exposing Windows account details."""

import os
import platform
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
    configured = os.environ.get("AUTOMATIC_PRINT_MACHINE_NAME", "").strip()
    return configured or platform.node().strip() or "未命名机器"
