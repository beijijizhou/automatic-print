import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from dataclasses import replace
import numpy as np
import pytest
from PIL import Image
from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.planner import plan_layout


def sources(root, double=False):
    paths=[]
    for order in range(4):
        for face in ((1,2) if double else (1,)):
            path=root/f'B{order}-1-T-Black-M-NO1-{face}.png'
            with Image.new('RGBA',(80,250)) as image:
                image.paste('white',(0,0,50,25))
                image.paste('blue',(0,70,80,250))
                image.save(path,dpi=(25.4,25.4))
            paths.append(path)
    return paths


def config():
    return LayoutSettings(dpi=25.4,media_width_mm=580,cutter_mode='dual',
        cutter_auto_knife=True,cutter_tail_rotation=False,cutter_rotation_zone=False,
        cutter_compare_whole_rotation=True,cutter_left_marker_external=True,
        cutter_knife_dots=False,
        cutter_left_marker_lift_mm=1.5,preserve_header_gap=True,
        platform_name='隆丰',platform_font_height_mm=6)


def test_fast_path_keeps_more_efficient_automatic_columns(tmp_path):
    paths=sources(tmp_path)
    settings=config()
    normal=plan_layout(paths,replace(settings,cutter_compare_whole_rotation=False),None)
    rotated=plan_layout(paths,settings,None)
    assert len({p.row_y_px for _,p in normal[0]})==1
    assert {p.cut_column_count for _, p in normal[0]} == {4}
    assert all(p.rotation_degrees==0 for _,p in rotated[0])
    assert rotated[3] == normal[3]


def test_gap_validator_rejects_text_moved_inside_rotated_source(tmp_path):
    from automatic_print.layout_engine.marker_space import validate_embedded_marks
    paths=sources(tmp_path)
    settings=config()
    plan=plan_layout(paths,settings,None)
    path,p=plan[0][0]
    unsafe=replace(p,number_x_px=p.x_px+40,number_y_px=p.y_px+10)
    with pytest.raises(ValueError,match='禁用区域|覆盖原图'):
        validate_embedded_marks([(path,unsafe)],settings)


def test_film_comparison_includes_whole_rotation_not_only_tail(tmp_path):
    from automatic_print.layout_engine.film_comparison import compare_films
    report=compare_films(sources(tmp_path),config())
    rows=report['rows']
    normal=next(r for r in rows if r['film_mm']==600 and not r['rotation_allowed'])
    rotated=next(r for r in rows if r['film_mm']==600 and r['rotation_allowed'])
    assert not normal['error'] and not rotated['error']
    assert rotated['rotated_images']==0
    assert rotated['length_m']==normal['length_m']


@pytest.mark.parametrize('engine',['pillow','libvips'])
def test_unsafe_double_order_rotation_falls_back_and_saved_parts_are_safe(tmp_path,engine):
    paths=sources(tmp_path,double=True)
    settings=replace(config(),png_engine=engine,output_parts=3,save_memory_unlimited=True)
    result=generate_layout(paths,tmp_path/'out',settings)
    assert all(p['rotation_degrees']==0 for p in result['placements'])
    for part in result.get('parts') or [result]:
        assert part['printed_guides']['dot_count']==0
        assert all(p['color_block_x_px'] in (0, 293) for p in part['placements'])
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for p in part['placements']:
                with Image.open(tmp_path/p['source']) as source:
                    expected=np.asarray(source)
                actual=np.asarray(output.crop((p['x_px'],p['y_px'],p['x_px']+p['width_px'],p['y_px']+p['height_px'])))
                assert np.array_equal(actual[expected[:,:,3]==255],expected[expected[:,:,3]==255])
        assert all(z['pixel_verified'] for z in part['cut_corridor']['zones'])
