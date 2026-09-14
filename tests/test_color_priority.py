import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import pytest
from PIL import Image
import numpy as np
from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.order_groups import ordered_paths
from automatic_print.layout_engine.source_metadata import source_color,source_size,source_block


def test_color_aliases_and_multicolor_order_stays_together():
    assert source_color(Path('B1-1-T-Black-M-NO1-1.png'))=='黑色'
    assert source_color(Path('B1-1-T-白色-M-NO1-1.png'))=='白色'
    names=['B1-3-A-White-S-NO1-1.png','B1-1-A-Black-XL-NO1-1.png',
           'B1-2-Z-黑色-M-NO1-1.png']
    assert [source_block(p) for p in ordered_paths([Path(n) for n in names])]==[
        ('黑色','M'),('黑色','XL'),('白色','S')]


def test_uniform_color_multis_and_singles_group_without_splitting_orders():
    names=['W1-1-A-White-S-NO1-1.png','W1-2-A-White-M-NO1-1.png',
           'B1-1-A-Black-L-NO1-1.png','B2-1-A-Black-M-NO1-1.png',
           'B2-2-A-Black-XL-NO1-1.png','W2-1-A-White-L-NO1-1.png']
    result=ordered_paths([Path(n) for n in names])
    assert [source_color(p) for p in result]==['黑色']*3+['白色']*3
    from automatic_print.layout_engine.order_groups import complete_orders
    assert sorted(map(len,complete_orders(result)))==[1,1,2,2]


@pytest.mark.parametrize('mode',['single','dual'])
@pytest.mark.parametrize('engine',['pillow','libvips'])
@pytest.mark.parametrize('fast', [False, True])
def test_saved_batch_groups_color_before_size_with_complete_double_sides(tmp_path,mode,engine,fast):
    paths=[]
    for order,(color,size) in enumerate([('White','L'),('Black','XL'),('白色','S'),('黑色','M')]):
        for face in (1,2):
            path=tmp_path/f'B{order}-1-T-{color}-{size}-NO1-{face}.png'
            with Image.new('RGBA',(100,100)) as image:
                image.paste('white',(0,0,70,25))
                image.paste('blue',(0,50,100,100))
                image.save(path,dpi=(25.4,25.4))
            paths.append(path)
    settings=LayoutSettings(dpi=25.4,media_width_mm=580,cutter_mode=mode,
        cutter_auto_knife=True,cutter_single_row_rotation=True,
        cutter_compare_whole_rotation=True,cutter_left_marker_external=True,
        cutter_left_marker_lift_mm=1.5,preserve_header_gap=True,cutter_knife_dots=False,
        png_engine=engine,png_fast_encoding=fast,output_parts=3,save_memory_unlimited=True)
    result=generate_layout(paths,tmp_path/'out',settings)
    if fast:
        assert all('原生快速PNG' in part['png_save_details']['encoder'] for part in result['parts'])
    actual=[source_block(Path(p['source'])) for p in result['placements']]
    assert actual==[block for block in [('黑色','M'),('黑色','XL'),('白色','S'),('白色','L')] for _ in range(2)]
    for part in result.get('parts') or [result]:
        if mode=='dual':
            assert all(z['pixel_verified'] for z in part['cut_corridor'].get('zones',[part['cut_corridor']]))
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for p in part['placements']:
                with Image.open(tmp_path/p['source']) as source:
                    source=source.convert('RGBA')
                    source=source.rotate(p['rotation_degrees'],expand=True)
                    expected=np.asarray(source)
                    actual=np.asarray(output.convert('RGBA').crop((p['x_px'],p['y_px'],
                        p['x_px']+source.width,p['y_px']+source.height)))
                    mask=expected[:,:,3]>0
                    assert np.array_equal(actual[mask],expected[mask])
