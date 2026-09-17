from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from copy import deepcopy
from dataclasses import replace
from time import monotonic
from automatic_print.layout_engine.planning.columns.cutter_planner import plan_cutter_layout, read_cutter_items
from automatic_print.layout_engine.planning.rotation.rotation_zones import plan_rotation_zones, rotation_items
from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.measurement.measurement_session import measurement_session, verify_sources
from math import ceil
from automatic_print.layout_engine.cutting.geometry.transition_marks import marked_height
from automatic_print.layout_engine.cutting.validation.order_validation import validate_order_placements
from automatic_print.layout_engine.cutting.validation.cut_validation import validate_cut_corridor
from automatic_print.layout_engine.cutting.geometry.knife_change_gap import apply_knife_change_gap
from automatic_print.layout_engine.labeling.markers.marker_space import validate_embedded_marks
from automatic_print.layout_engine.orders.batch_analysis import analyze_batch
from automatic_print.layout_engine.planning.film.film_specs import AVAILABLE_WIDTHS, availability_text, comparison_widths
from automatic_print.layout_engine.planning.cache.normal_plan_cache import NormalPlans
from automatic_print.layout_engine.diagnostics.dual_quality import dual_quality
def compare_films(paths, settings, progress=None, production=None):
    with measurement_session():
        result = _compare_films(paths, settings, progress, production)
        verify_sources()
        return result
def _compare_films(paths, settings, progress, production=None):
    rows = []
    started = monotonic()
    widths = comparison_widths(settings.compare_reference_films)
    count = len(widths)*2
    workers = max(1, min(4, settings.film_geometry_workers))
    shared = replace(settings, media_width_mm=max(widths)-settings.riin_left_mm-settings.riin_right_mm,
                     cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=False,
                     cutter_tail_rotation=False, allow_rotation=False,
                     manual_rotations=(), compare_film_sizes=False)
    choices, labels = read_cutter_items(paths, shared, progress, prepare_rotations=True,
                                        include_choices=True)
    options = [[row[0]] for row in choices]
    rotated_items, rotated_labels = rotation_items(paths, shared, None, prepared=(choices, labels))
    analysis = analyze_batch(paths, shared)
    measured_seconds = monotonic()-started
    if progress:
        progress('膜规格比较', 0, count, f'测量已完成，{count}套方案最多{workers}路计算，不合成图片、不切换生产参数')
    completed = [0]
    normals = NormalPlans(plan_cutter_layout)
    production_key = _production_key(production, settings)
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
                    progress('膜规格比较', completed[0], count, f'{name} · {stage} {current}/{total}')
            row = {'film_mm': film, 'usable_mm': usable, 'rotation_allowed': rotation,
                   'name': name, 'error': '', 'available': film in AVAILABLE_WIDTHS,
                   'availability': availability_text(film)}
            step = monotonic()
            try:
                if usable <= 0:
                    raise ValueError('RIIN 预留之和不小于膜宽')
                if production_key == (film, rotation):
                    row.update(_production_values(production, settings))
                    row['seconds'] = monotonic()-step
                    return row
                baseline, normal_config, normal_error = normals.get(
                    film, paths, config, report, (options, labels))
                if rotation:
                    width = mm_to_px(usable, config.dpi)
                    safety = ceil(config.cutter_safety_mm*config.dpi/25.4)
                    fitting = {p: item for p, item in rotated_items.items()
                               if item.footprint_width+2*safety < width}
                    result = plan_rotation_zones(paths, config, report, deepcopy(analysis), None,
                                                prepared=(options, labels, fitting, rotated_labels),
                                                normal_baseline=(baseline, normal_config))
                    from automatic_print.layout_engine.planning.rotation.whole_rotation import compare_whole
                    result = compare_whole(paths,config,report,result,(fitting,rotated_labels))
                else:
                    if normal_error:
                        raise ValueError(normal_error)
                    result, effective[0] = baseline, normal_config
                if config.cutter_knife_change_gap_mm > 0:
                    result, _changes = apply_knife_change_gap(result, config)
                planned, _, width, height = result[:4]
                validate_order_placements(paths, planned)
                validate_cut_corridor(planned, effective[0], width, 0, height)
                validate_embedded_marks(planned, config)
                height = marked_height(planned, config, width, height)
                metres_per_px = 25.4/config.dpi/1000
                length = height*metres_per_px
                image_area = sum(p.width_px*p.height_px for _, p in planned)*metres_per_px**2
                area = film/1000*length
                usable_area = usable/1000*length
                quality = dual_quality(planned, config, analysis)
                row.update(length_m=length, film_area_m2=area, usable_area_m2=usable_area,
                           image_area_m2=image_area,
                           image_occupancy_percent=100*image_area/area if area else 0,
                           usable_occupancy_percent=100*image_area/usable_area if usable_area else 0,
                           rotated_images=sum(bool(p.rotation_degrees) for _, p in planned),
                           paired_rows=quality.get('paired_rows', 0),
                           paired_images=quality.get('paired_rows', 0)*2,
                           column_rows=quality.get('column_rows', {}),
                           parallel_text=quality.get('parallel_text', '无并排'))
            except ValueError as exc:
                row['error'] = str(exc)
            row['seconds'] = monotonic()-step
            return row
    def collect(results):
        for row in results:
            rows.append(row)
            completed[0] = len(rows)
            if progress:
                progress('膜规格比较', len(rows), count, row['name']+' · '+('无安全方案' if row['error'] else '完成'))
    if workers == 1:
        collect(calculate(film, rotation) for rotation in (False, True) for film in widths)
    else:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='film-geometry') as pool:
            futures = [pool.submit(copy_context().run, calculate, film, rotation)
                       for rotation in (False, True) for film in widths]
            collect(future.result() for future in as_completed(futures))
    rows.sort(key=lambda r: (widths.index(r['film_mm']), r['rotation_allowed']))
    _apply_production_result(rows, production, settings)
    valid = [r for r in rows if not r['error']]
    best = min(valid, key=lambda r: r['film_area_m2']) if valid else None
    for row in valid:
        row['extra_area_vs_best_m2'] = row['film_area_m2']-best['film_area_m2']
    return {'rows': rows, 'seconds': monotonic()-started,
            'best_name': best['name'] if best else '', 'parallelism': workers,
            'measurement_seconds': measured_seconds,
            'scope': '分段前；自动多列与多刀位；单件并排优先，仅完整单排尺码后缀旋转；无手动旋转；包含标签、刀码、红线和留白；仅几何检查',
            'occupancy_basis': '生产图片矩形面积，含原图透明部分，不含新增标签/刀码；不是油墨覆盖率'}
def _apply_production_result(rows, production, settings):
    """Make the current-film row report the exact plan that will be written."""
    if production is None:
        return
    film, rotation = _production_key(production, settings)
    row = next((item for item in rows if abs(item['film_mm'] - film) < .01
                and item['rotation_allowed'] == rotation), None)
    if row is None:
        return
    row.update(_production_values(production, settings))
def _production_key(production, settings):
    if production is None:
        return None
    planned = production[0]
    film = settings.media_width_mm + settings.riin_left_mm + settings.riin_right_mm
    rotation = bool(
        settings.cutter_rotation_zone or settings.cutter_majority_two_zone
        or settings.cutter_tail_rotation or any(p.rotation_degrees for _, p in planned)
    )
    return film, rotation
def _production_values(production, settings):
    planned, _labels, _width, height = production[:4]
    film, _rotation = _production_key(production, settings)
    scale = 25.4 / settings.dpi / 1000
    length = height * scale
    image_area = sum(p.width_px * p.height_px for _, p in planned) * scale ** 2
    area = film / 1000 * length
    usable_area = settings.media_width_mm / 1000 * length
    quality = dual_quality(planned, settings)
    return dict(
        error='', production_selected=True, length_m=length,
        film_area_m2=area, usable_area_m2=usable_area,
        image_area_m2=image_area,
        image_occupancy_percent=100 * image_area / area if area else 0,
        usable_occupancy_percent=100 * image_area / usable_area if usable_area else 0,
        rotated_images=sum(bool(p.rotation_degrees) for _, p in planned),
        paired_rows=quality.get('paired_rows', 0),
        paired_images=quality.get('paired_rows', 0) * 2,
        column_rows=quality.get('column_rows', {}),
        parallel_text=quality.get('parallel_text', '无并排'),
    )
def comparison_text(comparison):
    if not comparison:
        return ''
    extended = any(r['film_mm'] not in AVAILABLE_WIDTHS for r in comparison['rows'])
    label = '40–80厘米、间隔5厘米' if extended else '45/60厘米'
    lines = [f'膜规格比较：{label}（分段前，按耗膜面积比较；不自动选择生产方案）']
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
                         f" · 并排 {r.get('parallel_text', '无并排')}"
                         f" · 图片占位 {r['image_occupancy_percent']:.1f}%"
                         f" · 可用区占位 {r['usable_occupancy_percent']:.1f}%"
                         f" · 实际旋转 {r['rotated_images']} 张"
                         f" · 比最省方案多 {r['extra_area_vs_best_m2']:.3f} 平方米")
    lines += ['理论面积最省（不代表当前设备可生产）：'+(comparison['best_name'] or '无安全方案'),
              comparison['scope'], comparison['occupancy_basis']]
    return '\n'.join(lines)
