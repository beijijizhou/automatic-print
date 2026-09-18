"""Compare every fixed normal knife while assigning whole orders to two zones."""
from dataclasses import replace

from automatic_print.layout_engine.planning.columns.cutter_planner import _horizontal, _lanes, solve_groups
from automatic_print.layout_engine.planning.knife.optimizer import distinct_knife_candidates
from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.planning.packing.units import build_units
from automatic_print.layout_engine.orders.size_policy import coalesced_size, same_single_size


def select_zones(orders, normal_items, rotated_items, settings, progress=None):
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    groups = []
    for order in orders:
        units = build_units([[normal_items[p]] for p in order], spacing)
        groups.append([[m.item for m in choices[0].members] for choices in units])
    knives = distinct_knife_candidates([g for order in groups for g in order], settings)
    if not settings.cutter_auto_knife:
        knives = [mm_to_px(settings.cutter_knife_mm, settings.dpi)]
    rotated_costs = [sum(rotated_items[p].footprint_height + spacing for p in order)
                     if all(p in rotated_items for p in order) else None for order in orders]
    best = None
    if progress:
        progress('比较旋转区域', 0, len(knives), '开始完整订单旋转组合比较')
    for index, knife in enumerate(knives):
        lanes = _lanes(replace(settings, cutter_knife_mm=knife*25.4/settings.dpi), width)
        sequence = list(range(len(orders)))  # Coalesced size blocks are already in production order.
        result = _assign([groups[i] for i in sequence], [rotated_costs[i] for i in sequence],
                         lanes, spacing, margin,
                         {pos for pos, i in enumerate(sequence) if coalesced_size(orders[i]) is not None})
        if result is not None:
            height, mask = result
            score = height, mask.bit_count(), abs(knife-width/2), knife
            if best is None or score < best[0]:
                best = score, mask, knife, sequence
        if progress:
            progress('比较旋转区域', index+1, len(knives), '同时比较常规、混合及整批旋转，保持完整订单')
    if best is None:
        raise ValueError('整批订单无法安全放入常规区或旋转区，请检查膜宽和图片尺寸。')
    return best[1], best[2], best[0][0], best[3]


def _assign(groups, rotated_costs, lanes, spacing, margin, sized=frozenset()):
    # A pending single-image order can share the next normal single order's row,
    # including across orders moved to the rotation zone. Multi-piece orders stay closed.
    singles, normal_costs = {}, []
    for index, order in enumerate(groups):
        result = solve_groups(order, lanes, spacing)
        normal_costs.append(result[0] if result else None)
        if len(order) == 1 and len(order[0]) == 1:
            singles[index] = order[0][0]
    states = {(None, False, False, False): (0, 0)}
    for index, normal_cost in enumerate(normal_costs):
        following = {}
        for (pending, normal, rotated, size_rotated), (cost, mask) in states.items():
            rotation_cost = rotated_costs[index]
            if rotation_cost is not None:
                _keep(following, (pending, normal, True, size_rotated or index in sized), cost+rotation_cost, mask | (1 << index))
            if normal_cost is None:
                continue
            if size_rotated and index in sized:
                continue  # Normal then rotated blocks must preserve ascending sizes.
            if index in singles:
                if pending is not None:
                    row = _horizontal([singles[pending], singles[index]], lanes) if same_single_size(singles[pending].path, singles[index].path) else None
                    if row:
                        _keep(following, (None, True, rotated, size_rotated), cost+row.height+spacing, mask)
                flushed = normal_costs[pending] if pending is not None else 0
                _keep(following, (index, True, rotated, size_rotated), cost+flushed, mask)
            else:
                flushed = normal_costs[pending] if pending is not None else 0
                _keep(following, (None, True, rotated, size_rotated), cost+flushed+normal_cost, mask)
        states = following
    results = []
    for (pending, normal, rotated, _size_rotated), (cost, mask) in states.items():
        cost += normal_costs[pending] if pending is not None else 0
        # Each zone has its own opening/closing margin, plus one boundary gap.
        height = cost-spacing + 2*margin*(int(normal)+int(rotated))
        results.append((height, mask))
    return min(results, key=lambda x: (x[0], x[1].bit_count(), x[1])) if results else None


def _keep(states, key, cost, mask):
    previous = states.get(key)
    score = cost, mask.bit_count(), mask
    if previous is None or score < (previous[0], previous[1].bit_count(), previous[1]):
        states[key] = cost, mask
