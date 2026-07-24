from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from zipfile import ZipFile


ProgressCallback = Callable[[str], None]


def download_production_images(
    page,
    batch_groups: Mapping[str, Sequence[str]],
    output_root: Path,
    progress: ProgressCallback | None = None,
    extract: bool = True,
) -> list[Path]:
    """Download only the production-image export for explicit batch numbers."""
    output_root.mkdir(parents=True, exist_ok=True)
    rows = page.locator("tbody tr")
    saved: list[Path] = []

    for group_name, batch_numbers in batch_groups.items():
        group_dir = output_root / group_name
        group_dir.mkdir(parents=True, exist_ok=True)
        for batch_number in batch_numbers:
            existing = list(group_dir.glob(f"{batch_number}_*"))
            if len(existing) == 1:
                if progress:
                    progress(f"已存在，跳过 {group_name} / {batch_number}")
                saved.append(existing[0])
                continue
            if len(existing) > 1:
                raise RuntimeError(f"生产批次 {batch_number} 存在多个下载文件。")
            matching_rows = rows.filter(has_text=batch_number)
            if matching_rows.count() != 1:
                raise RuntimeError(f"无法唯一定位生产批次 {batch_number}。")
            row = matching_rows.first
            row_text = row.inner_text()
            if "生成成功" not in row_text:
                raise RuntimeError(f"生产批次 {batch_number} 的图片尚未生成成功。")

            downloads = row.get_by_text("下载", exact=True)
            if downloads.count() != 3:
                raise RuntimeError(
                    f"生产批次 {batch_number} 的三个下载入口不完整。"
                )
            if progress:
                progress(f"正在下载 {group_name} / {batch_number}")
            with page.expect_download(timeout=120_000) as download_info:
                downloads.nth(2).click()
            download = download_info.value
            suggested = download.suggested_filename or "production-images.zip"
            destination = group_dir / f"{batch_number}_{suggested}"
            download.save_as(destination)
            saved.append(destination)

    if extract:
        extract_production_archives(saved, progress)
    return saved


def extract_production_archives(
    archives: Sequence[Path],
    progress: ProgressCallback | None = None,
) -> list[Path]:
    extracted: list[Path] = []
    for archive in archives:
        batch_number = archive.name.split("_", 1)[0]
        destination = archive.parent / batch_number
        destination.mkdir(parents=True, exist_ok=True)
        if progress:
            progress(f"正在解压 {archive.parent.name} / {batch_number}")
        with ZipFile(archive) as bundle:
            root = destination.resolve()
            for member in bundle.infolist():
                target = (destination / member.filename).resolve()
                if target != root and root not in target.parents:
                    raise RuntimeError(f"压缩包包含不安全路径：{member.filename}")
            bundle.extractall(destination)
        extracted.append(destination)
    return extracted
