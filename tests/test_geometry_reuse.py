from dataclasses import replace
from random import Random
from concurrent.futures import ThreadPoolExecutor

import pytest

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine import single_order_sequence as sequence
from automatic_print.layout_engine import measurement_session as measurements
from automatic_print.layout_engine.cutter_planner import _lanes
from automatic_print.layout_engine.normal_plan_cache import NormalPlans
from test_fast_knife_search import item


def old_sequence(orders, items, lanes, prepared):
    locked, pending, sizes = prepared
    pending, result = list(pending), list(locked)
    fits = {path: tuple(sequence.lane_fits(v, lane) for lane in lanes) for path, v in items.items()}
    while pending:
        first = pending.pop(0)
        result.append(first)
        if len(orders[first]) != 1:
            continue
        best = None
        for position, index in enumerate(pending):
            if len(orders[index]) != 1 or sizes[index] != sizes[first]:
                continue
            saved = sequence.horizontal_savings(items[orders[first][0]], items[orders[index][0]], lanes, fits)
            if saved is not None and saved > 0:
                candidate = -saved, position, index
                if best is None or candidate < best:
                    best = candidate
        if best:
            pending.remove(best[-1])
            result.append(best[-1])
    return result


def geometry(n, seed=7):
    rng = Random(seed)
    values = [replace(item(i, rng.choice((100, 200, 300)), rng.choice((100, 200, 300)),
                          rng.randrange(3)), rotation_degrees=rng.choice((0, 0, 90)))
              for i in range(n)]
    orders = [[v.path] for v in values]
    sizes = {i: rng.choice(('S', 'M', 'L')) for i in range(n)}
    for i in range(0, n, 17):
        orders[i] = [values[i].path, values[i].path]
    pending = sorted(range(n), key=lambda i: (sizes[i], -values[i].footprint_height))
    return orders, {v.path: v for v in values}, ([], pending, sizes)


def test_index_preserves_exact_greedy_sequence():
    for seed in range(50):
        orders, items, prepared = geometry(160, seed)
        settings = LayoutSettings(dpi=25.4, cutter_knife_mm=100+seed*7)
        lanes = _lanes(settings, 580)
        assert sequence.arrange_orders(orders, items, lanes, settings, prepared) == old_sequence(
            orders, items, lanes, prepared)


def test_repeated_geometry_avoids_quadratic_pair_scans(monkeypatch):
    values = [item(i, 200, 200) for i in range(1000)]
    orders, items = [[v.path] for v in values], {v.path: v for v in values}
    prepared = ([], list(range(1000)), dict.fromkeys(range(1000), 'M'))
    original, calls = sequence.horizontal_savings, []
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(sequence, 'horizontal_savings', counted)
    settings = LayoutSettings(dpi=25.4, cutter_knife_mm=290)
    result = sequence.arrange_orders(orders, items, _lanes(settings, 580), settings, prepared)
    assert result == list(range(1000)) and len(calls) == 500


def test_identity_shared_snapshot_and_final_change_detection(tmp_path, monkeypatch):
    path = tmp_path/'source.png'
    path.write_bytes(b'first')
    original, calls = measurements.fresh_identity, []
    def counted(p):
        calls.append(p)
        return original(p)
    monkeypatch.setattr(measurements, 'fresh_identity', counted)
    from contextvars import copy_context
    with measurements.measurement_session():
        with ThreadPoolExecutor(4) as pool:
            values = list(pool.map(lambda ctx: ctx.run(measurements.identity, path),
                                   [copy_context() for _ in range(100)]))
        assert len(set(values)) == 1 and len(calls) == 1
        measurements.verify_sources()
        assert len(calls) == 2
        path.write_bytes(b'changed-source')
        with pytest.raises(ValueError, match='发生变化'):
            measurements.verify_sources()
    assert measurements.identity(path) != values[0]


def test_normal_baseline_computed_once_with_effective_knife():
    calls = []
    def compute(paths, settings, report, prepared):
        calls.append(settings)
        report('批次刀位已确定', 270, 25.4, '')
        return ('plan',)
    cache = NormalPlans(compute)
    config = LayoutSettings(dpi=25.4, cutter_rotation_zone=True)
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: cache.get(600, [], config, lambda *a: None, ([], {})), range(20)))
    assert len(calls) == 1 and not calls[0].cutter_rotation_zone
    assert all(r[0] == ('plan',) and r[1].cutter_knife_mm == 270 for r in results)


def test_different_files_metadata_queries_remain_parallel(tmp_path, monkeypatch):
    from threading import Barrier
    from contextvars import copy_context
    paths = [tmp_path/str(i) for i in range(4)]
    for p in paths:
        p.write_bytes(b'data')
    original, barrier = measurements.fresh_identity, Barrier(4)
    def together(p):
        barrier.wait(timeout=3)
        return original(p)
    monkeypatch.setattr(measurements, 'fresh_identity', together)
    with measurements.measurement_session():
        with ThreadPoolExecutor(4) as pool:
            futures = [pool.submit(copy_context().run, measurements.identity, p) for p in paths]
            assert len([f.result() for f in futures]) == 4


def test_invalid_normal_and_unexpected_failure_reach_all_followers():
    for error in (ValueError('no normal'), RuntimeError('unexpected')):
        def compute(*a, **kw):
            raise error
        cache = NormalPlans(compute)
        if isinstance(error, ValueError):
            assert cache.get(450, [], LayoutSettings(), lambda *a: None, None)[2] == 'no normal'
        else:
            for _ in range(2):
                with pytest.raises(RuntimeError, match='unexpected'):
                    cache.get(450, [], LayoutSettings(), lambda *a: None, None)


def test_batch_label_bands_survive_global_cache_eviction(tmp_path, monkeypatch):
    from automatic_print.layout_engine import cut_guide_geometry as guides
    calls = []
    def cached(path, mtime, size):
        calls.append(path)
        return None if len(calls) % 2 else 'band'
    monkeypatch.setattr(guides, '_cached', cached)
    paths = [tmp_path/str(i) for i in range(600)]
    for path in paths:
        path.write_bytes(b'header')
    with measurements.measurement_session():
        first = [guides.detect_guide_band(p) for p in paths]
        second = [guides.detect_guide_band(p) for p in paths]
        assert first == second and len(calls) == 600
