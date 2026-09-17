from pathlib import Path

from PIL import Image
import tifffile

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.cutting.validation import cut_validation


def test_parallel_tiff_preserves_rgba_dpi_and_strips(tmp_path):
    source = tmp_path / 'B1-1-T-Black-M-NO1-1.png'
    Image.new('RGBA', (513, 777), (10, 20, 30, 128)).save(
        source, dpi=(25.4, 25.4))
    result = generate_layout([source], tmp_path / 'out', LayoutSettings(
        dpi=25.4, media_width_mm=600, margin_mm=0, spacing_mm=0,
        number_images=False, color_block_enabled=False, allow_rotation=False,
        output_format='tiff', png_engine='libvips', worker_threads=4,
        png_compression_level=1,
    ))
    output = tmp_path / 'out' / result['filename']
    assert output.suffix == '.tif'
    assert result['output_format'] == 'TIFF'
    assert result['png_engine'] == 'tifffile + imagecodecs'
    assert result['png_save_details']['worker_threads'] == 4
    assert result['png_save_details']['strip_count'] == 1
    assert not output.with_name(output.name + '.未完成').exists()
    with tifffile.TiffFile(output) as tif:
        page = tif.pages[0]
        assert page.shape == (777, 513, 4)
        assert not page.is_tiled and page.rowsperstrip == min(1024, page.imagelength)
        assert page.extrasamples[0].name == 'UNASSALPHA'
        numerator, denominator = page.tags['XResolution'].value
        assert numerator / denominator == 25.4
        pixels = page.asarray(maxworkers=4)
    assert pixels[0, 0].tolist() == [10, 20, 30, 128]
    assert pixels[-1, -1].tolist() == [10, 20, 30, 128]


def test_tiff_names_keep_extension_when_deduplicated(tmp_path):
    from automatic_print.layout_engine.output.output_name import unused_output_path
    (tmp_path / 'batch.tif').touch()
    assert unused_output_path(tmp_path, 'batch.tif').name == 'batch (2).tif'


def test_tiff_cut_validation_uses_random_access(tmp_path, monkeypatch):
    accesses = []
    monkeypatch.setattr(
        'pyvips.Image.new_from_file',
        lambda path, access: accesses.append(access) or object(),
    )
    monkeypatch.setattr(
        'automatic_print.layout_engine.cutting.geometry.printed_guides.vips_corridors_are_clear',
        lambda image, corridors, guide_boxes, transition_rectangles: True,
    )

    cut_validation.validate_vips_output(
        tmp_path / 'batch.tif',
        {'safe_left_px': 10, 'safe_right_px': 20},
    )

    assert accesses == ['random']


def test_tiff_validates_rendered_canvas_without_reopening_output(
    tmp_path, monkeypatch,
):
    source = tmp_path / 'B1-1-T-Black-M-NO1-1.png'
    Image.new('RGBA', (80, 120), 'blue').save(
        source, dpi=(25.4, 25.4)
    )
    monkeypatch.setattr(
        'automatic_print.layout_engine.pipeline.service.validate_vips_output',
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError('TIFF must not be decoded again after saving')
        ),
    )

    result = generate_layout([source], tmp_path / 'out', LayoutSettings(
        dpi=25.4, media_width_mm=200, margin_mm=0, number_images=False,
        color_block_enabled=True, allow_rotation=False,
        output_format='tiff', png_engine='libvips', cutter_mode='dual',
        cutter_knife_mm=100, cutter_auto_knife=False,
    ))

    assert result['cut_corridor']['pixel_verified'] is True


def test_segmented_tiff_keeps_each_parallel_output(tmp_path):
    paths = []
    for index in range(4):
        path = tmp_path / f'B{index}-1-T-Black-M-NO1-1.png'
        Image.new('RGBA', (80, 120), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    result = generate_layout(paths, tmp_path / 'segments', LayoutSettings(
        dpi=25.4, media_width_mm=100, margin_mm=0, number_images=False,
        color_block_enabled=False, allow_rotation=False, output_format='tiff',
        png_engine='libvips', output_parts=2, save_parallelism=2,
        worker_threads=4,
    ))
    assert result['segment_count'] == 2
    assert result['actual_save_parallelism'] == 2
    assert all(name.endswith('.tif') for name in result['files'])
    assert {path.name for path in (tmp_path / 'segments').glob('*.tif')} == set(result['files'])


def test_tiff_output_is_developer_only(tmp_path):
    from test_developer_mode import APP, window
    owner = window(tmp_path / 'prefs.ini')
    assert not owner.output_parallel_form.isRowVisible(owner.output_format)
    owner.developer_mode_checkbox.setChecked(True)
    assert owner.output_parallel_form.isRowVisible(owner.output_format)
    owner.output_format.setCurrentIndex(owner.output_format.findData('tiff'))
    assert owner._layout_settings().output_format == 'tiff'
    owner.developer_mode_checkbox.setChecked(False)
    assert owner.output_format.currentData() == 'png'
    assert owner._layout_settings().output_format == 'png'
    owner.close()
    APP.processEvents()
