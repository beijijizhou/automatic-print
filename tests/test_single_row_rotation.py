import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
import pytest
from PIL import Image
from automatic_print.layout import LayoutSettings, generate_layout


@pytest.mark.parametrize('engine',['pillow','libvips'])
@pytest.mark.parametrize('fast',[False,True])
def test_single_rows_choose_direction_per_complete_order_without_knife(tmp_path,engine,fast):
    paths=[]
    for order in range(4):
        size,w,h=('M',150,220) if order<2 else ('L',250,120)
        for face in (1,2):
            path=tmp_path/f'B{order}-1-T-Black-{size}-NO1-{face}.png'
            with Image.new('RGBA',(w,h)) as image:
                image.paste('white',(0,0,70,25))
                image.paste('blue',(0,50,w,h))
                image.save(path,dpi=(25.4,25.4))
            paths.append(path)
    settings=LayoutSettings(dpi=25.4,media_width_mm=430,cutter_mode='single',
        cutter_single_row_rotation=True,cutter_compare_whole_rotation=True,
        cutter_left_marker_external=True,cutter_left_marker_lift_mm=1.5,
        preserve_header_gap=True,cutter_knife_dots=False,png_engine=engine,png_fast_encoding=fast,
        output_parts=3,save_memory_unlimited=True,platform_name='隆丰',platform_font_height_mm=6)
    result=generate_layout(paths,tmp_path/'out',settings)
    for part in result.get('parts') or [result]:
        if fast:
            assert '原生快速PNG' in part['png_save_details']['encoder']
        assert part['cutter_knife_mm'] is None and part['cut_corridor'] is None
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for p in part['placements']:
                assert p['rotation_degrees']==(90 if '-M-' in p['source'] else 0)
                assert p['color_block_x_px']==0 and p['cut_knife_x_px'] is None
                with Image.open(tmp_path/p['source']) as original:
                    expected=np.asarray(original.rotate(p['rotation_degrees'],expand=True))
                actual=np.asarray(output.crop((p['x_px'],p['y_px'],p['x_px']+p['width_px'],p['y_px']+p['height_px'])))
                assert np.array_equal(actual[expected[:,:,3]==255],expected[expected[:,:,3]==255])


def test_single_rotation_can_use_full_width_without_second_knife_safety(tmp_path):
    from automatic_print.layout_engine.planner import plan_layout
    path=tmp_path/'B1-1-T-Black-M-NO1-1.png'
    Image.new('RGBA',(80,415),'blue').save(path,dpi=(25.4,25.4))
    settings=LayoutSettings(dpi=25.4,media_width_mm=430,cutter_mode='single',
        cutter_single_row_rotation=True,cutter_compare_whole_rotation=True,
        cutter_left_marker_external=True,cutter_left_marker_lift_mm=1.5,
        cutter_knife_dots=False,preserve_header_gap=True)
    planned,_,width,*_=plan_layout([path],settings,None)
    assert width==430
    assert planned[0][1].rotation_degrees==90
    assert planned[0][1].cut_knife_x_px is None
