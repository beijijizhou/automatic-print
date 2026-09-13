"""Evaluate all width-feasibility boundaries with the ordered batch DP."""
from dataclasses import replace
from math import ceil

from .models import mm_to_px
from .single_order_sequence import arrange_groups, prepare_groups, lane_fits


def select_batch_knife(groups, settings, spacing, progress=None):
    from .cutter_planner import _lanes, solve_groups
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    candidates = distinct_knife_candidates(groups, settings)
    best = None
    prepared = prepare_groups(groups)
    if progress:
        progress('计算批次刀位', 0, len(candidates), '开始整批固定刀位比较')
    for index, knife in enumerate(candidates):
        trial = replace(settings, cutter_knife_mm=knife*25.4/settings.dpi)
        lanes = _lanes(trial, width)
        result = solve_groups(arrange_groups(groups, lanes, trial, prepared), lanes, spacing)
        if result is not None:
            score = (result[0], abs(knife-width/2), knife)
            if best is None or score < best[0]:
                best = score, trial
        if progress:
            progress("计算批次刀位", index+1, len(candidates), "比较整批排版长度，保持订单顺序")
    if best is None:
        raise ValueError("整批图片不存在安全的统一双列刀位，请使用单列或更宽的膜。")
    return best[1]


def distinct_knife_candidates(groups, settings):
    """Equivalent lane-feasibility states have identical ordered height costs."""
    from .cutter_planner import _lanes
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    items = [item for group in groups for item in group]
    states = {}
    for knife in knife_candidates(groups, settings):
        lanes = _lanes(replace(settings, cutter_knife_mm=knife*25.4/settings.dpi), width)
        signature = tuple(lane_fits(item, lane) for item in items for lane in lanes)
        old = states.get(signature)
        if old is None or (abs(knife-width/2), knife) < (abs(old-width/2), old):
            states[signature] = knife
    return sorted(states.values())


def knife_candidates(groups, settings):
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    safety = ceil(settings.cutter_safety_mm * settings.dpi / 25.4)
    offset = mm_to_px(settings.cutter_marker_offset_mm, settings.dpi)
    candidates = {width//2, mm_to_px(settings.cutter_knife_mm, settings.dpi)}
    for group in groups:
        for item in group:
            candidates.add(item.footprint_width+safety)
            candidates.add(width-item.footprint_width-safety-offset+item.block_rx)
    return sorted(k for k in candidates if safety < k < width-safety-offset)
