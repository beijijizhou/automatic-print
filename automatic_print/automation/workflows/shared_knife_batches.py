"""Generate selected batches together, promoting only verified fixed-knife outputs."""
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ...layout_engine import generate_layout
from .shared_knife import continuous_print_eligibility, locked_knife_settings


def _layout_progress(progress, batch):
    def report(stage, current, total, _name):
        if not total or current == total or current % 50 == 0:
            progress(f'{batch} · {stage} {current}/{total}' if total else f'{batch} · {stage}')
    return report


def _promote_files(staged, target, result):
    """Move only this batch's verified output files; undo a partial promotion."""
    names = result.get('files') or [result['filename']]
    moves = [(staged / name, target / name) for name in names]
    for source, destination in moves:
        if not source.is_file() or destination.exists():
            raise OSError(f'输出文件缺失或目标已存在：{source} -> {destination}')
    target.mkdir(parents=True, exist_ok=True)
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


def render_shared_knife_batches(platform_root, platform_name, prepared, settings, progress):
    """Keep batches separate while all unattended files inherit one knife setting."""
    settings = replace(settings, output_format='png')  # RIIN file import accepts PNG only.
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
                                         _layout_progress(progress, batch), batch_name=batch)
                eligible, fallback_reason = continuous_print_eligibility(result, locked)
                if not eligible and not fallback_reason.startswith('实际纵刀位'):
                    raise ValueError(f'原策略输出未通过安全复核：{fallback_reason}')
                category = '常规' if eligible else '旋转'
                reason += f'；原策略复核：{fallback_reason}'
                target = root / category / run_name
                _promote_files(fallback_stage, target, result)
            except Exception as fallback_error:
                errors.append({'batch': batch, 'error': str(fallback_error),
                               'fixed_error': reason})
                progress(f'{batch}：原排版策略也失败，保留诊断并继续下一批 · {fallback_error}')
                continue
        else:
            if not eligible and not reason.startswith('实际纵刀位'):
                errors.append({'batch': batch, 'error': f'固定刀位输出未通过安全复核：{reason}'})
                progress(f'{batch}：安全复核未通过，输出保留在待检验区，不生成PRN · {reason}')
                continue
            category = '常规' if eligible else '旋转'
            target = root / category / run_name
            try:
                _promote_files(staged, target, result)
            except OSError as error:
                errors.append({'batch': batch, 'error': f'输出归档失败：{error}'})
                progress(f'{batch}：输出仍保留在待检验区，继续下一批 · {error}')
                continue
        routes[batch] = {'folder': str(Path(category) / run_name),
                         'unattended': eligible, 'reason': reason}
        completed.append((batch, result))
        progress(f'[{index}/{total}] {batch}：已归入{category} · {reason}')
    return {'type': 'processed', 'platform': platform_name, 'batches': completed,
            'batch_routes': routes, 'layout_errors': errors, 'merged_batches': [],
            'test': False, 'preview_only': False, 'shared_knife_mm': locked.cutter_knife_mm,
            'output_folder': str(root)}
