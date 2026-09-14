import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
import numpy as np
import pytest
from PIL import Image

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.cut_validation import validate_cut_corridor
from automatic_print.layout_engine.item_factory import read_items
from automatic_print.layout_engine.left_marker import external_left_item


def sources(root):
    paths = []
    for order in range(6):
        size, w, h = ('M',150,200) if order < 3 else ('3XL',300,500)
        for face in (1,2):
            path = root/f'B{order}-1-T-Black-{size}-NO1-{face}.png'
            with Image.new('RGBA', (w,h)) as image:
                x = 0 if order%2 else w-100
                image.paste('white', (x,0,x+100,45))
                image.paste('blue', (0,70,w,h))
                image.save(path, dpi=(25.4,25.4))
            paths.append(path)
    return paths


@pytest.mark.parametrize('engine', ['pillow','libvips'])
@pytest.mark.parametrize('rotation', [False,True])
def test_full_batch_left_external_right_unchanged_and_pixels_safe(tmp_path, engine, rotation):
    paths = sources(tmp_path)
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual',
        cutter_auto_knife=True, cutter_rotation_zone=rotation,
        cutter_left_marker_external=True, color_block_gap_mm=5,
        platform_name='隆丰', platform_font_height_mm=6,
        output_parts=3, png_engine=engine, save_memory_unlimited=True)
    result = generate_layout(paths,tmp_path/'out',settings)
    right_count = 0
    for part in result.get('parts') or [result]:
        planned = []
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for p in part['placements']:
                if p['color_block_x_px'] == 0:
                    assert p['x_px'] >= p['color_block_width_px']+5
                else:
                    right_count += 1
                    options,_ = read_items([tmp_path/p['source']],replace(settings,
                        allow_rotation=False, manual_rotations=()),None)
                    original = options[0][0]
                    assert p['x_px']-p['color_block_x_px'] == original.image_rx-original.block_rx
                with Image.open(tmp_path/p['source']) as source:
                    expected = np.asarray(source.rotate(p['rotation_degrees'],expand=True))
                actual = np.asarray(output.crop((p['x_px'],p['y_px'],
                    p['x_px']+p['width_px'],p['y_px']+p['height_px'])))
                assert np.array_equal(actual[expected[:,:,3]==255],expected[expected[:,:,3]==255])
        assert all(z['pixel_verified'] for z in part['cut_corridor'].get('zones',[part['cut_corridor']]))
    assert right_count > 0
    if rotation:
        assert any(p['cut_zone']=='旋转区' for p in result['placements'])


def test_external_item_is_idempotent_and_validation_rejects_embedded_left(tmp_path):
    from automatic_print.layout_engine.planner import _place_choice
    from automatic_print.layout_engine.units import UnitChoice, UnitMember
    paths = sources(tmp_path)
    settings = LayoutSettings(dpi=25.4, cutter_mode='single', allow_rotation=False,
                              cutter_left_marker_external=True)
    choices,_ = read_items([paths[0]],settings,None)
    item = external_left_item(choices[0][0])
    assert external_left_item(item)==item
    planned = _place_choice(UnitChoice(item.footprint_width,item.footprint_height,
                                      (UnitMember(item,0,0),),0),0,0)
    validate_cut_corridor(planned,settings,600)
    path,p = planned[0]
    with pytest.raises(ValueError,match='原图外'):
        validate_cut_corridor([(path,replace(p,x_px=0))],settings,600)
