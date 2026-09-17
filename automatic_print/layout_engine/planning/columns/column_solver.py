"""Ordered dynamic programming for one or more cutter lanes."""
from collections import Counter
from dataclasses import replace
from itertools import product

from automatic_print.layout_engine.orders.order_groups import order_key
from automatic_print.layout_engine.orders.size_policy import same_single_size
from automatic_print.layout_engine.planning.packing.units import UnitChoice, UnitMember


def solve_groups(
    groups, lanes, spacing, pair_adjacent=False, allow_order_boundary=False,
):
    counts = Counter(order_key(item.path) for group in groups for item in group)
    group_keys = [order_key(group[0].path) for group in groups]
    first_group = {key: group_keys.index(key) for key in dict.fromkeys(group_keys)}
    last_group = {key: len(group_keys)-1-group_keys[::-1].index(key)
                  for key in dict.fromkeys(group_keys)}
    costs, plans = [float('inf')] * (len(groups) + 1), [None] * len(groups)
    costs[-1] = 0
    for index in range(len(groups) - 1, -1, -1):
        candidates = [(1, row) for row in group_rows(groups[index], lanes, spacing)]
        for count in range(min(len(lanes), len(groups)-index), 1, -1):
            selected = groups[index:index+count]
            if all(len(group) == 1 for group in selected):
                combined = [group[0] for group in selected]
                keys = [order_key(item.path) for item in combined]
                from automatic_print.layout_engine.intake.metadata.source_metadata import source_color
                compatible = (len({source_color(item.path) for item in combined}) == 1
                              if pair_adjacent else all(same_single_size(
                                  combined[0].path, item.path) for item in combined[1:]))
                boundary_share = all(
                    keys[offset] == keys[offset+1]
                    or (index+offset == last_group[keys[offset]]
                        and index+offset+1 == first_group[keys[offset+1]])
                    for offset in range(len(keys)-1)
                )
                share = len(set(keys)) == 1 or (
                    compatible and (all(counts[key] == 1 for key in keys)
                                    or allow_order_boundary and boundary_share))
                candidate = horizontal(combined, lanes) if share else None
                if candidate:
                    candidates.insert(0, (count, candidate))
        for count, candidate in candidates:
            cost = candidate.height + spacing + costs[index + count]
            if cost < costs[index]:
                costs[index], plans[index] = cost, (count, candidate)
        if plans[index] is None:
            return None
    return costs[0], plans


def solve_group_choices(
    groups, lanes, spacing, pair_adjacent=False, allow_order_boundary=False,
    allow_any_adjacent=False,
):
    """Solve ordered groups while choosing each group's safe orientation."""
    representative = [choices[0] for choices in groups]
    counts = Counter(order_key(item.path) for group in representative for item in group)
    group_keys = [order_key(group[0].path) for group in representative]
    first_group = {key: group_keys.index(key) for key in dict.fromkeys(group_keys)}
    last_group = {key: len(group_keys)-1-group_keys[::-1].index(key)
                  for key in dict.fromkeys(group_keys)}
    costs, plans = [float('inf')] * (len(groups)+1), [None] * len(groups)
    costs[-1] = 0
    for index in range(len(groups)-1, -1, -1):
        candidates = [(1, row) for choice in groups[index]
                      for row in group_rows(choice, lanes, spacing)]
        for count in range(min(len(lanes), len(groups)-index), 1, -1):
            for selected in product(*groups[index:index+count]):
                if not all(len(group) == 1 for group in selected):
                    continue
                combined = [group[0] for group in selected]
                keys = [order_key(item.path) for item in combined]
                from automatic_print.layout_engine.intake.metadata.source_metadata import source_color
                compatible = (True if allow_any_adjacent else
                              len({source_color(item.path) for item in combined}) == 1
                              if pair_adjacent else all(same_single_size(
                                  combined[0].path, item.path) for item in combined[1:]))
                boundary_share = all(
                    keys[offset] == keys[offset+1]
                    or (index+offset == last_group[keys[offset]]
                        and index+offset+1 == first_group[keys[offset+1]])
                    for offset in range(len(keys)-1)
                )
                share = allow_any_adjacent or len(set(keys)) == 1 or (
                    compatible and (all(counts[key] == 1 for key in keys)
                                    or allow_order_boundary and boundary_share))
                candidate = horizontal(combined, lanes) if share else None
                if candidate:
                    candidates.append((count, candidate))
        for count, candidate in candidates:
            cost = candidate.height + spacing + costs[index+count]
            if cost < costs[index]:
                costs[index], plans[index] = cost, (count, candidate)
        if plans[index] is None:
            return None
    return costs[0], plans


def member(item, lane, y=0):
    start, end, marker = lane
    if marker is None:
        from automatic_print.layout_engine.labeling.markers.left_marker import external_left_item
        item = external_left_item(item)
    x = start if marker is None else marker - item.block_rx
    return None if x < start or x + item.footprint_width > end else UnitMember(item, x, y)


def row(members):
    return UnitChoice(max(m.x + m.item.footprint_width for m in members),
                      max(m.y + m.item.footprint_height for m in members),
                      tuple(members), 0)


def horizontal(group, lanes):
    if len(group) > len(lanes) or len(group) < 2:
        return None
    members = _first_lane_assignment(group, lanes[:len(group)])
    if members is None:
        return None
    anchor_y = max(value.item.image_ry for value in members)
    return row([replace(value, y=anchor_y-value.item.image_ry) for value in members])


def _first_lane_assignment(group, lanes):
    """Return the former permutation-first match without factorial rescans."""
    failed = set()

    def assign(item_index, used):
        state = item_index, used
        if state in failed:
            return None
        if item_index == len(group):
            return []
        for lane_index, lane in enumerate(lanes):
            bit = 1 << lane_index
            if used & bit:
                continue
            value = member(group[item_index], lane)
            if value is None:
                continue
            remaining = assign(item_index + 1, used | bit)
            if remaining is not None:
                return [value, *remaining]
        failed.add(state)
        return None

    return assign(0, 0)


def group_rows(group, lanes, spacing):
    if 2 <= len(group) <= len(lanes):
        candidate = horizontal(group, lanes)
        if candidate:
            return [candidate]
    members, y = [], 0
    for item in group:
        value = member(item, lanes[0], y)
        if value is None:
            return []
        members.append(value)
        y += item.footprint_height + spacing
    return [row(members)]
