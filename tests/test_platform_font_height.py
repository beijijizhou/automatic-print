import pytest
from PIL import Image
from automatic_print.layout_engine import generate_layout
from test_platform_labels import qr_image, settings


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_manual_platform_height_changes_geometry_and_saved_pixels(tmp_path, engine):
    paths = [qr_image(tmp_path/f'B{i}-1-T-Black-M-NO1-1.png') for i in range(12)]
    results = []
    for height in (6, 12):
        result = generate_layout(paths, tmp_path/f'out{height}', settings(
            png_engine=engine, platform_font_height_mm=height))
        results.append(result)
        assert result['cut_corridor']['pixel_verified']
        with Image.open(tmp_path/f'out{height}'/result['filename']) as output:
            for p in result['placements']:
                assert p['platform_height_px'] == height
                crop = output.crop((p['platform_x_px'], p['platform_y_px'],
                    p['platform_x_px']+p['platform_width_px'],
                    p['platform_y_px']+p['platform_height_px']))
                assert crop.getchannel('A').getbbox()
    assert results[0]['placements'][0]['platform_width_px'] < results[1]['placements'][0]['platform_width_px']
