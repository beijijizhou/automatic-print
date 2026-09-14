from threading import Barrier, Thread
from PIL import Image
from automatic_print.layout_engine import labels, platform_space
from automatic_print.layout_engine.membrane_region import MembraneRegion


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
    from automatic_print.layout_engine import rotated_marks
    from automatic_print.layout import LayoutSettings
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
    assert result == (0, 0, 0, 92)


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
