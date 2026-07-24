from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile


ProgressCallback = Callable[[str], None]
PRODUCTION_IMAGE_EXTENSIONS = {
    ".png", ".tif", ".tiff", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp"
}
DOWNLOAD_CONCURRENCY = 3


@dataclass(frozen=True)
class RemoteBatch:
    group_name: str
    batch_number: str
    group_dir: Path


def download_production_images(
    page,
    batch_groups: Mapping[str, Sequence[str]],
    output_root: Path,
    progress: ProgressCallback | None = None,
    extract: bool = True,
) -> list[Path]:
    """Reuse local files, then transfer production archives in groups of three."""
    output_root.mkdir(parents=True, exist_ok=True)
    saved, archives, remote = _classify_batches(
        batch_groups, output_root, progress
    )
    for offset in range(0, len(remote), DOWNLOAD_CONCURRENCY):
        group = remote[offset : offset + DOWNLOAD_CONCURRENCY]
        _search_batches(page, [task.batch_number for task in group])
        active = _start_parallel_downloads(page, group, progress)
        for task, download in active:
            suggested = (
                download.suggested_filename or "production-images.zip"
            )
            destination = (
                task.group_dir / f"{task.batch_number}_{suggested}"
            )
            download.save_as(destination)
            saved.append(destination)
            archives.append(destination)
            if progress:
                progress(
                    f"下载完成 {task.group_name} / {task.batch_number}"
                )
    if extract:
        extract_production_archives(archives, progress)
    return saved


def _classify_batches(batch_groups, output_root, progress):
    saved: list[Path] = []
    archives: list[Path] = []
    remote: list[RemoteBatch] = []
    for group_name, batch_numbers in batch_groups.items():
        group_dir = output_root / group_name
        group_dir.mkdir(parents=True, exist_ok=True)
        for number in batch_numbers:
            folder = group_dir / number
            images = (
                [
                    path
                    for path in folder.rglob("*")
                    if path.is_file()
                    and path.suffix.lower() in PRODUCTION_IMAGE_EXTENSIONS
                ]
                if folder.is_dir()
                else []
            )
            if images:
                saved.append(folder)
                if progress:
                    progress(
                        f"本地已有 {len(images)} 张图片，跳过下载 "
                        f"{group_name} / {number}"
                    )
                continue
            zips = [
                path
                for path in group_dir.glob(f"{number}_*.zip")
                if path.is_file()
            ]
            if len(zips) > 1:
                raise RuntimeError(f"生产批次 {number} 存在多个下载文件。")
            if zips:
                saved.append(zips[0])
                archives.append(zips[0])
                if progress:
                    progress(
                        f"发现本地压缩包，跳过下载 {group_name} / {number}"
                    )
                continue
            remote.append(RemoteBatch(group_name, number, group_dir))
    return saved, archives, remote


def _search_batches(page, batch_numbers: list[str]) -> None:
    search = page.locator("input[placeholder*='批次号']")
    button = page.get_by_text("搜 索", exact=True)
    if search.count() != 1 or button.count() != 1:
        return
    search.fill(",".join(batch_numbers))
    endpoint = "/production/v1/production/batch/page"
    with page.expect_response(
        lambda response: endpoint in response.url,
        timeout=30_000,
    ):
        button.click()
    page.locator("tbody tr").filter(
        has_text=batch_numbers[0]
    ).first.wait_for(state="visible", timeout=10_000)


def _start_parallel_downloads(page, tasks, progress):
    active = []
    rows = page.locator("tbody tr")
    for task in tasks:
        matching = rows.filter(has_text=task.batch_number)
        if matching.count() != 1:
            raise RuntimeError(
                f"无法唯一定位生产批次 {task.batch_number}。"
            )
        row = matching.first
        if "生成成功" not in row.inner_text():
            raise RuntimeError(
                f"生产批次 {task.batch_number} 的图片尚未生成成功。"
            )
        links = row.get_by_text("下载", exact=True)
        if links.count() != 3:
            raise RuntimeError(
                f"生产批次 {task.batch_number} 的三个下载入口不完整。"
            )
        if progress:
            progress(
                f"并行下载已启动 {task.group_name} / {task.batch_number}"
            )
        with page.expect_download(timeout=120_000) as info:
            links.nth(2).click()
        active.append((task, info.value))
    return active


def extract_production_archives(
    archives: Sequence[Path],
    progress: ProgressCallback | None = None,
) -> list[Path]:
    extracted = []
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
                    raise RuntimeError(
                        f"压缩包包含不安全路径：{member.filename}"
                    )
            bundle.extractall(destination)
        extracted.append(destination)
    return extracted
