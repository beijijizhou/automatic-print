from PIL import Image
import pytest
from automatic_print.layout import generate_layout
from automatic_print.layout_engine.cut_guide_geometry import detect_guide_band
from test_platform_labels import settings, qr_image
from automatic_print.layout_engine.output_sizes import cutting_report
from automatic_print.layout_engine.cut_validation import corridor_checks


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('side', ['left', 'right'])
def test_entire_batch_reuses_header_without_losing_pairs(tmp_path, engine, side):
    cv2 = pytest.importorskip('cv2')
    qr = Image.fromarray(cv2.QRCodeEncoder_create().encode('TEST123')).convert('RGBA')
    paths = []
    for index in range(12):
        path = tmp_path/f'B{index}-1-T-Black-M-NO1-1.png'
        image = Image.new('RGBA', (270, 250))
        card_x = 0 if side == 'left' else 160
        image.paste('white', (card_x, 0, card_x+110, 60))
        image.paste(qr, (card_x+75, 10))
        image.paste('blue', (0, 70, 270, 250))
        image.save(path, dpi=(25.4, 25.4))
        paths.append(path)
    result = generate_layout(paths, tmp_path/'out', settings(png_engine=engine,
        cutter_auto_knife=True, media_width_mm=580))
    rows = {}
    with Image.open(tmp_path/'out'/result['filename']) as output:
        for p in result['placements']:
            rows.setdefault(p['row_y_px'], []).append(p)
            assert p['x_px'] <= p['platform_x_px']
            assert p['platform_x_px']+p['platform_width_px'] <= p['x_px']+p['width_px']
            assert p['platform_y_px']+p['platform_height_px'] <= p['y_px']+70
            box = (p['platform_x_px'], p['platform_y_px'],
                p['platform_x_px']+p['platform_width_px'],
                p['platform_y_px']+p['platform_height_px'])
            assert output.crop(box).getchannel('A').getbbox()
        assert all(len(row) == 2 for row in rows.values())
        for corridor in corridor_checks(result['cut_corridor']):
            stripe = output.crop((corridor['safe_left_px'], corridor.get('start_y_px', 0),
                corridor['safe_right_px'], corridor.get('end_y_px', output.height)))
            assert all(pixel[3] == 0 or pixel[:3] == (255, 0, 0) for pixel in stripe.getdata())
        # The renderer independently validates the exact printed dot mask.
    assert result['cut_corridor']['pixel_verified']
    assert result['dual_quality']['paired_rows'] == 6
    assert not result['dual_quality']['needs_review']


def test_single_rows_are_not_reported_as_good_dual_layout(tmp_path):
    paths = []
    for index in range(2):
        path = qr_image(tmp_path/f'B{index}-1-T-Black-M-NO1-1.png')
        with Image.open(path) as original:
            wide = Image.new('RGBA', (330, 250), 'blue')
            wide.paste(original, (0, 0))
        wide.save(path, dpi=(25.4, 25.4))
        paths.append(path)
    result = generate_layout(paths, tmp_path/'out', settings(cutter_auto_knife=True))
    quality = result['dual_quality']
    assert quality['paired_rows'] == 0
    assert len(quality['single_images']) == 2
    assert quality['needs_review']
    assert all(p['platform_external'] for p in quality['single_images'])
    assert '未达到全双排预期' in cutting_report(result)
