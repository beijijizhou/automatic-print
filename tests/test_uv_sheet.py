from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
import tifffile

from automatic_print.layout_engine.uv import (
    UV_MATERIALS,
    generate_uv_sheet,
    plan_uv_sheet,
)
from automatic_print.layout_engine.uv import sheet


def dimensions(width=200, height=300, dpi=150):
    return SimpleNamespace(
        width_mm=width,
        height_mm=height,
        x_dpi=dpi,
        y_dpi=dpi,
        embedded_dpi=True,
    )


def test_uv_material_catalog_uses_supplied_finished_sizes_and_shared_canvas():
    actual = {
        item.label: (
            item.width_mm, item.length_mm,
            item.item_width_mm, item.item_height_mm,
            int(2500 // item.item_width_mm) * int(1300 // item.item_height_mm),
        )
        for item in UV_MATERIALS
    }
    assert actual == {
        '1040': (102, 402, 102, 402, 72),
        '2030铁': (202, 302, 302, 202, 48),
        '2030铝': (202, 302, 302, 202, 48),
        '2030木板': (202, 302, 302, 202, 48),
        '圆铁': (201, 201, 201, 201, 72),
        '原铝': (199, 199, 199, 199, 72),
        '3040': (302, 402, 302, 402, 24),
        '挂钟2525': (252, 252, 252, 252, 45),
        '挂钟3030': (302, 302, 302, 302, 32),
        '车牌': (308, 157, 308, 157, 64),
        '亚克力': (150, 220, 150, 220, 80),
    }


@pytest.mark.parametrize(
    ('material', 'width', 'height', 'expected_rotation'),
    (
        ('1040', 100, 400, 0),
        ('2030_aluminum', 200, 300, 90),
        ('3040', 300, 400, 0),
        ('license_plate', 300, 150, 0),
    ),
)
def test_uv_material_orientation_follows_each_finished_size(
    tmp_path, monkeypatch, material, width, height, expected_rotation
):
    path = tmp_path/'source.png'
    monkeypatch.setattr(sheet, 'discover_images', lambda _folder: [path])
    monkeypatch.setattr(
        sheet, 'print_dimensions',
        lambda _path, _fallback: dimensions(width, height),
    )
    plan = plan_uv_sheet(tmp_path, material)
    placement = plan.placements[0]
    assert placement.rotation_degrees == expected_rotation
    assert placement.x_px + placement.width_px == plan.canvas_width_px
    assert placement.y_px + placement.height_px == plan.canvas_height_px


def test_uv_2030_starts_bottom_right_and_fills_left_then_up(tmp_path, monkeypatch):
    paths = [tmp_path/f'{index:02}.png' for index in range(16)]
    monkeypatch.setattr(sheet, 'discover_images', lambda _folder: paths)
    monkeypatch.setattr(sheet, 'print_dimensions', lambda _path, _fallback: dimensions())

    plan = plan_uv_sheet(tmp_path)

    assert plan.columns == 8 and plan.rows == 2 and plan.capacity == 48
    first, second, ninth = plan.placements[0], plan.placements[1], plan.placements[8]
    assert first.x_px + first.width_px == plan.canvas_width_px
    assert first.y_px + first.height_px == plan.canvas_height_px
    assert second.x_px + second.width_px == first.x_px
    assert ninth.x_px + ninth.width_px == plan.canvas_width_px
    assert ninth.y_px + ninth.height_px == first.y_px
    assert all(item.rotation_degrees == 90 for item in plan.placements)


def test_uv_2030_preserves_batch_when_one_canvas_capacity_is_exceeded(
    tmp_path, monkeypatch
):
    paths = [tmp_path/f'{index:02}.png' for index in range(49)]
    monkeypatch.setattr(sheet, 'discover_images', lambda _folder: paths)
    monkeypatch.setattr(sheet, 'print_dimensions', lambda _path, _fallback: dimensions())
    with pytest.raises(ValueError, match='单画布容量为 48 张'):
        plan_uv_sheet(tmp_path)


def test_uv_render_creates_one_rgba_canvas_with_source_dpi(tmp_path):
    pytest.importorskip('pyvips')
    batch = tmp_path/'2026-09-19-03-04'
    batch.mkdir()
    for index, color in enumerate(('red', 'green', 'blue')):
        image = Image.new('RGBA', (79, 118), color)
        image.save(batch/f'{index}.png', dpi=(10, 10))

    result = generate_uv_sheet(batch)
    plan = plan_uv_sheet(batch)

    output = tmp_path/'UV合成文件'/Path(result['output']).name
    assert output.is_file()
    assert output.suffix == '.tif'
    with tifffile.TiffFile(output) as tif:
        page = tif.pages[0]
        assert (page.imagewidth, page.imagelength) == result['canvas_px']
        assert page.shape[-1] == 4
        assert tif.is_bigtiff
        pixels = page.asarray()
        for placement, expected in zip(
            plan.placements, ((255, 0, 0), (0, 128, 0), (0, 0, 255))
        ):
            center = pixels[
                placement.y_px + placement.height_px // 2,
                placement.x_px + placement.width_px // 2,
            ]
            assert tuple(center[:3]) == expected
            assert center[3] == 255
        assert tuple(pixels[0, 0]) == (0, 0, 0, 0)
    assert result['image_count'] == 3
    assert result['start_corner'] == '右下'
    assert result['fill_direction'] == '同行向左，满行后向上'
    assert result['output_format'] == 'BigTIFF'
