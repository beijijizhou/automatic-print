"""Runtime identity returned by live machine probes."""

from functools import lru_cache
from pathlib import Path
import os
import shutil
import subprocess

from automatic_print import (
    __command_capabilities__, __command_protocol__, __version__,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@lru_cache(maxsize=1)
def source_revision():
    git = shutil.which("git")
    if not git or not (PROJECT_ROOT / ".git").exists():
        return ""
    try:
        result = subprocess.run(
            [git, "rev-parse", "HEAD"], cwd=PROJECT_ROOT, timeout=5,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if os.name == "nt" else 0
            ),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    revision = result.stdout.strip().lower()
    return revision if result.returncode == 0 and len(revision) == 40 else ""


def runtime_manifest():
    return {
        "app_version": __version__,
        "source_revision": source_revision(),
        "command_protocol": __command_protocol__,
        "capabilities": list(__command_capabilities__),
    }
