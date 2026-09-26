"""Compact menu summaries parsed from full-test process output."""

import re
import json
from pathlib import Path


def phase_summary(key, output):
    text = str(output or "")
    if key == "automated":
        passed = _last_number(text, r"(\d+) passed")
        failed = _last_number(text, r"(\d+) failed")
        errors = _last_number(text, r"(\d+) error")
        parts = [f"自动 {passed}项"] if passed is not None else ["自动结果见日志"]
        if failed:
            parts.append(f"失败{failed}")
        if errors:
            parts.append(f"错误{errors}")
        return " ".join(parts)
    if key == "real_batches":
        passed = _last_number(text, r'"passed"\s*:\s*(\d+)')
        total = _last_number(text, r'"total"\s*:\s*(\d+)')
        if passed is not None and total is not None:
            return f"真实批次 {passed}/{total}"
    return "结果见日志"


def _last_number(text, pattern):
    values = re.findall(pattern, text)
    return int(values[-1]) if values else None


def real_batch_file_summary(path, fallback="结果见日志"):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return f"真实批次 {int(data['passed'])}/{int(data['total'])}"
    except (OSError, ValueError, KeyError, TypeError):
        return fallback
