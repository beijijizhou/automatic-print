from __future__ import annotations


def optimal_ordered_rows(
    footprints: list[tuple[int, int]],
    usable_width: int,
    spacing: int,
) -> list[tuple[int, int]]:
    """Minimize total ordered shelf height without reordering items."""
    count = len(footprints)
    best: list[tuple[int, int] | None] = [None] * (count + 1)
    previous = [-1] * (count + 1)
    best[0] = (0, 0)
    for start in range(count):
        if best[start] is None:
            continue
        row_width = 0
        row_height = 0
        for end in range(start, count):
            width, height = footprints[end]
            row_width += width + (spacing if end > start else 0)
            if row_width > usable_width:
                break
            row_height = max(row_height, height)
            prior_height, prior_rows = best[start]
            candidate = (
                prior_height + row_height + (spacing if start else 0),
                prior_rows + 1,
            )
            if best[end + 1] is None or candidate < best[end + 1]:
                best[end + 1] = candidate
                previous[end + 1] = start
    if best[count] is None:
        raise ValueError("至少一张图片超过了材料可打印宽度。")
    rows = []
    end = count
    while end:
        start = previous[end]
        rows.append((start, end))
        end = start
    return list(reversed(rows))
