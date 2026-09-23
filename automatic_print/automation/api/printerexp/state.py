"""Parse PrintExp's current-task files without modifying its installation."""

import re
from dataclasses import dataclass
from pathlib import Path


VALUE = re.compile(r"^\s*([A-Z_]+)\s*=\s*(.*?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class PrintExpSnapshot:
    task_id: str
    progress: float
    task_file: str
    task_folder: str
    modified_at: float


def read_snapshot(installation):
    root = Path(installation)
    info_path = root / "Data" / "PrintInfo.ini"
    values = dict(VALUE.findall(_read_text(info_path)))
    if "PRINT_PROGRESS" not in values:
        return None
    try:
        progress = float(values["PRINT_PROGRESS"])
        modified = info_path.stat().st_mtime
    except (OSError, ValueError):
        return None
    task_path = _task_path(root / "Data" / "printTask.tf")
    task_folder = _value(root / "Data" / "Temp.ini", "TASK_FOLDER")
    task_file = Path(task_path).name if task_path else ""
    if not task_file and task_folder:
        task_file = Path(task_folder.rstrip("\\/ ")).name
    return PrintExpSnapshot(
        task_id=values.get("TASK_GUID", "").strip(),
        progress=max(0, min(100, progress)),
        task_file=task_file,
        task_folder=Path(task_folder.rstrip("\\/ ")).name if task_folder else "",
        modified_at=modified,
    )


def _value(path, name):
    return dict(VALUE.findall(_read_text(path))).get(name, "").strip()


def _read_text(path):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _task_path(path):
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return ""
    strings, current = [], []
    for offset in range(0, len(raw) - 1, 2):
        code = raw[offset] | raw[offset + 1] << 8
        character = chr(code)
        if character.isprintable() and code not in {0xfffe, 0xffff}:
            current.append(character)
        else:
            if len(current) >= 3:
                strings.append("".join(current).strip())
            current = []
    if len(current) >= 3:
        strings.append("".join(current).strip())
    candidates = [value for value in strings if value.casefold().endswith(".prn")]
    paths = [value for value in candidates if re.match(r"^[A-Za-z]:\\", value)]
    return (paths or candidates or [""])[0]
