from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..layout import discover_images


@dataclass(frozen=True)
class LocalBatch:
    platform_name: str
    batch_number: str
    folder: Path
    image_count: int
    modified_at: str


def discover_local_batches(
    output_root: Path, platform_name: str
) -> list[LocalBatch]:
    platform_root = output_root / platform_name
    if not platform_root.is_dir():
        return []
    batches = []
    for folder in platform_root.rglob("*"):
        if (
            not folder.is_dir()
            or len(folder.name) != 12
            or not folder.name.isdigit()
            or {"PROCESSED", "TEST_SAMPLE"}.intersection(folder.parts)
        ):
            continue
        images = discover_images(folder)
        if not images:
            continue
        modified = max(path.stat().st_mtime for path in images)
        batches.append(
            LocalBatch(
                platform_name,
                folder.name,
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
