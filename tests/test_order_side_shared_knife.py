"""The opt-in shared knife route does not change the old workflow."""
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from automatic_print.automation.workflows.shared_knife_batches import render_shared_knife_batches
from automatic_print.layout_engine.domain.models import LayoutSettings
from automatic_print.layout_engine.orders.order_groups import order_key
from automatic_print.layout_engine.rendering.storage.plan_partition import partition_plan


def _source(folder, order, number, width, size, side=1):
    path = folder / f'{order}-{number}-T-Black-{size}-NO1-{side}.png'
    Image.new('RGB', (width, 140), 'blue').save(path, dpi=(25.4, 25.4))
    return path


def test_explicit_order_side_routes_unfit_whole_order_to_rotation(tmp_path):
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual', cutter_knife_mm=300,
        number_images=False, margin_mm=0, platform_name='隆丰',
        png_engine='pillow', color_block_gap_mm=5, output_parts=1,
    )
    prepared = []
    for batch in ('批次甲', '批次乙'):
        folder = tmp_path / batch
        folder.mkdir()
        paths = [
            _source(folder, 'A', 1, 280, 'M', 1),
            _source(folder, 'A', 1, 280, 'M', 2),
            _source(folder, 'A', 2, 280, 'XL'),
            _source(folder, 'B', 1, 180, 'S'),
            _source(folder, 'C', 1, 400, '3XL'),
            _source(folder, 'C', 2, 400, '3XL'),
        ]
        prepared.append((folder, paths))
    report = render_shared_knife_batches(
        tmp_path / '隆丰', '隆丰', prepared, settings,
        lambda _message: None, order_side=True)
    assert not report['layout_errors']
    assert report['shared_knife_mm'] == 300
    for batch, result in report['batches']:
        routes = report['batch_routes'][batch]['parts']
        assert {Path(route['folder']).parts[0] for route in routes} == {
            '常规', '旋转'}
        assert result['order_check']['orders'] == 3
        assert result['cut_corridor']['pixel_verified']
        assert any('共刀并排等比缩小' in notice[1]
                   for notice in result['analysis']['width_adjustments'])
        output_root = Path(report['output_folder'])
        for route in routes:
            with Image.open(output_root / route['folder'] / route['filename']) as image:
                assert image.mode == 'RGBA'
        zones = {}
        for placement in result['placements']:
            zones.setdefault(order_key(Path(placement['source'])), set()).add(
                placement['cut_zone'])
        assert zones['a'] == zones['b'] == {'并排区'}
        assert zones['c'] == {'旋转区'}


def test_same_knife_still_separates_rotation_and_normal_files():
    planned = [
        (Path('A-1-T-Black-M-NO1-1.png'), SimpleNamespace(
            row_y_px=10, footprint_height_px=40, cut_knife_xs_px=(300,),
            cut_zone='并排区')),
        (Path('B-1-T-Black-3XL-NO1-1.png'), SimpleNamespace(
            row_y_px=60, footprint_height_px=40, cut_knife_xs_px=(300,),
            cut_zone='旋转区')),
    ]
    parts = partition_plan(planned, 1, split_by_knife=True)
    assert len(parts) == 2
    assert [[path for path, _placement in part] for part in parts] == [
        [planned[0][0]], [planned[1][0]]]
