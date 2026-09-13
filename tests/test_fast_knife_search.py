from dataclasses import replace
from pathlib import Path
from random import Random

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.item_factory import LayoutItem
from automatic_print.layout_engine.cutter_planner import _horizontal, _lanes, solve_groups
from automatic_print.layout_engine.single_order_sequence import arrange_groups, horizontal_savings
from automatic_print.layout_engine.knife_optimizer import select_batch_knife, knife_candidates


def item(i, width, height, offset=0):
    return LayoutItem(Path(f'B{i}-1-T-Black-M-NO1-1.png'), i, width-15, height,
        15, offset, 0, 15, 0, 0, width, height+offset, 0, 0, 0, 10, 10)


def test_numeric_pair_cost_matches_real_placement_geometry():
    rng = Random(7)
    for i in range(200):
        a, b = [item(j, rng.randrange(50, 400), rng.randrange(50, 400), rng.randrange(5)) for j in (1, 2)]
        lanes = _lanes(LayoutSettings(dpi=25.4, cutter_knife_mm=rng.randrange(100, 480)), 600)
        row = _horizontal([a, b], lanes)
        expected = a.footprint_height+b.footprint_height-row.height if row else None
        assert horizontal_savings(a, b, lanes) == expected


def test_deduplicated_search_preserves_exhaustive_best_height_and_knife():
    rng = Random(11)
    for trial in range(12):
        groups = [[item(i, rng.randrange(70, 360), rng.randrange(90, 300))] for i in range(12)]
        settings = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual')
        scores = []
        for knife in knife_candidates(groups, settings):
            candidate = replace(settings, cutter_knife_mm=knife)
            lanes = _lanes(candidate, 580)
            result = solve_groups(arrange_groups(groups, lanes, candidate), lanes, 5)
            if result:
                scores.append((result[0], abs(knife-290), knife))
        actual = select_batch_knife(groups, settings, 5)
        assert round(actual.cutter_knife_mm) == min(scores)[2]
