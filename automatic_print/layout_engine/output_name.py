"""Portable output names derived from rendered label text."""
import re
from pathlib import Path


def order_quantity(paths, scope="批次"):
    """Count order identities, not pictures, pieces or front/back faces."""
    from .order_groups import order_key
    keys = {order_key(path) for path in paths}
    unknown = '未识别订单组' in keys
    keys.discard('未识别订单组')
    if unknown:
        return f'{scope}已识别{len(keys)}单 订单待核对' if keys else f'{scope}订单待核对'
    return f'{scope}{len(keys)}单'


def production_quantity(paths, analysis=None, scope="批次"):
    """Format the verified order and physical-piece counts used by output names."""
    orders = order_quantity(paths, scope)
    report = analysis or {}
    known = report.get('orders', ())
    if known and all(order.get('pieces') is not None for order in known):
        return f"{orders} {sum(order['pieces'] for order in known)}件"
    from .order_groups import complete_orders, order_key, pair_identity
    pieces = 0
    for group in complete_orders(paths):
        identities = [pair_identity(path) for path in group]
        if order_key(group[0]) == '未识别订单组' or not all(identities):
            return orders+' 件数待核对'
        pieces += len({identity[0] for identity in identities})
    return f'{orders} {pieces}件'


def label_output_name(text, batch_name="", extension=".png"):
    if batch_name:
        text = f"{batch_name}_{text}"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    name = re.sub(r"\s+", " ", name).strip(" .")
    extension = '.' + extension.lower().lstrip('.')
    for suffix in ('.png', '.tif', '.tiff'):
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)].rstrip(" .")
            break
    name = name or "排版图片"
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10))
    if name.split(".")[0].upper() in reserved:
        name = "标签_" + name
    while len(name.encode("utf-8")) > 180:
        name = name[:-1]
    return name.rstrip(" .") + extension


def batch_directory_name(batch_name, job_id):
    """Initial directory keeps source identity, never an internal job identifier."""
    return Path(label_output_name(batch_name)).stem


def finish_output_files(directory, filename):
    """Move verified PNGs from log staging into the flat print directory."""
    directory = Path(directory)
    staged = directory.parent.name == '.处理中' and directory.parent.parent.name == '排版日志'
    log_root = directory.parent.parent if staged else directory.parent/'排版日志'
    base = log_root.parent if staged else directory.parent
    print_root = base/'切膜机文件'
    print_root.mkdir(parents=True, exist_ok=True)
    names = [filename] if isinstance(filename, str) else list(filename)
    mapping = {}
    for name in names:
        source = directory/name
        if not source.is_file():
            raise ValueError(f'完成输出时找不到排版文件：{source}')
        target = unused_output_path(print_root, name)
        source.replace(target)
        mapping[name] = target.name
    directory.rmdir()
    try:
        directory.parent.rmdir()
    except OSError:
        pass
    return print_root, mapping


def output_log_path(print_root, filename, kind='排版报告'):
    log_root = Path(print_root).parent/'排版日志'
    log_root.mkdir(parents=True, exist_ok=True)
    target = log_root/f'{Path(filename).stem}_{kind}.txt'
    index = 2
    while target.exists():
        target = log_root/f'{Path(filename).stem}_{kind} ({index}).txt'
        index += 1
    return target


def remap_result_files(result, mapping):
    result['filename'] = mapping.get(result['filename'], result['filename'])
    if 'files' in result:
        result['files'] = [mapping.get(name, name) for name in result['files']]
    for part in result.get('parts', ()):
        part['filename'] = mapping.get(part['filename'], part['filename'])
    for placement in result.get('placements', ()):
        name = placement.get('output_filename')
        if name:
            placement['output_filename'] = mapping.get(name, name)
    for mark in result.get('transition_marks', ()):
        name = mark.get('filename')
        if name:
            mark['filename'] = mapping.get(name, name)


def batch_output_directory(base, batch_name, job_id):
    base = base/'排版日志'/'.处理中'
    name = Path(label_output_name(f'{batch_directory_name(batch_name, job_id)}_{job_id}')).stem
    path, index = base / name, 2
    while path.exists():
        path = base / f"{name} ({index})"
        index += 1
    return path


def unused_output_path(directory, filename):
    path = directory / filename
    index = 2
    while path.exists() or path.with_name(path.name+'.未完成').exists():
        original = Path(filename)
        path = directory / f"{original.stem} ({index}){original.suffix}"
        index += 1
    return path
