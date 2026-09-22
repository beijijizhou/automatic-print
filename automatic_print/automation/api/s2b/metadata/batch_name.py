"""Parse stable S2B metadata from the right side of a batch folder name."""
from dataclasses import dataclass
from pathlib import Path
import re


S2B_BATCH = re.compile(
    r"^(?P<prefix>.+)_(?P<count>\d+)_"
    r"(?P<batch>[A-Z0-9]{12})_(?P<date>\d{8})_"
    r"(?P<time>\d{6})_(?P<suffix>[A-Za-z0-9]+)$"
)
S2B_BATCH_WITHOUT_COUNT = re.compile(
    r"^(?P<prefix>.+)_(?P<batch>[A-Z0-9]{12})_"
    r"(?P<date>\d{8})_(?P<time>\d{6})_(?P<suffix>[A-Za-z0-9]+)$"
)
S2B_PARTIAL_BATCH = re.compile(
    r"^(?P<prefix>.*S2B\d+[^\\/]*)_(?P<count>\d+)$", re.I,
)
S2B_SIZE = r"(?:XXS|XS|S|M|L|XL|XXL|[2-9]XL)"
S2B_UNDERSCORE_IMAGE = re.compile(
    r"^(?P<order>[A-Z0-9]+)_(?P<item>\d+)_\d+_"
    r"(?P<views>[12])_\d+_[^_]+_"
    r"(?P<size>XXS|XS|S|M|L|XL|XXL|[2-9]XL)_"
    r"(?P<batch>[A-Z0-9]{12})-\d+_(?P<image>\d+)$",
    re.I,
)
S2B_HYPHEN_IMAGE = re.compile(
    rf"^(?:(?P<prefix_size>{S2B_SIZE})_)?"
    r"(?P<batch>[A-Z0-9]{12})-\d+-(?P<image>\d+)-"
    r"(?P<order>[A-Z0-9]+)-(?P<item>\d+)-\d+-\d+-\d+-"
    rf"[^-]*(?:-(?P<size>{S2B_SIZE}))?$",
    re.I,
)
S2B_SIZE_FOLDER = re.compile(rf"^{S2B_SIZE}$", re.I)


@dataclass(frozen=True)
class S2BBatchFolder:
    path: Path
    prefix: str
    expected_count: int
    batch_number: str
    exported_date: str
    exported_time: str
    suffix: str


@dataclass(frozen=True)
class S2BImageName:
    order_code: str
    order_item_code: str
    batch_number: str
    size: str
    view_count: int
    image_number: int


def parse_s2b_image_name(path):
    path = Path(path)
    match = S2B_UNDERSCORE_IMAGE.fullmatch(path.stem)
    if match:
        return S2BImageName(
            order_code=match["order"],
            order_item_code=f'{match["order"]}-{match["item"]}',
            batch_number=match["batch"].upper(),
            size=match["size"].upper(),
            view_count=int(match["views"]),
            image_number=int(match["image"]),
        )
    match = S2B_HYPHEN_IMAGE.fullmatch(path.stem)
    if not match:
        return None
    if match["size"] and match["prefix_size"] and (
        match["size"].upper() != match["prefix_size"].upper()
    ):
        return None
    size = match["size"] or match["prefix_size"]
    if not size and S2B_SIZE_FOLDER.fullmatch(path.parent.name):
        size = path.parent.name
    if not size:
        return None
    return S2BImageName(
        order_code=match["order"],
        order_item_code=f'{match["order"]}-{match["item"]}',
        batch_number=match["batch"].upper(),
        size=size.upper(),
        view_count=1,
        image_number=int(match["image"]),
    )


def image_batch_number(path):
    """Prefer an unambiguous image batch ID over its containing folder ID."""
    folder = find_s2b_batch_folder(path)
    if not folder:
        return None
    image = parse_s2b_image_name(path)
    return image.batch_number if image else folder.batch_number


def parse_s2b_batch_name(path_or_name):
    path = Path(path_or_name)
    match = S2B_BATCH.fullmatch(path.name)
    if match and "S2B" in match["prefix"].upper():
        count = int(match["count"])
    else:
        match = S2B_BATCH_WITHOUT_COUNT.fullmatch(path.name)
        if not match:
            partial = S2B_PARTIAL_BATCH.fullmatch(path.name)
            if not partial:
                return None
            return S2BBatchFolder(
                path=path, prefix=partial["prefix"],
                expected_count=int(partial["count"]), batch_number="",
                exported_date="", exported_time="", suffix="",
            )
        count = 0
    return S2BBatchFolder(
        path=path,
        prefix=match["prefix"],
        expected_count=count,
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
