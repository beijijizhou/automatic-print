from dataclasses import replace
from random import Random

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.orders.single_order_sequence import arrange_groups, lane_fits
from automatic_print.layout_engine.planning.columns.cutter_planner import _lanes, solve_groups
from automatic_print.layout_engine.planning.columns.knife_optimizer import (
    distinct_knife_candidates, knife_candidates, select_batch_knife,
)
from test_fast_knife_search import item


def test_deduplicated_search_preserves_exhaustive_best_height_and_knife():
    rng = Random(11)
    for _trial in range(12):
        groups = [[item(i, rng.randrange(70, 360), rng.randrange(90, 300))]
                  for i in range(12)]
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


def test_range_event_states_match_full_lane_checks_with_marker_offsets():
    rng = Random(17)
    for _ in range(20):
        groups = [[replace(item(i, rng.randrange(50, 500), 200),
                           block_rx=rng.randrange(-5, 30))] for i in range(20)]
        config = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual',
                                cutter_marker_offset_mm=rng.randrange(0, 25))
        states = {}
        for knife in knife_candidates(groups, config):
            lanes = _lanes(replace(config, cutter_knife_mm=knife), 580)
            signature = tuple(lane_fits(g[0], lane) for g in groups for lane in lanes)
            old = states.get(signature)
            if old is None or (abs(knife-290), knife) < (abs(old-290), old):
                states[signature] = knife
        assert distinct_knife_candidates(groups, config) == sorted(states.values())
