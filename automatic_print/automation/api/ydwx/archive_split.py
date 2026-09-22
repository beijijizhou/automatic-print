"""Split one downloaded UV ZIP into canvas-sized, recoverable image folders."""

import json
import re
import shutil
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from automatic_print.layout_engine.intake.discovery.discovery import SUPPORTED_EXTENSIONS
from automatic_print.layout_engine.output.output_name import label_output_name
from automatic_print.layout_engine.uv import uv_sheet_capacity

from .archive.verification import verify_existing_split


@dataclass(frozen=True)
class SplitResult:
    root: Path
    material: str
    capacity: int
    image_count: int
    folders: tuple[Path, ...]
    warning: str = ""


def split_uv_archive(archive_path, spec, expected_count=None, progress=None):
    """Preserve the ZIP; publish complete groups only after every image is copied."""
    archive_path = Path(archive_path)
    target = archive_path.with_name(f"{archive_path.stem}-分组")
    capacity = uv_sheet_capacity(spec)
    if target.exists():
        count, folders, warning = verify_existing_split(target, archive_path, spec, capacity)
        return SplitResult(target, spec.label, capacity, count, folders, warning)
    with ZipFile(archive_path) as archive:
        members = _image_members(archive)
        if not members:
            raise ValueError(f"{archive_path.name} 没有可识别的 UV 图片；原 ZIP 已保留。")
        groups, kept_orders = _canvas_groups(members, capacity)
        ignored = len([item for item in archive.infolist() if not item.is_dir()]) - len(members)
        warning_parts = []
        if expected_count is not None and len(members) != expected_count:
            warning_parts.append(
                f"接口稿件数 {expected_count}，ZIP 实际图片 {len(members)}；按 ZIP 实际数量分组"
            )
        if ignored:
            warning_parts.append(f"ZIP 另有 {ignored} 个非图片文件，仅保留在原 ZIP")
        if kept_orders:
            warning_parts.append("同订单编号稿件保持在同一画布组；个别组可能少于满版数量")
        stage = Path(tempfile.mkdtemp(prefix=target.name + ".未完成-", dir=target.parent))
        records = []
        try:
            for group_index, group in enumerate(groups, 1):
                folder = stage / f"{group_index}-{len(group)}"
                folder.mkdir(exist_ok=True)
                for member in group:
                    source_name = PurePosixPath(member.filename.replace("\\", "/")).name
                    safe_name = label_output_name(
                        f"{len(records) + 1:06d}_{Path(source_name).stem}",
                        extension=Path(source_name).suffix,
                    )
                    destination = folder / safe_name
                    with archive.open(member) as source, destination.open("xb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                    if destination.stat().st_size != member.file_size:
                        raise ValueError(f"{member.filename} 解压大小不一致；未发布分组。")
                    records.append({
                        "source": member.filename,
                        "path": f"{folder.name}/{safe_name}",
                        "bytes": member.file_size,
                    })
                if progress:
                    progress(f"{archive_path.parent.name}：已整理 {len(records)}/{len(members)} 张")
            archive_stat = archive_path.stat()
            manifest = {
                "archive": archive_path.name,
                "archive_bytes": archive_stat.st_size,
                "archive_mtime_ns": archive_stat.st_mtime_ns,
                "material": spec.label,
                "capacity": capacity,
                "image_count": len(members),
                "warning": "；".join(warning_parts),
                "files": records,
            }
            (stage / "分组信息.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            stage.rename(target)
        except Exception as error:
            # Only this run's unpublished stage is disposable; the original
            # ZIP remains the recoverable source for a clean retry.
            try:
                shutil.rmtree(stage)
            except OSError as cleanup_error:
                raise OSError(
                    f"{archive_path.name} 分组失败，且临时目录 {stage} 清理失败："
                    f"{cleanup_error}；原 ZIP 已保留。"
                ) from error
            raise
    folders = tuple(target / f"{index}-{len(group)}"
                    for index, group in enumerate(groups, 1))
    return SplitResult(target, spec.label, capacity, len(members), folders,
                       "；".join(warning_parts))


def _image_members(archive):
    members, seen = [], set()
    for member in archive.infolist():
        if member.is_dir():
            continue
        normalized = member.filename.replace("\\", "/")
        path = PurePosixPath(normalized)
        if (not path.parts or path.is_absolute() or ".." in path.parts
                or ":" in path.parts[0]):
            raise ValueError(f"ZIP 包含不安全路径：{member.filename}")
        if (member.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError(f"ZIP 包含符号链接：{member.filename}")
        if path.parts[0] == "__MACOSX" or path.name.startswith("._"):
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            canonical = str(path)
            if canonical in seen:
                raise ValueError(f"ZIP 包含重复图片路径：{member.filename}")
            seen.add(canonical)
            members.append(member)
    return members


def _canvas_groups(members, capacity):
    """Keep repeated SDS order IDs together; never split a known order at a boundary."""
    orders = OrderedDict()
    for index, member in enumerate(members):
        name = PurePosixPath(member.filename.replace("\\", "/")).name
        match = re.match(r"^(\d{12,})_", name)
        key = match.group(1) if match else f"single:{index}"
        orders.setdefault(key, []).append(member)
    result, current = [], []
    for key, unit in orders.items():
        if len(unit) > capacity:
            raise ValueError(
                f"订单编号 {key} 有 {len(unit)} 张，超过单画布 {capacity} 张；"
                "原 ZIP 已保留，请人工决定拆分方式。"
            )
        if current and len(current) + len(unit) > capacity:
            result.append(current)
            current = []
        current.extend(unit)
    if current:
        result.append(current)
    return result, any(len(unit) > 1 for unit in orders.values())
