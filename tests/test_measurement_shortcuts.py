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
