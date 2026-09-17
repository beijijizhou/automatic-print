import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import pytest
from PIL import Image
import numpy as np

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.output.batch_footer import footer_sprite
from automatic_print.layout_engine.cutting.validation.marked_pixel_validation import validate_marked_pillow
from automatic_print.layout_engine.cutting.geometry.printed_guides import vips_corridor_is_clear


def sources(root):
    paths = []
    for order in range(6):
        size, width, height = ('M', 150, 200) if order < 3 else ('3XL', 300, 500)
        for face in (1, 2):
            path = root/f'B{order}-1-T-Black-{size}-NO1-{face}.png'
            image = Image.new('RGBA', (width, height))
            x = 0 if order%2 else width-100
            image.paste('white', (x, 0, x+100, 45))
            image.paste('blue', (0, 70, width, height))
            image.save(path, dpi=(25.4,25.4))
            paths.append(path)
    return paths


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('parts', [1, 3])
def test_footer_and_cut_spacing_preserve_full_batch_pixels_and_zones(tmp_path, engine, parts):
    paths = sources(tmp_path)
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual',
        cutter_auto_knife=True, cutter_rotation_zone=True, platform_name='隆丰',
        platform_font_height_mm=6, transition_lines=True, transition_gap_mm=10,
        batch_footer_enabled=True, batch_footer_font_mm=8,
        output_parts=parts, png_engine=engine, save_memory_unlimited=True)
    result = generate_layout(paths, tmp_path/'out', settings)
    assert {'常规区', '旋转区'} == {p['cut_zone'] for p in result['placements']}
    for part in result.get('parts') or [result]:
        footer, line = part['transition_marks']
        assert footer['kind'] == '批次信息'
        assert '批次6单' in footer['text']
        assert '并排区/常规区' in footer['text']
        assert '旋转区' in footer['text']
        content = max(max(p['y_px']+p['height_px'],
            p['number_y_px']+p['number_height_px'],
            p['platform_y_px']+p['platform_height_px'],
            p['color_block_y_px']+p['color_block_height_px']) for p in part['placements'])
        assert footer['y'] >= content+10
        assert line['y'] == footer['y']+footer['height']+10
        with Image.open(tmp_path/'out'/part['filename']) as output:
            assert line['y']+line['height'] <= output.height
            assert output.getpixel((0, line['y'])) == (255,0,0,255)
            assert output.crop((0, footer['y'], footer['width'], footer['y']+footer['height'])).getchannel('A').getbbox()
            for p in part['placements']:
                with Image.open(tmp_path/p['source']) as original:
                    source = np.asarray(original.rotate(p['rotation_degrees'], expand=True))
                actual = np.asarray(output.crop((p['x_px'],p['y_px'],p['x_px']+p['width_px'],p['y_px']+p['height_px'])))
                assert np.array_equal(actual[source[:,:,3] == 255], source[source[:,:,3] == 255])
        assert all(z['pixel_verified'] for z in part['cut_corridor'].get('zones', [part['cut_corridor']]))


def test_footer_mask_rejects_ink_in_glyph_whitespace_for_both_engines():
    r = {'x':0, 'y':10, 'width':100, 'height':1, 'text':'批次结束',
         'dpi':100, 'font_mm':4, 'max_width':100}
    with footer_sprite(r) as sprite:
        r['width'], r['height'] = sprite.size
        canvas = Image.new('RGBA', (100, r['height']+20))
        canvas.alpha_composite(sprite, (0,10))
        pixels = np.asarray(sprite)
        y,x = np.argwhere(pixels[:,:,3] == 0)[0]
    check = {'safe_left_px':0, 'safe_right_px':100}
    validate_marked_pillow(canvas, check, rectangles=[r])
    pyvips = pytest.importorskip('pyvips')
    clean = pyvips.Image.new_from_memory(canvas.tobytes(), *canvas.size, 4, 'uchar')
    assert vips_corridor_is_clear(clean, check, rectangles=[r])
    canvas.putpixel((int(x),int(y)+10), (255,0,0,255))
    with pytest.raises(ValueError, match='禁止输出'):
        validate_marked_pillow(canvas, check, rectangles=[r])
    image = pyvips.Image.new_from_memory(canvas.tobytes(), *canvas.size, 4, 'uchar')
    assert not vips_corridor_is_clear(image, check, rectangles=[r])


def test_footer_preferences_migrate_once_and_remember_custom_gap(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from automatic_print.ui.transition_settings import TransitionSettings
    app = QApplication.instance() or QApplication([])
    prefs = QSettings(str(tmp_path/'settings.ini'), QSettings.IniFormat)
    prefs.setValue('cutter/transition_gap_mm', 3)
    prefs.setValue('cutter/batch_footer_enabled', True)
    first = TransitionSettings(prefs)
    assert not first.footer.isChecked() and first.gap.value() == 10
    first.footer.setChecked(True)
    first.gap.setValue(7)
    first.footer_font.setValue(5)
    second = TransitionSettings(prefs)
    assert second.gap.value() == 7 and second.footer_font.value() == 5
    assert second.footer.isChecked()
    first.close()
    second.close()


def test_footer_can_be_enabled_without_red_line(tmp_path):
    from automatic_print.layout_engine.cutting.geometry.transition_marks import transition_rects
    from automatic_print.layout_engine.domain.models import Placement
    p = Placement('a.png', 1, 0, 0, 100, 80, 0, 0, 0, 0, 0, 100, 80)
    rects = transition_rects([(tmp_path/'a.png', p)],
        LayoutSettings(dpi=25.4, transition_lines=False, batch_footer_enabled=True), 200)
    assert len(rects) == 1 and rects[0]['kind'] == '批次信息'
