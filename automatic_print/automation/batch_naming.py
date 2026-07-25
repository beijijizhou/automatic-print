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
    metadata_path = folder / METADATA_NAME
    existed = metadata_path.is_file()
    data = _load_metadata(folder)
    data["batch_type"] = batch_type
    if batch_type in MULTI_PIECE_TYPES and "names_normalized" not in data:
        if existed and not has_source_prefix(folder):
            data["names_normalized"] = True
        else:
            data["naming_pending"] = True
    _save_metadata(folder, data)


def load_batch_type(folder: Path) -> str:
    return str(_load_metadata(folder).get("batch_type", ""))


def prepare_multi_piece_names(folder: Path, batch_type: str) -> int:
    if batch_type not in MULTI_PIECE_TYPES:
        return 0
    metadata = _load_metadata(folder)
    if metadata.get("names_normalized"):
        return 0
    generic = bool(metadata.get("naming_pending"))
    plan = [
        (
            source,
            source.with_name(_without_source_prefix(source.name, generic)),
        )
        for source in discover_images(folder)
        if _has_removable_prefix(source.name, generic)
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
    metadata.update(names_normalized=True, naming_pending=False)
    _save_metadata(folder, metadata)
    return len(renamed)


def has_source_prefix(folder: Path) -> bool:
    return any(
        SOURCE_PREFIX.match(image.name) for image in discover_images(folder)
    )


def _has_removable_prefix(name: str, generic: bool) -> bool:
    return ("-" in name) if generic else bool(SOURCE_PREFIX.match(name))


def _without_source_prefix(name: str, generic: bool) -> str:
    if generic:
        return name.split("-", 1)[1]
    return SOURCE_PREFIX.sub("", name, count=1)


def _load_metadata(folder: Path) -> dict:
    path = folder / METADATA_NAME
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_metadata(folder: Path, data: dict) -> None:
    (folder / METADATA_NAME).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
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
