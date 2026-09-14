"""Only compress truly consecutive named sizes, never invent missing sizes."""
from .source_metadata import source_size, size_key


def size_range_label(paths):
    sequence = []
    for path in paths:
        size = source_size(path)
        if not sequence or sequence[-1] != size:
            sequence.append(size)
    sizes = sorted(set(sequence), key=size_key)
    known = [s for s in sizes if s != '未识别尺码']
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
    knife = '；'.join(f"{z.get('name') or '整段'}刀位 {z['knife_x_px']*25.4/result['output_dpi']:.1f} 毫米"
                     for z in zones if 'knife_x_px' in z)
    sizes = result.get('size_range') or '尺码待核对'
    notices = '；'.join(('批次信息：\n'+r['text']) if 'text' in r else
                        f"{r['kind']}红线：距文件顶部 {r['y']*25.4/result['output_dpi']:.1f} 毫米"
                        for r in result.get('transition_marks', []))
    rotated = any(p['cut_zone'] == '旋转区' for p in result['placements'])
    shift = ' · 刀码保持左侧固定基准' if rotated else ''
    return (f"{result['filename']} · {sizes} · {len(result['placements'])} 张 · {knife or '单列 / 自由排版'}"
            f"{shift}"+(f'\n{notices}' if notices else ''))


def cutting_report(result):
    parts = result.get('parts') or [result]
    quality = result.get('dual_quality', {})
    review = quality.get('text', '')
    from .film_comparison import comparison_text
    review += '\n'+comparison_text(result.get('analysis', {}).get('film_comparison'))
    from .image_anomalies import anomaly_text
    review += '\n'+anomaly_text(result.get('analysis', {}))
    from .header_gap import gap_report
    review += '\n'+gap_report(result.get('analysis', {}).get('header_gap', []))
    from .measurement_timing import measurement_text
    from .output_file_info import result_file_report
    review += '\n'+result_file_report(result)
    review += '\n'+measurement_text(result.get('analysis', {}).get('measurement_timings'))
    comparison = result.get('analysis', {}).get('rotation_comparison')
    if comparison:
        normal = comparison['normal_m']
        normal_text = f'{normal:.3f} 米' if normal is not None else '无安全方案'
        saving = comparison['saved_m']
        saved_text = f'{saving:.3f} 米' if saving is not None else '无法比较'
        review += (f"\n并行比较（分段前）：不旋转 {normal_text} · 启用旋转 {comparison['rotation_m']:.3f} 米"
                   f" · 省膜 {saved_text} · 实际旋转 {comparison['rotated_images']} 张")
    for item in quality.get('single_images', []):
        review += f"\n单排：{item['source']} · 图宽 {item['width_mm']:g} 毫米 · {item['reason']}"
    return ('按文件段号顺序生产，不重新排序。刀位从输出文件最左侧起算，实际膜位置还需加 RIIN 左预留。\n'
            '红色横线表示分段或批次结束，区域之间不加横线；不切入图片。刀码不添加旋转偏移。\n\n'
            +review+'\n\n'+'\n\n'.join(cutting_description(part) for part in parts))
