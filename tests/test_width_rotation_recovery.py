from PIL import Image
import pytest
from automatic_print.layout import LayoutSettings,generate_layout


@pytest.mark.parametrize('engine',['pillow','libvips'])
def test_failed_normal_batch_rotates_without_resizing(tmp_path,engine):
    paths=[]
    for order in range(3):
        for face in (1,2):
            path=tmp_path/f'B{order}-1-T-Black-L-NO1-{face}.png'
            with Image.new('RGBA',(563,234),(20,50,90,255)) as image:
                image.save(path,dpi=(25.4,25.4))
            paths.append(path)
    original=[p.read_bytes() for p in paths]
    plans=[]
    settings=LayoutSettings(dpi=25.4,media_width_mm=430,cutter_mode='dual',
        cutter_auto_knife=True,cutter_compare_whole_rotation=True,
        cutter_left_marker_external=True,number_images=False,allow_rotation=False,
        auto_fit_width=True,png_engine=engine)
    result=generate_layout(paths,tmp_path/'out',settings,plan_ready=plans.append)
    assert result['order_check']['double_pairs']==3
    assert not result['analysis'].get('width_adjustments')
    assert '未缩小图片' in result['analysis']['rotation_recovery']['action']
    assert [p.read_bytes() for p in paths]==original
    with Image.open(tmp_path/'out'/result['filename']) as output:
        for path,p in plans[0]['planned']:
            assert p.rotation_degrees==90 and (p.width_px,p.height_px)==(234,563)
            assert p.color_block_x_px==0 and p.cut_zone=='旋转区'
            with Image.open(path) as source:
                rotated=source.rotate(90,expand=True)
                assert output.crop((p.x_px,p.y_px,p.x_px+234,p.y_px+563)).tobytes()==rotated.tobytes()
        zones=result['cut_corridor']['zones']
        assert len(zones)==1
        for zone in zones:
            assert output.crop((zone['safe_left_px'],0,zone['safe_right_px'],output.height)).getchannel('A').getextrema()[1]==0


def test_non_width_errors_are_not_recovered():
    from automatic_print.layout_engine.whole_rotation import recover_normal_width
    error=ValueError('订单被拆散')
    with pytest.raises(ValueError,match='订单被拆散'):
        recover_normal_width([],LayoutSettings(cutter_mode='dual',cutter_compare_whole_rotation=True),None,error)
