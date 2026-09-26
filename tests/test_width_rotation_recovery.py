from PIL import Image
import pytest
from automatic_print.layout_engine import LayoutSettings,generate_layout
from automatic_print.layout_engine.pipeline.validation import validate_plan
from automatic_print.layout_engine.planning.base.planner import plan_layout


@pytest.mark.parametrize('engine',['pillow','libvips'])
@pytest.mark.parametrize('mode',['free','single','dual'])
def test_failed_normal_batch_rotates_without_resizing(tmp_path,engine,mode):
    paths=[]
    for order in range(3):
        for face in (1,2):
            path=tmp_path/f'B{order}-1-T-Black-L-NO1-{face}.png'
            with Image.new('RGBA',(563,234)) as image:
                image.paste('white',(0,0,200,30))
                image.paste((20,50,90,255),(0,70,563,234))
                image.save(path,dpi=(25.4,25.4))
            paths.append(path)
    original=[p.read_bytes() for p in paths]
    plans=[]
    settings=LayoutSettings(dpi=25.4,media_width_mm=430,cutter_mode=mode,
        cutter_auto_knife=True,cutter_compare_whole_rotation=False,cutter_knife_dots=False,
        cutter_left_marker_external=True,cutter_left_marker_lift_mm=1.5,
        preserve_header_gap=(mode!='free'),platform_below_marker=True,
        platform_name='隆丰',platform_font_height_mm=6,
        number_images=True,allow_rotation=False,
        auto_fit_width=True,png_engine=engine)
    result=generate_layout(paths,tmp_path/'out',settings,plan_ready=plans.append)
    from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
    assert all(detect_guide_band(path) is not None for path in paths)
    assert result['order_check']['double_pairs']==3
    assert not result['analysis'].get('width_adjustments')
    assert '未缩小图片' in result['analysis']['rotation_recovery']['action']
    assert [p.read_bytes() for p in paths]==original
    with Image.open(tmp_path/'out'/result['filename']) as output:
        for path,p in plans[0]['planned']:
            assert p.rotation_degrees==90 and (p.width_px,p.height_px)==(234,563)
            assert p.color_block_x_px==0
            assert p.color_block_y_px==p.y_px-round(1.5*25.4/25.4)
            assert p.cut_zone==('旋转区' if mode=='dual' else '单排区')
            with Image.open(path) as source:
                rotated=source.rotate(90,expand=True)
                actual = output.crop((p.x_px,p.y_px,p.x_px+234,p.y_px+563))
                import numpy as np
                expected_pixels = np.asarray(rotated)
                actual_pixels = np.asarray(actual)
                opaque = expected_pixels[:, :, 3] == 255
                assert np.array_equal(actual_pixels[opaque], expected_pixels[opaque])
        zones=result['cut_corridor'].get('zones', []) if mode=='dual' else []
        if mode == 'dual':
            assert result['cut_corridor']['column_count'] == 1
            assert result['cut_corridor']['knife_xs_px'] == []
        assert not zones
        for zone in zones:
            assert output.crop((zone['safe_left_px'],0,zone['safe_right_px'],output.height)).getchannel('A').getextrema()[1]==0


def test_non_width_errors_are_not_recovered():
    from automatic_print.layout_engine.planning.rotation.whole_rotation import recover_normal_width
    error=ValueError('订单被拆散')
    with pytest.raises(ValueError,match='订单被拆散'):
        recover_normal_width([],LayoutSettings(cutter_mode='dual',cutter_compare_whole_rotation=True),None,error)


def test_free_layout_without_markers_uses_full_width_rotation_recovery(tmp_path):
    path = tmp_path/'B1-1-T-Black-5XL-NO1-1.png'
    Image.new('RGBA', (563, 234), 'blue').save(path, dpi=(25.4, 25.4))
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=430, cutter_mode='free',
        color_block_enabled=False, number_images=False, platform_name='',
        allow_rotation=False, auto_fit_width=True,
    )

    result = plan_layout([path], settings, None)
    placement = result[0][0][1]
    warning, order_check, cut_check = validate_plan(
        [path], result[0], settings, result[2], result[3], False,
    )

    assert placement.rotation_degrees == 90
    assert placement.cut_knife_x_px is None
    assert placement.cut_knife_xs_px == ()
    assert placement.cut_column_count == 1
    assert warning == ''
    assert order_check
    assert cut_check == {}
