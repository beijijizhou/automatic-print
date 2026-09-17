from __future__ import annotations

from automatic_print.layout_engine.domain.models import Placement


def optimal_ordered_rows(
    footprints: list[tuple[int, int]],
    usable_width: int,
    spacing: int,
) -> list[tuple[int, int]]:
    options = [[footprint] for footprint in footprints]
    return [
        (start, end)
        for start, end, _choices in optimal_ordered_layout(
            options, usable_width, spacing
        )
    ]


def optimal_ordered_layout(
    options: list[list[tuple[int, int]]],
    usable_width: int,
    spacing: int,
) -> list[tuple[int, int, tuple[int, ...]]]:
    """Optimize ordered row breaks and orientation choices exactly."""
    count = len(options)
    best: list[tuple[int, int, int] | None] = [None] * (count + 1)
    previous: list[tuple[int, tuple[int, ...]] | None] = [None] * (
        count + 1
    )
    best[0] = (0, 0, 0)
    for start in range(count):
        if best[start] is None:
            continue
        states = [(0, 0, (), 0)]
        for end in range(start, count):
            states = _extend_states(
                states,
                options[end],
                usable_width,
                spacing if end > start else 0,
            )
            if not states:
                break
            prior_height, prior_rotations, prior_rows = best[start]
            for _width, row_height, choices, rotations in states:
                candidate = (
                    prior_height
                    + row_height
                    + (spacing if start else 0),
                    prior_rotations + rotations,
                    prior_rows + 1,
                )
                if best[end + 1] is None or candidate < best[end + 1]:
                    best[end + 1] = candidate
                    previous[end + 1] = (start, choices)
    if best[count] is None:
        raise ValueError("至少一张图片超过了材料可打印宽度。")
    rows = []
    end = count
    while end:
        record = previous[end]
        if record is None:
            raise RuntimeError("排版优化结果不完整。")
        start, choices = record
        rows.append((start, end, choices))
        end = start
    return list(reversed(rows))


def _extend_states(states, item_options, usable_width, gap):
    expanded = []
    for width, height, choices, rotations in states:
        for choice, option in enumerate(item_options):
            item_width, item_height = option[:2]
            rotation_cost = option[2] if len(option) > 2 else int(choice > 0)
            new_width = width + gap + item_width
            if new_width <= usable_width:
                expanded.append(
                    (
                        new_width,
                        max(height, item_height),
                        choices + (choice,),
                        rotations + rotation_cost,
                    )
                )
    return _pareto_states(expanded)


def _pareto_states(states):
    result = []
    for state in sorted(states, key=lambda value: (value[0], value[1], value[3])):
        width, height, _choices, rotations = state
        if any(
            kept[0] <= width
            and kept[1] <= height
            and kept[3] <= rotations
            for kept in result
        ):
            continue
        result = [
            kept
            for kept in result
            if not (
                width <= kept[0]
                and height <= kept[1]
                and rotations <= kept[3]
            )
        ]
        result.append(state)
    return result


def used_canvas_width(planned):
    right_edges = []
    for _path, placement in planned:
        if placement.platform_width_px:
            right_edges.append(placement.platform_x_px + placement.platform_width_px)
        right_edges.append(placement.x_px + placement.width_px)
        if placement.number_width_px:
            right_edges.append(placement.number_x_px + placement.number_width_px)
        if placement.color_block_width_px:
            right_edges.append(placement.color_block_x_px + placement.color_block_width_px)
    return max(right_edges)


def place_rows(units, rows, top_margin, spacing):
    planned, y = [], top_margin
    for start, end, choice_indexes in rows:
        row = [units[index][choice] for index, choice in zip(
            range(start, end), choice_indexes, strict=True)]
        row_height = max(choice.height for choice in row)
        x = 0
        for choice in row:
            planned.extend(_place_choice(choice, x, y))
            x += choice.width + spacing
        y += row_height + spacing
    return planned


def _place_choice(choice, unit_x, row_y):
    placed = []
    for member in choice.members:
        item = member.item
        base_x, base_y = unit_x + member.x, row_y + member.y
        placed.append((item.path, Placement(
            item.path.name, item.index,
            base_x + item.image_rx, base_y + item.image_ry,
            item.width, item.height,
            base_x + item.label_rx, base_y + item.label_ry,
            item.label_width, item.label_height,
            row_y, choice.width, choice.height, item.rotation_degrees,
            base_x + item.block_rx, base_y + item.block_ry,
            item.block_width, item.block_height,
            platform_x_px=base_x + item.platform_rx,
            platform_y_px=base_y + item.platform_ry,
            platform_width_px=item.platform_width,
            platform_height_px=item.platform_height,
        )))
    return placed
