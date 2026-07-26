from __future__ import annotations

import sys
from pathlib import Path


def asset_path(name: str) -> Path:
    packaged_root = getattr(sys, "_MEIPASS", None)
    root = Path(packaged_root) if packaged_root else Path(__file__).parents[1]
    return root / "assets" / name
