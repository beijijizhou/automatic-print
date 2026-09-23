from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ...layout_engine import discover_images


@dataclass(frozen=True)
class LocalBatch:
    platform_name: str
    batch_number: str
    folder: Path
    image_count: int
    modified_at: str


def batch_number_from_folder(folder: Path) -> str:
    """Return the production batch code represented by an archive folder."""
    name = folder.name
    if name.startswith("AS2B_"):
        for part in name.split("_")[1:]:
            if len(part) == 12 and part.isalnum():
                return part
    return name


def discover_batch_folders(platform_root: Path) -> list[Path]:
    """Keep an archive's outer batch folder once, including its nested images."""
    excluded = {'PROCESSED', 'TEST_SAMPLE', 'PREVIEW', '切膜机文件'}
    standard_root = platform_root / "BATCHES"
    standard = (
        [folder for folder in standard_root.iterdir() if folder.is_dir()]
        if standard_root.is_dir()
        else []
    )
    legacy = [
        folder for folder in platform_root.rglob('*')
        if folder.is_dir()
        and len(folder.name) == 12
        and folder.name.isalnum()
        and not excluded.intersection(folder.parts)
    ]
    folders = list(dict.fromkeys((*standard, *legacy)))
    candidates = set(folders)
    return [folder for folder in folders
            if not any(parent in candidates and parent.name == folder.name
                       for parent in folder.parents)
            and discover_images(folder)]


def discover_local_batches(
    output_root: Path, platform_name: str
) -> list[LocalBatch]:
    platform_root = output_root / platform_name
    if not platform_root.is_dir():
        return []
    batches = []
    for folder in discover_batch_folders(platform_root):
        images = discover_images(folder)
        if not images:
            continue
        modified = max(path.stat().st_mtime for path in images)
        batches.append(
            LocalBatch(
                platform_name,
                batch_number_from_folder(folder),
                folder,
                len(images),
                datetime.fromtimestamp(modified).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            )
        )
    return sorted(
        batches, key=lambda batch: batch.modified_at, reverse=True
    )
