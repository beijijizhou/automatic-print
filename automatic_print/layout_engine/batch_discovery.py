"""Read each directory once, keeping direct images separate from child batches."""
from pathlib import Path
from os import scandir

from .discovery import SUPPORTED_EXTENSIONS


def scan_batches(root, progress=None, cancellation=None):
    pending, batches, errors, visited = [Path(root)], [], [], 0
    while pending:
        if cancellation:
            cancellation.check()
        folder = pending.pop()
        if progress:
            progress('扫描批次目录', visited, 0, str(folder))
        try:
            images, children = [], []
            with scandir(folder) as entries:
                for entry in entries:
                    if cancellation:
                        cancellation.check()
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name != '切膜机文件':
                            children.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in SUPPORTED_EXTENSIONS:
                        images.append(Path(entry.path))
            pending.extend(sorted(children, reverse=True))
            if images:
                batches.append({'folder': folder, 'relative': folder.relative_to(root),
                                'images': sorted(images), 'image_count': len(images)})
        except OSError as error:
            errors.append({'folder': str(folder), 'error': str(error)})
            if progress:
                progress('扫描目录失败，继续下一层', visited, 0, f'{folder}：{error}')
        visited += 1
    from .platform_detection import detect_scanned_platform
    return {'batches': batches, 'errors': errors, 'directories': visited,
            'platform':detect_scanned_platform(Path(root),batches)}
