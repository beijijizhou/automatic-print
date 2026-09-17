import numpy as np
import pytest
from contextlib import contextmanager
from PIL import Image, ImageFile

from automatic_print.layout_engine.labeling.markers.marker_space import transparent_rect
from automatic_print.layout_engine.measurement.measurement_session import measuring_source
from automatic_print.layout_engine.labeling.platform.transparent_search import clear_rectangles


@pytest.mark.parametrize('degrees', [0, 90, -90, 180])
@pytest.mark.parametrize('vertical', [False, True])
def test_projection_matches_independent_pixel_checks(tmp_path, degrees, vertical):
    data = np.zeros((101, 153, 4), dtype=np.uint8)
    data[21:49, 30:65, 3] = 1  # Even faint alpha must block placement.
    data[71:83, 100:110, 3] = 255
    path = tmp_path / 'source.png'
    Image.fromarray(data).save(path)
    width, height = (217, 329) if degrees % 180 else (329, 217)
    rectangles = [(15 if vertical else n, n if vertical else 15, 21, 23)
                  for n in range(-5, max(width, height)+1, 3)]
    rectangles.extend([(0, 0, 0, 10), (0, 0, 10, 0)])
    with measuring_source(path):
        expected = tuple(transparent_rect(path, width, height, degrees, rect)
                         for rect in rectangles)
        assert clear_rectangles(path, width, height, degrees, rectangles,
                                vertical=vertical) == expected


def test_candidate_checks_crop_one_strip(tmp_path, monkeypatch):
    path = tmp_path / 'source.png'
    Image.new('RGBA', (1000, 200)).save(path)
    original = Image.Image.crop
    calls = []

    def crop(source, box=None):
        calls.append(box)
        return original(source, box)

    monkeypatch.setattr(Image.Image, 'crop', crop)
    rects = [(x, 0, 20, 20) for x in range(500)]
    assert all(clear_rectangles(path, 1000, 200, 0, rects))
    assert len(calls) == 1


def test_non_alpha_sources_remain_unsafe(tmp_path):
    path = tmp_path / 'source.png'
    Image.new('RGB', (100, 100), 'white').save(path)
    assert clear_rectangles(path, 100, 100, 0,
                            [(0, 0, 20, 20), (0, 0, 0, 20)]) == (False, True)


def test_transparent_rectangle_persists_across_batch_sessions(
    tmp_path, monkeypatch,
):
    from automatic_print.layout_engine.labeling.markers import marker_space
    from automatic_print.layout_engine.measurement import measurement_cache
    from automatic_print.layout_engine.measurement.measurement_session import measurement_session

    path = tmp_path / 'source.png'
    Image.new('RGBA', (100, 100)).save(path)
    monkeypatch.setattr(measurement_cache, 'cache_directory', lambda: tmp_path)
    original = marker_space.source_pixels
    reads = []

    @contextmanager
    def counted(source):
        reads.append(source)
        with original(source) as image:
            yield image

    monkeypatch.setattr(marker_space, 'source_pixels', counted)
    with measurement_session():
        assert marker_space.transparent_rect(
            path, 100, 100, 0, (0, 0, 20, 20)
        )
    with measurement_session():
        assert marker_space.transparent_rect(
            path, 100, 100, 0, (0, 0, 20, 20)
        )

    assert reads == [path]


def test_normal_rotation_decode_once_and_cached_comparison_opens_nothing(tmp_path, monkeypatch):
    from automatic_print.layout_engine.intake.preparation.item_factory import read_items
    from automatic_print.layout_engine.domain.models import LayoutSettings
    from automatic_print.layout_engine.measurement.measurement_session import measurement_session

    path = tmp_path / 'source.png'
    Image.new('RGBA', (200, 300), 'blue').save(path, dpi=(25.4, 25.4))
    original = ImageFile.ImageFile.load
    decodes = []

    def load(source, *args, **kwargs):
        if source.fp is not None:
            decodes.append(source.filename)
        return original(source, *args, **kwargs)

    monkeypatch.setattr(ImageFile.ImageFile, 'load', load)
    settings = LayoutSettings(dpi=25.4, cutter_mode='dual', allow_rotation=True)
    with measurement_session():
        first = read_items([path], settings, None)
        assert len(first[0][0]) == 2
        assert len(decodes) == 1

        def forbidden(*args, **kwargs):
            raise AssertionError('Cached geometry must not open a PNG')

        monkeypatch.setattr(Image, 'open', forbidden)
        assert read_items([path], settings, None) == first
