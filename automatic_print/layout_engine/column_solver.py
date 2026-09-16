"""Ordered dynamic programming for one or more cutter lanes."""
from collections import Counter
from dataclasses import replace
from itertools import permutations

from .order_groups import order_key
from .size_policy import same_single_size
from .units import UnitChoice, UnitMember


def solve_groups(groups, lanes, spacing, pair_adjacent=False):
    counts = Counter(order_key(item.path) for group in groups for item in group)
    costs, plans = [float('inf')] * (len(groups) + 1), [None] * len(groups)
    costs[-1] = 0
    for index in range(len(groups) - 1, -1, -1):
        candidates = [(1, row) for row in group_rows(groups[index], lanes, spacing)]
        for count in range(min(len(lanes), len(groups)-index), 1, -1):
            selected = groups[index:index+count]
            if all(len(group) == 1 for group in selected):
                combined = [group[0] for group in selected]
                keys = [order_key(item.path) for item in combined]
                from .source_metadata import source_color
                compatible = (len({source_color(item.path) for item in combined}) == 1
                              if pair_adjacent else all(same_single_size(
                                  combined[0].path, item.path) for item in combined[1:]))
                share = len(set(keys)) == 1 or (
                    all(counts[key] == 1 for key in keys) and compatible)
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


def member(item, lane, y=0):
    start, end, marker = lane
    if marker is None:
        from .left_marker import external_left_item
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
    members = None
    for assigned in permutations(lanes[:len(group)]):
        candidate = [member(item, lane) for item, lane in zip(group, assigned)]
        if not any(value is None for value in candidate):
            members = candidate
            break
    if members is None:
        return None
    anchor_y = max(value.item.image_ry for value in members)
    return row([replace(value, y=anchor_y-value.item.image_ry) for value in members])


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
