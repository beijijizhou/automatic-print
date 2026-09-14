"""Portable output names derived from rendered label text."""
import re


def order_quantity(paths, scope="批次"):
    """Count order identities, not pictures, pieces or front/back faces."""
    from .order_groups import order_key
    keys = {order_key(path) for path in paths}
    unknown = '未识别订单组' in keys
    keys.discard('未识别订单组')
    if unknown:
        return f'{scope}已识别{len(keys)}单 订单待核对' if keys else f'{scope}订单待核对'
    return f'{scope}{len(keys)}单'


def label_output_name(text, batch_name=""):
    if batch_name:
        text = f"{batch_name}_{text}"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if name.lower().endswith(".png"):
        name = name[:-4].rstrip(" .")
    name = name or "排版图片"
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10))
    if name.split(".")[0].upper() in reserved:
        name = "标签_" + name
    while len(name.encode("utf-8")) > 180:
        name = name[:-1]
    return name.rstrip(" .") + ".png"


def batch_directory_name(batch_name, job_id):
    """Initial directory keeps source identity, never an internal job identifier."""
    return label_output_name(batch_name)[:-4]


def finish_output_directory(directory, filename):
    """Name the completed directory after its PNG, preserving old outputs."""
    from pathlib import Path
    name = Path(filename).stem
    target, index = directory.parent/name, 2
    if target == directory:
        return directory
    while target.exists():
        target = directory.parent/f'{name} ({index})'
        index += 1
    return directory.rename(target)


def batch_output_directory(base, batch_name, job_id, relative_parts=()):
    base = base / "切膜机文件"
    for part in relative_parts:
        if part in ('', '.', '..') or '/' in part or '\\' in part:
            raise ValueError('输出目录层级无效')
        base = base / part
    name = batch_directory_name(batch_name, job_id)
    path, index = base / name, 2
    while path.exists():
        path = base / f"{name} ({index})"
        index += 1
    return path


def unused_output_path(directory, filename):
    path = directory / filename
    index = 2
    while path.exists() or path.with_name(path.name+'.未完成').exists():
        path = directory / f"{filename[:-4]} ({index}).png"
        index += 1
    return path
