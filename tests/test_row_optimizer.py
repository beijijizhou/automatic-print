from automatic_print.layout_engine.row_optimizer import (
    optimal_ordered_rows,
)


def test_optimizer_beats_greedy_without_reordering() -> None:
    footprints = [(2, 1), (2, 1), (2, 3), (5, 3)]

    rows = optimal_ordered_rows(footprints, usable_width=10, spacing=0)

    flattened = [
        index for start, end in rows for index in range(start, end)
    ]
    assert flattened == [0, 1, 2, 3]
    optimized_height = sum(
        max(height for _width, height in footprints[start:end])
        for start, end in rows
    )
    assert optimized_height == 4
    assert optimized_height < 6  # 顺序贪心算法的结果


def test_optimizer_counts_horizontal_and_vertical_spacing() -> None:
    footprints = [(4, 2), (4, 5), (4, 1)]

    rows = optimal_ordered_rows(footprints, usable_width=9, spacing=1)

    assert rows == [(0, 2), (2, 3)]
