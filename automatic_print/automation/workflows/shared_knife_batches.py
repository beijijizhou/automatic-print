"""Generate selected batches together, promoting only verified fixed-knife outputs."""
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ...layout_engine import generate_layout
from .shared_knife import (
    actual_knife_signatures, continuous_print_eligibility, locked_knife_settings,
)


def _layout_progress(progress, batch):
    def report(stage, current, total, _name):
        if not total or current == total or current % 50 == 0:
            progress(f'{batch} · {stage} {current}/{total}' if total else f'{batch} · {stage}')
    return report


def _promote_files(staged, destinations):
    """Move only verified files; undo a partial promotion across both folders."""
    moves = [(staged / name, target / name) for name, target in destinations]
    for source, destination in moves:
        if not source.is_file() or destination.exists():
            raise OSError(f'输出文件缺失或目标已存在：{source} -> {destination}')
    for _source, destination in moves:
        destination.parent.mkdir(parents=True, exist_ok=True)
    moved = []
    try:
        for source, destination in moves:
            source.rename(destination)
            moved.append((source, destination))
    except OSError:
        for source, destination in reversed(moved):
            if destination.exists() and not source.exists():
                destination.rename(source)
        raise


def _route_parts(result, locked, root, run_name):
    """Route each independently verified PNG by its actual complete knife signature."""
    parts = result.get('parts') or [result]
    routes, destinations = [], []
    for part in parts:
        eligible, reason = continuous_print_eligibility(part, locked)
        if not eligible and not reason.startswith('实际纵刀位'):
            raise ValueError(f'{part.get("filename", "输出文件")} 未通过安全复核：{reason}')
        signatures = actual_knife_signatures(part)
        if len(signatures) != 1:
            raise ValueError(f'{part.get("filename", "输出文件")} 含不同实际刀位，不能合并打印。')
        category = '常规' if eligible else '旋转'
        folder = root / category / run_name
        routes.append({
            'filename': part['filename'], 'folder': str(Path(category) / run_name),
            'unattended': eligible, 'reason': reason,
            'knife_signature': next(iter(signatures)),
        })
        destinations.append((part['filename'], folder))
    return routes, destinations


def render_shared_knife_batches(platform_root, platform_name, prepared, settings, progress):
    """Keep batches separate while all unattended files inherit one knife setting."""
    # This operator workflow prioritizes unchanged knife setup and fast output,
    # not a second four-film optimization pass.
    settings = replace(settings, output_format='png', compare_film_sizes=False)
    locked = locked_knife_settings(settings)
    token = datetime.now().strftime('%m%d%H%M') + '_' + uuid4().hex[:6]
    root = Path(platform_root) / '切膜机文件'
    run_name = f'共刀_{token}'
    for category in ('常规', '旋转'):
        (root / category).mkdir(parents=True, exist_ok=True)
    staged = root / '旋转' / run_name / '待检验'
    staged.mkdir(parents=True, exist_ok=False)
    completed, routes, errors = [], {}, []
    total = len(prepared)
    progress(f'已读取 {total} 个批次；共用固定刀位 {locked.cutter_knife_mm:g} 毫米')
    for index, (folder, images) in enumerate(prepared, 1):
        batch = folder.name
        progress(f'[{index}/{total}] {batch}：固定刀位排版 {len(images)} 张')
        try:
            result = generate_layout(images, staged, locked,
                                     _layout_progress(progress, batch), batch_name=batch)
            eligible, reason = continuous_print_eligibility(result, locked)
            shrink = [row for row in result.get('analysis', {}).get('width_adjustments', ())
                      if row[1].startswith('共刀并排等比缩小：')]
            if shrink:
                reason += f'；{len(shrink)} 张已等比缩小，原/采用尺寸见排版报告'
        except Exception as error:
            eligible, reason = False, f'固定刀位无法完成：{error}'
            progress(f'{batch}：{reason}；改用原排版策略，复核实际刀位')
            try:
                fallback_stage = root / '旋转' / run_name / f'待检验_{index}'
                fallback_stage.mkdir(parents=True, exist_ok=False)
                result = generate_layout(images, fallback_stage, settings,
                                         _layout_progress(progress, batch), batch_name=batch,
                                         split_by_knife=True)
                part_routes, destinations = _route_parts(result, locked, root, run_name)
                _promote_files(fallback_stage, destinations)
                reason += ('；原策略按实际刀位分文件复核：' + '；'.join(
                    dict.fromkeys(route['reason'] for route in part_routes)))
            except Exception as fallback_error:
                errors.append({'batch': batch, 'error': str(fallback_error),
                               'fixed_error': reason})
                progress(f'{batch}：原排版策略也失败，保留诊断并继续下一批 · {fallback_error}')
                continue
        else:
            try:
                part_routes, destinations = _route_parts(result, locked, root, run_name)
                _promote_files(staged, destinations)
            except (OSError, ValueError) as error:
                errors.append({'batch': batch, 'error': f'输出归档失败：{error}'})
                progress(f'{batch}：输出仍保留在待检验区，继续下一批 · {error}')
                continue
        categories = {route['folder'] for route in part_routes}
        routes[batch] = {'folder': next(iter(categories)) if len(categories) == 1 else '',
                         'unattended': all(route['unattended'] for route in part_routes),
                         'reason': reason, 'parts': part_routes}
        completed.append((batch, result))
        normal = sum(route['unattended'] for route in part_routes)
        progress(f'[{index}/{total}] {batch}：固定刀位 {normal} 文件，需换刀 '
                 f'{len(part_routes)-normal} 文件 · {reason}')
    return {'type': 'processed', 'platform': platform_name, 'batches': completed,
            'batch_routes': routes, 'layout_errors': errors, 'merged_batches': [],
            'test': False, 'preview_only': False, 'shared_knife_mm': locked.cutter_knife_mm,
            'output_folder': str(root)}
