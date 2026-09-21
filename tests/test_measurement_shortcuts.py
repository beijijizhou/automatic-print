from threading import Barrier, Thread
import random
import numpy as np
from PIL import Image
from automatic_print.layout_engine.labeling.base import labels
from automatic_print.layout_engine.labeling.platform import platform_space
from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion


def test_vector_card_search_matches_original_pixel_order_and_reservations():
    rng = random.Random(19)
    for _ in range(120):
        width, height = rng.randint(2, 22), rng.randint(2, 18)
        box_width, box_height = rng.randint(1, width), rng.randint(1, height)
        blocked = np.array([
            [rng.randrange(4) == 0 for _x in range(width)]
            for _y in range(height)
        ], dtype=np.int32)
        integral = np.pad(blocked, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
        reserved = tuple(
            (x, y, x+rng.randint(1, 6), y+rng.randint(1, 6))
            for x, y in ((rng.randrange(width), rng.randrange(height))
                         for _entry in range(rng.randrange(4)))
        )
        expected = None
        for y in range(height-box_height+1):
            for x in range(width-box_width+1):
                if any(x < rx2 and x+box_width > rx1 and y < ry2
                       and y+box_height > ry1 for rx1, ry1, rx2, ry2 in reserved):
                    continue
                if not blocked[y:y+box_height, x:x+box_width].any():
                    expected = (x, y)
                    break
            if expected is not None:
                break
        assert platform_space._first_clear_card_rect(
            integral, width, height, box_width, box_height, reserved,
        ) == expected


def test_nearby_clear_space_skips_full_header_search(tmp_path, monkeypatch):
    path = tmp_path/'source.png'
    Image.new('RGBA', (300, 200)).save(path)
    monkeypatch.setattr(platform_space, '_free_band_candidates',
                        lambda *_: (_ for _ in ()).throw(AssertionError('Unnecessary header scan')))
    result = platform_space.header_space(path, MembraneRegion(.2, 0, .4, .2),
                                        300, 200, 20, 20, 5, 0)
    assert result == 125


def test_blank_header_checks_only_nearest_candidate(tmp_path, monkeypatch):
    path = tmp_path/'source.png'
    Image.new('RGBA', (300, 200)).save(path)
    original, checked = platform_space.clear_rectangles, []
    def counted(*args, **kwargs):
        rectangles = tuple(args[4])
        checked.append(len(rectangles))
        return original(*args[:4], rectangles, **kwargs)
    monkeypatch.setattr(platform_space, 'clear_rectangles', counted)
    assert platform_space.header_space(path, MembraneRegion(.2, 0, .4, .2),
                                       300, 200, 20, 20, 5, 0) == 125
    assert checked == [1]


def test_blank_rotated_header_does_not_scan_remaining_image(tmp_path, monkeypatch):
    from automatic_print.layout_engine.cutting.geometry import rotated_marks
    from automatic_print.layout_engine import LayoutSettings
    path = tmp_path/'source.png'
    Image.new('RGBA', (300, 600)).save(path)
    # After left rotation this card lies at the upper left of the output.
    monkeypatch.setattr(rotated_marks, 'detect_guide_band',
                        lambda _: MembraneRegion(.7, 0, 1, .15))
    monkeypatch.setattr(rotated_marks, 'clear_rectangles',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('Scanned entire tail')))
    result = rotated_marks.rotated_marks(path, 600, 300, 90,
        LayoutSettings(dpi=25.4, cutter_mode='dual', number_gap_mm=1),
        (-11, 0, 10, 10), (-11, 11, 10, 10), (0, 0, 0, 0))
    assert result == (0, 0, -11, 11)


def test_font_cache_reuses_within_thread_but_does_not_share_faces(monkeypatch):
    barrier, results = Barrier(2), []
    def run():
        a, b = labels._font(17), labels._font(17)
        assert a is b
        results.append(a)
        barrier.wait(5)
    threads = [Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 2 and results[0] is not results[1]


def test_item_cache_loads_only_requested_keys_in_one_query(tmp_path, monkeypatch):
    from automatic_print.layout_engine.measurement import measurement_cache
    monkeypatch.setattr(measurement_cache, 'cache_directory', lambda: tmp_path)
    cache = measurement_cache.MeasurementCache()
    cache.save('item', 'one', {'value': 1})
    cache.save('item', 'two', {'value': 2})
    cache.close()

    cache = measurement_cache.MeasurementCache()
    statements = []
    cache.connection.set_trace_callback(statements.append)
    assert cache.load_many('item', ('one', 'two', 'missing')) == {
        'one': {'value': 1}, 'two': {'value': 2},
    }
    queries = [sql for sql in statements
               if 'SELECT key, payload FROM measurements' in sql]
    assert len(queries) == 1 and "'missing'" in queries[0]
    cache.close()


def test_unavailable_persistent_cache_is_not_reopened_for_each_image(monkeypatch):
    from automatic_print.layout_engine.measurement import measurement_cache
    from automatic_print.layout_engine.measurement.measurement_session import (
        measurement_session, persistent_cache,
    )
    attempts = []

    def unavailable():
        attempts.append(True)
        raise OSError('cache directory unavailable')

    monkeypatch.setattr(measurement_cache, 'MeasurementCache', unavailable)
    with measurement_session():
        assert persistent_cache().load('item', 'one') is None
        assert persistent_cache().load('item', 'two') is None
    assert len(attempts) == 1


def test_item_geometry_cache_is_shared_by_png_and_tiff():
    from dataclasses import replace
    from automatic_print.layout_engine import LayoutSettings
    from automatic_print.layout_engine.measurement.measurement_cache import item_settings
    png = LayoutSettings(output_format='png', png_compression_level=1)
    tiff = replace(png, output_format='tiff', png_compression_level=3)
    assert item_settings(png) == item_settings(tiff)


def test_item_key_ignores_developer_only_batch_packing_switch():
    from dataclasses import replace
    from datetime import datetime, timezone
    from automatic_print.layout_engine import LayoutSettings
    from automatic_print.layout_engine.measurement.measurement_cache import (
        item_key,
        item_settings,
    )
    production = item_settings(LayoutSettings())
    developer = item_settings(replace(
        LayoutSettings(), developer_compact_cutter_layout=True,
    ))
    created = datetime(2026, 9, 17, tzinfo=timezone.utc)

    assert item_key(('a.png', 1, 2), 1, 100, 200, production, 0, created) == item_key(
        ('a.png', 1, 2), 1, 100, 200, developer, 0, created,
    )


def test_card_pixels_are_extracted_once_for_multiple_badge_sizes(tmp_path, monkeypatch):
    from automatic_print.layout_engine.labeling.platform import platform_space
    from automatic_print.layout_engine.measurement.measurement_session import measurement_session
    path = tmp_path/'source.png'
    Image.new('RGBA', (300, 200), 'white').save(path)
    original, calls = platform_space.source_pixels, []

    from contextlib import contextmanager
    @contextmanager
    def counted(source):
        calls.append(source)
        with original(source) as image:
            yield image

    monkeypatch.setattr(platform_space, 'source_pixels', counted)
    card = MembraneRegion(0, 0, 1, 1)
    with measurement_session():
        assert platform_space.card_space(path, card, 300, 200, 20, 10) is not None
        assert platform_space.card_space(path, card, 300, 200, 40, 20) is not None
    assert calls == [path]
