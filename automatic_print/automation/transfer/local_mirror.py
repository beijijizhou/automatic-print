"""Safely reuse downloaded production images instead of decoding an SMB copy."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import os

from ...layout_engine.intake.discovery.discovery import SUPPORTED_EXTENSIONS


@dataclass(frozen=True)
class LocalMirror:
    images: tuple[Path, ...]
    aliases: dict[str, str]
    used: bool
    detail: str


def prefer_downloaded_batch(images, source, download_root, platform_name):
    """Return an exact local filename/size mirror, or the untouched sources."""
    originals = tuple(Path(path) for path in images)
    fallback = LocalMirror(originals, {}, False, '')
    root = Path(download_root) if download_root else None
    source = Path(source)
    if not originals or root is None or not platform_name or not is_remote_path(source):
        return fallback
    batch = source.name
    candidate = root / platform_name / 'BATCHES' / batch
    if not candidate.is_dir():
        return fallback
    local = sorted(
        path for path in candidate.rglob('*')
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if len(local) != len(originals):
        return fallback
    try:
        local_rows = _file_rows(local)
        remote_rows = _file_rows(originals)
    except OSError:
        return fallback
    by_key = defaultdict(list)
    for path, size in local_rows:
        by_key[(path.name.casefold(), size)].append(path)
    selected = []
    for path, size in remote_rows:
        matches = by_key[(path.name.casefold(), size)]
        if len(matches) != 1:
            return fallback
        selected.append(matches[0])
    if len(set(selected)) != len(selected):
        return fallback
    aliases = {str(local_path.resolve()): str(remote_path.resolve())
               for remote_path, local_path in zip(originals, selected, strict=True)}
    total = sum(size for _path, size in remote_rows)
    detail = (f'已核对{len(selected)}张、{total / 1_000_000:.2f} MB；'
              '后续尺寸、标签、刀码和合成使用本地下载副本')
    return LocalMirror(tuple(selected), aliases, True, detail)


def _file_rows(paths):
    workers = max(1, min(8, len(paths)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='mirror-stat') as pool:
        sizes = list(pool.map(lambda path: path.stat().st_size, paths))
    return tuple(zip(paths, sizes, strict=True))


def is_remote_path(path):
    text = str(path)
    if text.startswith(('\\\\', '//')):
        return True
    if os.name != 'nt':
        return False
    drive = Path(path).drive
    if not drive:
        return False
    try:
        from ctypes import windll
        return windll.kernel32.GetDriveTypeW(drive + '\\') == 4
    except (AttributeError, OSError):
        return False
