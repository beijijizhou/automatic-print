import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from dataclasses import replace
from PIL import Image
import pytest
from automatic_print.layout_engine import LayoutSettings,generate_layout
from automatic_print.layout_engine.planning.zones import gap_fallback
from automatic_print.layout_engine.planning.zones import width_fit
from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.layout_engine.orders.order_groups import pair_identity


def source(path,size):
    with Image.new('RGBA',size,(10,20,30,255)) as image:
        image.save(path,dpi=(25.4,25.4))
    return path


def test_rotation_is_forced_before_any_scaling(tmp_path,monkeypatch):
    path=source(tmp_path/'B1-1-T-Black-M-NO1-1.png',(300,100))
    monkeypatch.setattr(width_fit,'scaled_copy',lambda *args:pytest.fail('旋转可放下，不应缩小'))
    settings=LayoutSettings(dpi=25.4,media_width_mm=150,cutter_mode='single',
        cutter_left_marker_external=True,auto_fit_width=True,allow_rotation=False,number_images=False)
    plans=[]
    result=generate_layout([path],tmp_path/'out',settings,plan_ready=plans.append)
    p=plans[0]['planned'][0][1]
    assert p.rotation_degrees==90 and (p.width_px,p.height_px)==(100,300)
    assert '未缩小图片' in result['analysis']['rotation_recovery']['action']
    assert not result['analysis'].get('width_adjustments')


@pytest.mark.parametrize('engine',['pillow','libvips'])
def test_full_double_batch_short_side_scaling_and_saved_pixels(tmp_path,monkeypatch,engine):
    monkeypatch.setattr(width_fit,'cache_root',lambda:tmp_path/'cache')
    paths=[source(tmp_path/f'B{o}-1-T-Black-M-NO1-{f}.png',(500,300)) for o in range(4) for f in (1,2)]
    originals=[p.read_bytes() for p in paths]
    settings=LayoutSettings(dpi=25.4,media_width_mm=150,cutter_mode='single',cutter_auto_knife=True,
        cutter_left_marker_external=True,auto_fit_width=True,allow_rotation=False,number_images=False,png_engine=engine)
    plans=[]
    result=generate_layout(paths,tmp_path/'out',settings,plan_ready=plans.append)
    assert result['order_check']['double_pairs']==4
    assert len(result['analysis']['width_adjustments'])==8
    with Image.open(tmp_path/'out'/result['filename']) as output:
        for path,p in plans[0]['planned']:
            assert p.rotation_degrees==90 and p.color_block_x_px==0
            assert p.x_px+p.width_px<=150
            with Image.open(path) as prepared:
                assert abs(prepared.width/prepared.height-500/300)<.02
                rotated=prepared.rotate(90,expand=True)
                actual=output.crop((p.x_px,p.y_px,p.x_px+rotated.width,p.y_px+rotated.height))
                assert actual.tobytes()==rotated.tobytes()
        check=result.get('cut_corridor')
        if check:
            for zone in check.get('zones',[check]):
                assert output.crop((zone['safe_left_px'],0,zone['safe_right_px'],output.height)).getchannel('A').getextrema()[1]==0
    assert [p.read_bytes() for p in paths]==originals
    assert '缩小会改变实际烫印尺寸' in result['analysis']['image_anomalies'][0]['kind']


def test_feature_can_be_disabled_without_silent_resize(tmp_path):
    path=source(tmp_path/'B1-1-T-Black-M-NO1-1.png',(500,300))
    with pytest.raises(ValueError):
        generate_layout([path],tmp_path/'out',LayoutSettings(dpi=25.4,media_width_mm=150,
            allow_rotation=False,auto_fit_width=False,number_images=False,color_block_enabled=False))


def test_free_mode_never_enters_width_recovery(tmp_path,monkeypatch):
    paths=[source(tmp_path/f'B1-1-T-Black-M-NO1-{face}.png',(500,300)) for face in (1,2)]
    original=[p.read_bytes() for p in paths]
    monkeypatch.setattr(width_fit,'fit_oversized',lambda *args:pytest.fail('非单排不得自动缩小'))
    with pytest.raises(ValueError):
        generate_layout(paths,tmp_path/'out',LayoutSettings(dpi=25.4,media_width_mm=150,
            cutter_mode='free',cutter_auto_knife=True,auto_fit_width=True,allow_rotation=False,
            number_images=False,color_block_enabled=False))
    assert [p.read_bytes() for p in paths]==original


def test_direct_recovery_accepts_dual_rotation_leftovers():
    paths, settings = width_fit.fit_oversized(
        [], LayoutSettings(cutter_mode='dual', auto_fit_width=True)
    )
    assert paths == [] and settings.cutter_mode == 'dual'


def test_double_batch_greedy_rotation_scales_blocked_pair_together(tmp_path):
    dimensions = (
        (336, 505), (346, 559), (293, 448), (301, 496),
        (293, 448), (301, 496), (102, 178), (271, 483),
        (283, 435), (290, 481), (259, 405), (266, 447),
    )
    orders = ('B89ZWUT', 'BO9VPPM', 'BD849RJ', 'BVBKZ8Y', 'BHX5D83', 'BGRFUPZ')
    sizes = ('5Xl', '4Xl', 'Xxl', 'Xl', 'Xl', 'S')
    paths = []
    for index, size in enumerate(dimensions):
        pair = index // 2
        face = index % 2 + 1
        paths.append(source(
            tmp_path / f'A{index + 1:07d}-{orders[pair]}-1-T-LSJ-2-Black-{sizes[pair]}-NO1-{face}.png',
            size,
        ))
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=580, spacing_mm=12,
        cutter_mode='dual', cutter_auto_knife=True,
        cutter_left_marker_external=True, cutter_compare_whole_rotation=True,
        cutter_single_row_rotation=True, preserve_header_gap=False,
        auto_fit_width=True, force_small_pair_width=True,
        platform_below_marker=True, platform_reuse_qr=True,
        allow_rotation=False, cutter_majority_two_zone=True,
        cutter_safety_mm=3, cutter_knife_mm=290,
        platform_name='隆丰', platform_font_height_mm=6,
        label_machine_enabled=True,
    )
    normal = gap_fallback.plan_with_gap_fallback(
        paths, replace(settings, auto_fit_width=False), [], None, None,
    )[2]
    _, selected, result = gap_fallback.plan_with_gap_fallback(
        paths, settings, [], None, None,
    )
    planned = result[0]
    assert result[3] < normal[3]
    assert len({placement.cut_zone for _, placement in planned}) <= 2
    overrides = dict(selected.dimension_overrides)
    first_pair = paths[:2]
    ratios = []
    for path in first_pair:
        width, _height = overrides[str(path.resolve())]
        ratios.append(width / print_dimensions(path, settings.dpi).width_mm)
    assert ratios[0] == pytest.approx(ratios[1])
    for identity in {pair_identity(path)[0] for path in paths}:
        members = [(path, placement) for path, placement in planned
                   if pair_identity(path)[0] == identity]
        assert len({placement.rotation_degrees for _, placement in members}) == 1
        assert len({placement.cut_zone for _, placement in members}) == 1
