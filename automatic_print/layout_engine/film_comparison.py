"""Four geometry-only alternatives; sequential to avoid nested CPU/I/O contention."""
from dataclasses import replace
from time import monotonic

from .cutter_planner import plan_cutter_layout
from .rotation_zones import plan_rotation_zones
from .transition_marks import marked_height
from .order_validation import validate_order_placements
from .cut_validation import validate_cut_corridor
from .marker_space import validate_embedded_marks
from .batch_analysis import analyze_batch


def compare_films(paths, settings, progress=None):
    rows = []
    started = monotonic()
    if progress:
        progress('膜规格比较', 0, 4, '开始四套整批几何计算，不生成比较 PNG')
    for film in (600, 450):
        usable = film-settings.riin_left_mm-settings.riin_right_mm
        for rotation in (False, True):
            name = f'{film/10:g} 厘米 · '+('允许旋转' if rotation else '不旋转')
            config = replace(settings, media_width_mm=usable, cutter_mode='dual',
                             cutter_auto_knife=True, cutter_rotation_zone=rotation,
                             cutter_tail_rotation=False, allow_rotation=False,
                             manual_rotations=(), compare_film_sizes=False)
            effective = [config]
            def report(stage, current, total, filename):
                if stage == '批次刀位已确定':
                    effective[0] = replace(config, cutter_knife_mm=current*25.4/total)
                if progress:
                    progress('膜规格比较', len(rows), 4,
                             f'{name} · {stage} {current}/{total} · {filename}')
            row = {'film_mm': film, 'usable_mm': usable, 'rotation_allowed': rotation,
                   'name': name, 'error': ''}
            step = monotonic()
            try:
                if usable <= 0:
                    raise ValueError('RIIN 预留之和不小于膜宽')
                if rotation:
                    analysis = analyze_batch(paths, config, report)
                    result = plan_rotation_zones(paths, config, report, analysis, None)
                else:
                    result = plan_cutter_layout(paths, config, report)
                planned, _, width, height = result[:4]
                validate_order_placements(paths, planned)
                validate_cut_corridor(planned, effective[0], width)
                validate_embedded_marks(planned)
                height = marked_height(planned, config, width, height)
                metres_per_px = 25.4/config.dpi/1000
                length = height*metres_per_px
                image_area = sum(p.width_px*p.height_px for _, p in planned)*metres_per_px**2
                area = film/1000*length
                usable_area = usable/1000*length
                row.update(length_m=length, film_area_m2=area, usable_area_m2=usable_area,
                           image_area_m2=image_area,
                           image_occupancy_percent=100*image_area/area if area else 0,
                           usable_occupancy_percent=100*image_area/usable_area if usable_area else 0,
                           rotated_images=sum(bool(p.rotation_degrees) for _, p in planned))
            except ValueError as exc:
                row['error'] = str(exc)
            row['seconds'] = monotonic()-step
            rows.append(row)
            if progress:
                progress('膜规格比较', len(rows), 4, name+' · '+('无安全方案' if row['error'] else '完成'))
    valid = [r for r in rows if not r['error']]
    best = min(valid, key=lambda r: r['film_area_m2']) if valid else None
    for row in valid:
        row['extra_area_vs_best_m2'] = row['film_area_m2']-best['film_area_m2']
    return {'rows': rows, 'seconds': monotonic()-started,
            'best_name': best['name'] if best else '', 'parallelism': 1,
            'scope': '分段前；自动刀位；无手动旋转；包含标签、刀码、红线和留白；仅几何检查',
            'occupancy_basis': '生产图片矩形面积，含原图透明部分，不含新增标签/刀码；不是油墨覆盖率'}


def comparison_text(comparison):
    if not comparison:
        return ''
    lines = ['膜规格四方案比较（分段前，按耗膜面积比较）']
    for r in comparison['rows']:
        if r['error']:
            lines.append(r['name']+'：无安全方案 · '+r['error'])
        else:
            lines.append(f"{r['name']}：{r['length_m']:.3f} 米 · {r['film_area_m2']:.3f} 平方米"
                         f" · 图片占位 {r['image_occupancy_percent']:.1f}%"
                         f" · 可用区占位 {r['usable_occupancy_percent']:.1f}%"
                         f" · 实际旋转 {r['rotated_images']} 张"
                         f" · 比最省方案多 {r['extra_area_vs_best_m2']:.3f} 平方米")
    lines += ['面积最省：'+(comparison['best_name'] or '无安全方案'),
              comparison['scope'], comparison['occupancy_basis']]
    return '\n'.join(lines)
