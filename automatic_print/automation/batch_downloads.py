from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from zipfile import ZipFile


ProgressCallback = Callable[[str], None]
PRODUCTION_IMAGE_EXTENSIONS = {
    ".png", ".tif", ".tiff", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp"
}


def download_production_images(
    page,
    batch_groups: Mapping[str, Sequence[str]],
    output_root: Path,
    progress: ProgressCallback | None = None,
    extract: bool = True,
) -> list[Path]:
    """Download only the production-image export for explicit batch numbers."""
    output_root.mkdir(parents=True, exist_ok=True)
    rows = None
    saved: list[Path] = []
    archives_to_extract: list[Path] = []

    for group_name, batch_numbers in batch_groups.items():
        group_dir = output_root / group_name
        group_dir.mkdir(parents=True, exist_ok=True)
        for batch_number in batch_numbers:
            extracted_folder = group_dir / batch_number
            local_images = (
                [
                    path
                    for path in extracted_folder.rglob("*")
                    if path.is_file()
                    and path.suffix.lower() in PRODUCTION_IMAGE_EXTENSIONS
                ]
                if extracted_folder.is_dir()
                else []
            )
            if local_images:
                if progress:
                    progress(
                        f"本地已有 {len(local_images)} 张图片，跳过下载 "
                        f"{group_name} / {batch_number}"
                    )
                saved.append(extracted_folder)
                continue
            existing = [
                path
                for path in group_dir.glob(f"{batch_number}_*")
                if path.is_file() and path.suffix.lower() == ".zip"
            ]
            if len(existing) == 1:
                if progress:
                    progress(
                        f"发现本地 ZIP，跳过下载 "
                        f"{group_name} / {batch_number}"
                    )
                saved.append(existing[0])
                archives_to_extract.append(existing[0])
                continue
            if len(existing) > 1:
                raise RuntimeError(f"生产批次 {batch_number} 存在多个下载文件。")
            if rows is None:
                rows = page.locator("tbody tr")
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
            archives_to_extract.append(destination)

    if extract:
        extract_production_archives(archives_to_extract, progress)
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
