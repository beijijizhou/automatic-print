from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..automation.batch_naming import (
    MULTI_PIECE_TYPES,
    has_source_prefix,
    load_batch_type,
    prepare_multi_piece_names,
    sort_multi_piece_images,
)
from ..layout import discover_images, generate_layout


def process_local_batches(
    output: Path,
    platform_name: str,
    batch_numbers: list[str],
    batch_types: dict[str, str],
    settings,
    sample_limit: int | None,
    merge_batches: bool,
    progress,
) -> dict:
    platform_root = output / platform_name
    folders = _batch_folders(platform_root, batch_numbers)
    if not folders:
        raise RuntimeError(
            f"没有找到 {platform_name} 已解压的生产批次文件夹。"
        )
    if sample_limit and not merge_batches:
        folders = folders[:1]
    prepared = [
        (
            folder,
            _prepare_images(
                folder,
                batch_types.get(folder.name) or load_batch_type(folder),
                sample_limit,
                progress,
            ),
        )
        for folder in folders
    ]
    output_name = "TEST_SAMPLE" if sample_limit else "PROCESSED"
    destination_root = platform_root / output_name
    if merge_batches:
        completed = _render_merged(
            prepared, destination_root, settings, progress
        )
    else:
        completed = _render_separately(
            prepared, destination_root, settings, progress
        )
    return {
        "type": "processed",
        "platform": platform_name,
        "batches": completed,
        "merged_batches": [folder.name for folder, _images in prepared]
        if merge_batches
        else [],
        "test": bool(sample_limit),
        "output_folder": str(destination_root),
    }


def _batch_folders(root: Path, selected: list[str]) -> list[Path]:
    folders = [
        folder
        for folder in root.rglob("*")
        if folder.is_dir()
        and len(folder.name) == 12
        and folder.name.isdigit()
        and not {"PROCESSED", "TEST_SAMPLE"}.intersection(folder.parts)
        and discover_images(folder)
    ]
    if not selected:
        return sorted(folders)
    positions = {number: index for index, number in enumerate(selected)}
    return sorted(
        (folder for folder in folders if folder.name in positions),
        key=lambda folder: positions[folder.name],
    )


def _prepare_images(folder, batch_type, sample_limit, progress):
    if not batch_type and has_source_prefix(folder):
        raise RuntimeError(
            f"批次 {folder.name} 包含平台来源前缀，但无法确认"
            "是单件还是多件。为避免多件订单被打散，已停止排版。"
        )
    if batch_type in MULTI_PIECE_TYPES:
        progress(f"{folder.name} · 正在整理{batch_type}图片名称")
        renamed = prepare_multi_piece_names(folder, batch_type)
        progress(
            f"{folder.name} · 图片名称整理完成，"
            f"删除 {renamed} 个平台来源前缀"
        )
    images = discover_images(folder)
    if batch_type in MULTI_PIECE_TYPES:
        images = sort_multi_piece_images(images)
    return images[:sample_limit] if sample_limit else images


def _render_merged(prepared, destination_root, settings, progress):
    images = [
        image for _folder, folder_images in prepared for image in folder_images
    ]
    codes = [folder.name for folder, _images in prepared]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = destination_root / f"MERGED_{stamp}_{len(codes)}批次"
    progress(f"[1/1] 正在合并 {len(codes)} 个批次、{len(images)} 张图片")
    result = generate_layout(
        images,
        destination,
        settings,
        lambda stage, current, total, name: progress(
            f"合并批次 · {stage} {current}/{total}"
        )
        if current == total or current % 50 == 0
        else None,
    )
    return [("合并批次", result)]


def _render_separately(prepared, destination_root, settings, progress):
    completed = []
    total = len(prepared)
    for index, (folder, images) in enumerate(prepared, start=1):
        progress(
            f"[{index}/{total}] {folder.name}：正在排版 {len(images)} 张图片"
        )
        result = generate_layout(
            images,
            destination_root / folder.name,
            settings,
            lambda stage, current, count, name: progress(
                f"{folder.name} · {stage} {current}/{count}"
            )
            if current == count or current % 50 == 0
            else None,
        )
        completed.append((folder.name, result))
    return completed
