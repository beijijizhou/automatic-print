"""Output compatibility, size labels, and one copyable production report."""
from dataclasses import replace

from automatic_print.layout_engine.intake.metadata.source_metadata import source_size, size_key


def enforce_output_compatibility(settings, progress=None):
    """RIIN cutter workflows use PNG; safely downgrade a stale TIFF choice."""
    if settings.cutter_mode == 'free' or settings.output_format.lower() != 'tiff':
        return settings, None
    message = (
        'RIIN 切膜链路不支持 TIFF：原值 TIFF，已采用 PNG；'
        '仅改变输出容器，不改变排版坐标、图片尺寸或刀位。'
    )
    if progress:
        progress('输出格式确认', 1, 1, message)
    return replace(settings, output_format='png'), {
        'original': 'TIFF',
        'adopted': 'PNG',
        'impact': '仅改变输出容器；排版坐标、图片尺寸和刀位不变',
        'edit_path': '打印参数 → 输出图片格式',
        'message': message,
    }


def size_range_label(paths):
    sequence = []
    for path in paths:
        size = source_size(path)
        if not sequence or sequence[-1] != size:
            sequence.append(size)
    sizes = sorted(set(sequence), key=size_key)
    known = [size for size in sizes if size != '未识别尺码']
    runs = []
    for size in known:
        rank = size_key(size)[0]
        if sequence == known and runs and rank < 1000 and size_key(runs[-1][-1])[0] == rank-10:
            runs[-1].append(size)
        else:
            runs.append([size])
    label = '+'.join(row[0] if len(row) == 1 else f'{row[0]}-{row[-1]}' for row in runs)
    if '未识别尺码' in sizes and known:
        label += '+待核对尺码'
    return label


def cutting_description(result):
    check = result.get('cut_corridor') or {}
    zones = check.get('zones', [check])
    knife = '；'.join(
        f"{zone.get('name') or '整段'}刀位 {zone['knife_x_px']*25.4/result['output_dpi']:.1f} 毫米"
        for zone in zones if 'knife_x_px' in zone
    )
    sizes = result.get('size_range') or '尺码待核对'
    notices = '；'.join(
        ('批次信息：\n'+record['text']) if 'text' in record else
        f"{record['kind']}{'' if record['kind'] == '批次结束色块' else '红线'}：距文件顶部 "
        f"{record['y']*25.4/result['output_dpi']:.1f} 毫米"
        for record in result.get('transition_marks', [])
    )
    rotated = any(placement['cut_zone'] == '旋转区' for placement in result['placements'])
    shift = ' · 刀码保持左侧固定基准' if rotated else ''
    changes = (result.get('cut_corridor') or {}).get('knife_change_gaps', [])
    change_text = ''
    if changes:
        rows = []
        for change in changes:
            required = change['required_px'] * 25.4 / result['output_dpi']
            actual = change['actual_px'] * 25.4 / result['output_dpi']
            rows.append(
                f"{change['from_zone']}→{change['to_zone']}："
                f"左侧识别刀码 {actual:.1f} 毫米（要求至少 {required:.1f} 毫米）"
            )
        change_text = '\n换刀与批次结束停止距离：' + '；'.join(rows)
    return (
        f"{result['filename']} · {sizes} · {len(result['placements'])} 张 · "
        f"{knife or '单列 / 自由排版'}{shift}"
        + change_text + (f'\n{notices}' if notices else '')
    )


def cutting_report(result):
    parts = result.get('parts') or [result]
    quality = result.get('dual_quality', {})
    review = quality.get('text', '')
    fallback = result.get('analysis', {}).get('output_format_fallback')
    if fallback:
        review += (
            f"\n输出格式兼容处理：原值 {fallback['original']} → "
            f"采用 {fallback['adopted']}；{fallback['impact']}。"
            f"修改位置：{fallback['edit_path']}。"
        )
    from automatic_print.layout_engine.orders.batch_analysis import distribution_text
    review += '\n'+distribution_text(result.get('analysis', {}))
    from automatic_print.layout_engine.planning.film.film_comparison import comparison_text
    review += '\n'+comparison_text(result.get('analysis', {}).get('film_comparison'))
    from automatic_print.layout_engine.intake.metadata.image_anomalies import anomaly_text
    review += '\n'+anomaly_text(result.get('analysis', {}))
    from automatic_print.layout_engine.labeling.base.header_gap import gap_report
    review += '\n'+gap_report(result.get('analysis', {}).get('header_gap', []))
    from automatic_print.layout_engine.planning.zones.gap_loss import gap_loss_text
    review += '\n'+gap_loss_text(result.get('analysis', {}).get('gap_loss'))
    from automatic_print.automation.api.s2b.metadata.prepare import (
        metadata_summary_text, metadata_warning_text,
    )
    metadata_records = result.get('analysis', {}).get('s2b_metadata', ())
    metadata_summary = metadata_summary_text(metadata_records)
    if metadata_summary:
        review += '\nS2B批次信息：\n'+metadata_summary
    metadata_warning = metadata_warning_text(
        metadata_records)
    if metadata_warning:
        review += '\nS2B订单颜色提示：\n'+metadata_warning
    from .output_file_info import result_file_report
    review += '\n'+result_file_report(result)
    comparison = result.get('analysis', {}).get('rotation_comparison')
    if comparison:
        normal = comparison['normal_m']
        normal_text = f'{normal:.3f} 米' if normal is not None else '无安全方案'
        saving = comparison['saved_m']
        saved_text = f'{saving:.3f} 米' if saving is not None else '无法比较'
        strategy = comparison.get('selected_strategy', '旋转区域')
        review += (
            f"\n实际排版策略比较（分段前）：固定刀位不旋转 {normal_text} · "
            f"{strategy} {comparison['rotation_m']:.3f} 米 · 省膜 {saved_text}"
            f" · 实际旋转 {comparison['rotated_images']} 张"
        )
    for item in quality.get('single_images', []):
        footprint = item.get('footprint_mm')
        occupied = f" · 含标签/刀码占位 {footprint:g} 毫米" if footprint is not None else ''
        review += f"\n单排：{item['source']} · 图宽 {item['width_mm']:g} 毫米{occupied} · {item['reason']}"
    return (
        '按文件段号顺序生产，不重新排序。刀位从输出文件最左侧起算，实际膜位置还需加 RIIN 左预留。\n'
        '红色横线表示分段或批次结束，区域之间不加横线；不切入图片。刀码不添加旋转偏移。\n\n'
        + review + '\n\n' + '\n\n'.join(cutting_description(part) for part in parts)
    )
