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
    notices = '；'.join(f"{r['kind']}红线：距文件顶部 {r['y']*25.4/result['output_dpi']:.1f} 毫米"
                        for r in result.get('transition_marks', []))
    rotated = any(p['cut_zone'] == '旋转区' for p in result['placements'])
    shift = f" · 旋转区刀码右移 {result.get('rotation_marker_shift_mm', 0):g} 毫米" if rotated else ''
    return (f"{result['filename']} · {sizes} · {len(result['placements'])} 张 · {knife or '单列 / 自由排版'}"
            f"{shift}"+(f'\n{notices}' if notices else ''))


def cutting_report(result):
    parts = result.get('parts') or [result]
    return ('按文件段号顺序生产，不重新排序。刀位从输出文件最左侧起算，实际膜位置还需加 RIIN 左预留。\n'
            '红色横线表示分段、换刀或批次结束，详见每段说明；不切入图片。刀码偏移是否停机必须实测。\n\n'
            +'\n\n'.join(cutting_description(part) for part in parts))
