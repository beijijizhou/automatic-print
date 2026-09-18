"""File-list validation for automated local layout and RIIN handoff."""
from pathlib import Path


def available_prn_path(source):
    folder = Path(source).resolve()
    candidate = folder / f"{folder.name}.prn"
    index = 2
    while candidate.exists():
        candidate = folder / f"{folder.name}-{index}.prn"
        index += 1
    return candidate


def generated_pngs(records):
    files = []
    for record in records:
        output = Path(record['output'])
        result = record['result']
        names = result.get('files') or [result['filename']]
        files.extend((output / name).resolve() for name in names)
    missing = [path for path in files if not path.is_file()]
    if not files or missing:
        raise ValueError(
            '本地排版没有返回可导入的最终PNG。' if not files
            else f'本地排版结果不存在：{missing[0]}')
    if any(path.suffix.lower() != '.png' for path in files):
        raise ValueError('RIIN自动化只接受本地排版生成的PNG。')
    return files


def existing_layout_pngs(source):
    """List existing cutter PNGs without decoding their potentially huge pixels."""
    root = Path(source).resolve(strict=True)
    files = sorted(
        (path.resolve() for path in root.iterdir()
         if path.is_file() and path.suffix.lower() == '.png'), key=str)
    if not files:
        raise ValueError('切膜机文件目录中没有PNG排版成品。')
    return files
