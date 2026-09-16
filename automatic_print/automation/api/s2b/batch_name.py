"""Parse stable S2B batch facts from the right side of a folder name."""
from dataclasses import dataclass
from pathlib import Path
import re


S2B_BATCH = re.compile(
    r"^(?P<prefix>.+)_(?P<count>\d+)_"
    r"(?P<batch>[A-Z0-9]{12})_(?P<date>\d{8})_"
    r"(?P<time>\d{6})_(?P<suffix>[A-Za-z0-9]+)$"
)


@dataclass(frozen=True)
class S2BBatchFolder:
    path: Path
    prefix: str
    expected_count: int
    batch_number: str
    exported_date: str
    exported_time: str
    suffix: str


def parse_s2b_batch_name(path_or_name):
    path = Path(path_or_name)
    match = S2B_BATCH.fullmatch(path.name)
    if not match or "S2B" not in match["prefix"].upper():
        return None
    return S2BBatchFolder(
        path=path,
        prefix=match["prefix"],
        expected_count=int(match["count"]),
        batch_number=match["batch"],
        exported_date=match["date"],
        exported_time=match["time"],
        suffix=match["suffix"],
    )


def find_s2b_batch_folder(path):
    """Find the batch root above either a size folder or an image file."""
    current = Path(path)
    if current.suffix:
        current = current.parent
    for candidate in (current, *current.parents):
        parsed = parse_s2b_batch_name(candidate)
        if parsed:
            return parsed
    return None
