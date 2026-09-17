from dataclasses import replace
from threading import current_thread, get_ident
from pathlib import Path

from PIL import Image, ImageFile
import pytest
import numpy as np

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.planning.film import film_comparison
from automatic_print.layout_engine.measurement.measurement_session import measurement_session
from automatic_print.layout_engine.intake.preparation.item_factory import read_items
from automatic_print.layout_engine.domain.models import Placement
from automatic_print.layout_engine.cutting.geometry.printed_guides import collect_guides, dot_boxes
from automatic_print.layout_engine.cutting.validation.marked_pixel_validation import validate_marked_pillow


def qr_sources(tmp_path):
    cv2 = pytest.importorskip('cv2')
    qr = Image.fromarray(cv2.QRCodeEncoder_create().encode('FILM123')).convert('RGBA')
    paths = []
    for i in range(12):
        rotated = Image.new('RGBA', (250, 300))
        top = 10 if i < 6 else 150
        rotated.paste('white', (35, top, 100, top+45))
        rotated.paste(qr, (45, top+10))
        rotated.paste('blue', (115, 0, 250, 300))
        path = tmp_path/f'B{i//2}-1-T-Black-M-NO1-{i%2+1}.png'
        rotated.rotate(-90, expand=True).save(path, dpi=(25.4, 25.4))
        paths.append(path)
    return paths


def settings():
    return LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual',
        cutter_auto_knife=True, allow_rotation=False, platform_name='隆丰',
        platform_font_height_mm=6, label_text_template='CY', label_machine_enabled=True,
        label_sequence_enabled=True, transition_lines=True, compare_reference_films=True)


def test_four_workers_simultaneous_and_no_image_io_after_measurement(tmp_path, monkeypatch):
    paths = qr_sources(tmp_path)
    threads = set()
    def concurrent(fn):
        def run(*args, **kwargs):
            threads.add(get_ident())
            return fn(*args, **kwargs)
        return run
    for name in ('plan_cutter_layout', 'plan_rotation_zones'):
        monkeypatch.setattr(film_comparison, name, concurrent(getattr(film_comparison, name)))
    original = Image.open
    def no_worker_image_io(*args, **kwargs):
        assert not current_thread().name.startswith('film-geometry'), 'Geometry reopened source PNG'
        return original(*args, **kwargs)
    monkeypatch.setattr(Image, 'open', no_worker_image_io)
    result = film_comparison.compare_films(paths, settings())
    assert result['parallelism'] == 4 and 1 <= len(threads) <= 4
    assert all(not row['error'] for row in result['rows'])


def test_rotated_transparent_search_decodes_once_and_reuses_item_results(tmp_path, monkeypatch):
    paths = qr_sources(tmp_path)
    original, decodes = ImageFile.ImageFile.load, []
    def counted(image, *args, **kwargs):
        if image.fp is not None and Path(getattr(image, 'filename', '')) in paths:
            decodes.append(image.filename)
        return original(image, *args, **kwargs)
    monkeypatch.setattr(ImageFile.ImageFile, 'load', counted)
    config = replace(settings(), manual_rotations=tuple((str(p.resolve()), 90) for p in paths))
    with measurement_session():
        first = read_items(paths, config, None)
        count = len(decodes)
        assert count == len(paths)
        second = read_items(paths, replace(config, media_width_mm=430), None)
        assert second == first
        assert len(decodes) == count


def test_shared_normal_baselines_preserve_all_eighteen_results(tmp_path, monkeypatch):
    paths = qr_sources(tmp_path)
    config = replace(settings(), film_geometry_workers=1)
    normal, calls = film_comparison.plan_cutter_layout, []
    def counted(*args, **kwargs):
        calls.append(args[1].media_width_mm)
        return normal(*args, **kwargs)
    monkeypatch.setattr(film_comparison, 'plan_cutter_layout', counted)
    shared = film_comparison.compare_films(paths, config)
    assert len(calls) == len(set(calls)) == 2
    rotation = film_comparison.plan_rotation_zones
    def without_baseline(*args, **kwargs):
        kwargs.pop('normal_baseline', None)
        return rotation(*args, **kwargs)
    monkeypatch.setattr(film_comparison, 'plan_rotation_zones', without_baseline)
    independent = film_comparison.compare_films(paths, config)
    for a, b in zip(shared['rows'], independent['rows']):
        assert {k: v for k, v in a.items() if k != 'seconds'} == {
            k: v for k, v in b.items() if k != 'seconds'}


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_comparison_keeps_actual_selected_batch_pixel_corridors(tmp_path, engine):
    paths = qr_sources(tmp_path)
    result = generate_layout(paths, tmp_path/'out', replace(settings(),
        compare_film_sizes=True, png_engine=engine, output_parts=3, save_memory_unlimited=True))
    assert len(result['analysis']['film_comparison']['rows']) == 4
    for part in result.get('parts', [result]):
        assert part['order_check']
        planned = [(tmp_path/p['source'], Placement(**p)) for p in part['placements']]
        effective = settings()
        spans, _ = collect_guides(planned, effective)
        with Image.open(tmp_path/'out'/part['filename']) as image:
            validate_marked_pillow(image, part['cut_corridor'],
                                   list(dot_boxes(spans, settings().dpi)), part['transition_marks'])
            for zone in part['cut_corridor'].get('zones', [part['cut_corridor']]):
                assert zone['pixel_verified']
            for path, p in planned:
                with Image.open(path) as source:
                    original = np.asarray(source.rotate(p.rotation_degrees, expand=True))
                actual = np.asarray(image.crop((p.x_px, p.y_px,
                                                p.x_px+p.width_px, p.y_px+p.height_px)))
                ink = original[:, :, 3] == 255
                assert np.array_equal(actual[ink], original[ink])
