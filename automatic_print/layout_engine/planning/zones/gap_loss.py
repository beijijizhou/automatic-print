"""Geometry-only comparison against unchanged source images."""
from dataclasses import replace
from pathlib import Path
from time import perf_counter


def compare_gap_loss(records, settings, actual_m, progress=None):
    changed = [r for r in records if r.get('added_px', 0)]
    width_m = (settings.media_width_mm+settings.riin_left_mm+settings.riin_right_mm)/1000
    if not changed:
        return dict(original_m=actual_m, current_m=actual_m, extra_m=0,
                    extra_area_m2=0, changed_images=0, seconds=0)
    paths = [Path(r['source']) for r in records]
    remap = {str(Path(r.get('prepared', r['source'])).resolve()): str(Path(r['source']).resolve())
             for r in records}
    reference = replace(settings, membrane_gap_mm=0, compare_film_sizes=False,
        compare_reference_films=False, developer_gap_loss=False,
        manual_rotations=tuple((remap.get(str(Path(p).resolve()),p),d) for p,d in settings.manual_rotations),
        sequence_numbers=tuple((remap.get(str(Path(p).resolve()),p),n) for p,n in settings.sequence_numbers))
    started = perf_counter()
    from automatic_print.layout_engine.planning.base.planner import plan_layout
    try:
        result = plan_layout(paths, reference,
            (lambda stage, current, total, name: progress('间距参考·'+stage, current, total, name))
            if progress else None)
    except (ValueError, OSError) as exc:
        return dict(unavailable=str(exc), changed_images=len(changed), seconds=perf_counter()-started)
    original_m = result[3]*25.4/settings.dpi/1000
    extra = actual_m-original_m
    return dict(original_m=original_m, current_m=actual_m, extra_m=extra,
        extra_area_m2=extra*width_m, changed_images=len(changed), seconds=perf_counter()-started)


def gap_loss_text(data):
    if not data:
        return ''
    if data.get('unavailable'):
        reason = str(data['unavailable']).replace('禁止输出：', '')
        reason = reason.replace('，禁止输出。', '。').replace('禁止输出。', '').strip()
        return ('间距额外用膜：原间距对照未完成，不影响当前排版；'
                '当前采用补足间距方案。对照未完成原因：'+reason)
    return (f"间距额外用膜：补足 {data['changed_images']} 张 · 原间距 {data['original_m']:.3f} 米"
            f" · 当前 {data['current_m']:.3f} 米 · 增量 {data['extra_m']:+.3f} 米"
            f" / {data['extra_area_m2']:+.3f} 平方米\n"
            '同膜宽、同旋转策略重新排版，分段前比较；可因方向变化出现负增量。')
