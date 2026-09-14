"""Measure once, then compare immutable geometry plans with bounded workers."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from copy import deepcopy
from dataclasses import replace
from time import monotonic

from .cutter_planner import plan_cutter_layout, read_cutter_items
from .rotation_zones import plan_rotation_zones, rotation_items
from .models import mm_to_px
from .measurement_session import measurement_session
from math import ceil
from .transition_marks import marked_height
from .order_validation import validate_order_placements
from .cut_validation import validate_cut_corridor
from .marker_space import validate_embedded_marks
from .batch_analysis import analyze_batch
from .film_specs import FILM_WIDTHS, AVAILABLE_WIDTHS, COMPARISON_COUNT, availability_text


def compare_films(paths, settings, progress=None):
    with measurement_session():
        return _compare_films(paths, settings, progress)


def _compare_films(paths, settings, progress):
    rows = []
    started = monotonic()
    shared = replace(settings, media_width_mm=max(FILM_WIDTHS)-settings.riin_left_mm-settings.riin_right_mm,
                     cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=False,
                     cutter_tail_rotation=False, allow_rotation=False,
                     manual_rotations=(), compare_film_sizes=False)
    options, labels = read_cutter_items(paths, shared, progress)
    rotated_items, rotated_labels = rotation_items(paths, shared, progress)
    analysis = analyze_batch(paths, shared)
    measured_seconds = monotonic()-started
    if progress:
        progress('膜规格比较', 0, COMPARISON_COUNT, '测量已完成，八套参考方案最多四路并行，不合成图片、不切换生产参数')
    completed = [0]
    def calculate(film, rotation):
            usable = film-settings.riin_left_mm-settings.riin_right_mm
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
                    progress('膜规格比较', completed[0], COMPARISON_COUNT, f'{name} · {stage} {current}/{total}')
            row = {'film_mm': film, 'usable_mm': usable, 'rotation_allowed': rotation,
                   'name': name, 'error': '', 'available': film in AVAILABLE_WIDTHS,
                   'availability': availability_text(film)}
            step = monotonic()
            try:
                if usable <= 0:
                    raise ValueError('RIIN 预留之和不小于膜宽')
                if rotation:
                    width = mm_to_px(usable, config.dpi)
                    safety = ceil(config.cutter_safety_mm*config.dpi/25.4)
                    fitting = {p: item for p, item in rotated_items.items()
                               if item.footprint_width+2*safety < width}
                    result = plan_rotation_zones(paths, config, report, deepcopy(analysis), None,
                                                prepared=(options, labels, fitting, rotated_labels))
                else:
                    result = plan_cutter_layout(paths, config, report, prepared=(options, labels))
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
            return row
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix='film-geometry') as pool:
        futures = [pool.submit(copy_context().run, calculate, film, rotation)
                   for film in FILM_WIDTHS for rotation in (False, True)]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            completed[0] = len(rows)
            if progress:
                progress('膜规格比较', len(rows), COMPARISON_COUNT, row['name']+' · '+('无安全方案' if row['error'] else '完成'))
    rows.sort(key=lambda r: (FILM_WIDTHS.index(r['film_mm']), r['rotation_allowed']))
    valid = [r for r in rows if not r['error']]
    best = min(valid, key=lambda r: r['film_area_m2']) if valid else None
    for row in valid:
        row['extra_area_vs_best_m2'] = row['film_area_m2']-best['film_area_m2']
    return {'rows': rows, 'seconds': monotonic()-started,
            'best_name': best['name'] if best else '', 'parallelism': 4,
            'measurement_seconds': measured_seconds,
            'scope': '分段前；自动刀位；无手动旋转；包含标签、刀码、红线和留白；仅几何检查',
            'occupancy_basis': '生产图片矩形面积，含原图透明部分，不含新增标签/刀码；不是油墨覆盖率'}


def comparison_text(comparison):
    if not comparison:
        return ''
    lines = ['膜规格八方案比较（分段前，按耗膜面积比较；不自动选择生产方案）']
    if 'measurement_seconds' in comparison:
        measurement = comparison['measurement_seconds']
        lines.append(f"共享测量 {measurement:.2f} 秒 · 方案并行计算 "
                     f"{max(0, comparison['seconds']-measurement):.2f} 秒")
    for r in comparison['rows']:
        lines.append(r['name']+' · '+r.get('availability', '现有规格'))
        if r['error']:
            lines.append(r['name']+'：无安全方案 · '+r['error'])
        else:
            lines.append(f"{r['name']}：{r['length_m']:.3f} 米 · {r['film_area_m2']:.3f} 平方米"
                         f" · 图片占位 {r['image_occupancy_percent']:.1f}%"
                         f" · 可用区占位 {r['usable_occupancy_percent']:.1f}%"
                         f" · 实际旋转 {r['rotated_images']} 张"
                         f" · 比最省方案多 {r['extra_area_vs_best_m2']:.3f} 平方米")
    lines += ['理论面积最省（不代表当前设备可生产）：'+(comparison['best_name'] or '无安全方案'),
              comparison['scope'], comparison['occupancy_basis']]
    return '\n'.join(lines)
