from __future__ import annotations

import json
import re
from pathlib import Path

from ..layout import discover_images


MULTI_PIECE_TYPES = {"单项多件", "多项多件"}
METADATA_NAME = ".automatic-print-batch.json"
SOURCE_PREFIX = re.compile(
    r"^(?:CVC面料\d+|A\d{7})-",
    re.IGNORECASE,
)


def save_batch_type(folder: Path, batch_type: str) -> None:
    if batch_type not in {"单项单件", *MULTI_PIECE_TYPES}:
        return
    (folder / METADATA_NAME).write_text(
        json.dumps({"batch_type": batch_type}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_batch_type(folder: Path) -> str:
    metadata = folder / METADATA_NAME
    if not metadata.is_file():
        return ""
    try:
        return str(
            json.loads(metadata.read_text(encoding="utf-8")).get(
                "batch_type", ""
            )
        )
    except (OSError, ValueError, TypeError):
        return ""


def prepare_multi_piece_names(folder: Path, batch_type: str) -> int:
    if batch_type not in MULTI_PIECE_TYPES:
        return 0
    plan = [
        (
            source,
            source.with_name(SOURCE_PREFIX.sub("", source.name, count=1)),
        )
        for source in discover_images(folder)
        if SOURCE_PREFIX.match(source.name)
    ]
    _validate_rename_plan(plan)
    renamed: list[tuple[Path, Path]] = []
    try:
        for source, target in plan:
            source.rename(target)
            renamed.append((source, target))
    except OSError as error:
        for source, target in reversed(renamed):
            if target.exists() and not source.exists():
                target.rename(source)
        raise RuntimeError(f"整理多件图片名称失败，已停止：{error}") from error
    return len(renamed)


def has_source_prefix(folder: Path) -> bool:
    return any(
        SOURCE_PREFIX.match(image.name) for image in discover_images(folder)
    )


def _validate_rename_plan(plan: list[tuple[Path, Path]]) -> None:
    source_keys = {str(source).casefold() for source, _target in plan}
    target_keys: set[str] = set()
    for source, target in plan:
        if not target.name:
            raise RuntimeError(f"图片名称删除前缀后为空：{source.name}")
        key = str(target).casefold()
        if key in target_keys:
            raise RuntimeError(
                f"整理多件图片名称后发生重名，已停止：{target.name}"
            )
        target_keys.add(key)
        if target.exists() and key not in source_keys:
            raise RuntimeError(
                f"整理多件图片名称会覆盖已有文件，已停止：{target.name}"
            )
