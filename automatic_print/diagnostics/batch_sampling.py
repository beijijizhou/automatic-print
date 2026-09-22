"""Select reproducible, complete Haloo source batches for cold-run diagnostics."""

import random
import re
from pathlib import Path

from automatic_print.layout_engine.intake.discovery.batch_discovery import scan_batches


_BATCH_NAME = re.compile(r"\d{12}")
_DATE_NAME = re.compile(r"\d{4}")
_HL_NAMES = frozenset({"HL", "HL 2"})


def haloo_roots(root: Path) -> list[Path]:
    """Locate explicit HL source roots without traversing unrelated platforms."""
    root = Path(root)
    if root.name.upper() in _HL_NAMES:
        return [root]
    children = [item for item in root.iterdir() if item.is_dir()]
    direct = [item for item in children if item.name.upper() in _HL_NAMES]
    if direct:
        return sorted(direct)
    dates = [item for item in children if _DATE_NAME.fullmatch(item.name)]
    return sorted(platform for date in dates for platform in date.iterdir()
                  if platform.is_dir() and platform.name.upper() in _HL_NAMES)


def choose_batches(root: Path, count: int, seed: int, progress=None):
    candidates, scan_errors, directories = [], [], 0
    for platform_root in haloo_roots(root):
        if progress:
            progress("扫描平台", platform_root)
        scan = scan_batches(platform_root)
        directories += scan["directories"]
        scan_errors.extend(scan["errors"])
        candidates.extend(batch for batch in scan["batches"]
                          if _BATCH_NAME.fullmatch(batch["folder"].name)
                          and "排版日志" not in batch["folder"].parts)
    candidates.sort(key=lambda item: str(item["folder"]).casefold())
    if len(candidates) < count:
        raise ValueError(f"DTF 盘只发现 {len(candidates)} 个可读 HL 批次，无法随机抽取 {count} 个")
    return random.Random(seed).sample(candidates, count), {
        "candidate_count": len(candidates), "scanned_directories": directories,
        "scan_errors": scan_errors,
    }
