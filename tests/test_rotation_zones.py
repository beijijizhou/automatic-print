from dataclasses import replace

from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.layout_engine.rotation_zones import complete_orders
from automatic_print.layout_engine.rotation_zones import _rotated


def _sources(tmp_path):
    paths = []
    for order,width,height in (("BORDER1",340,500),("BORDER2",200,150)):
        for side in (1,2):
            size = 'L' if order == 'BORDER1' else 'S'
            path = tmp_path/f"{order}-1-T-Black-{size}-NO1-{side}.png"
            Image.new("RGBA",(width,height),"blue").save(path,dpi=(25.4,25.4))
            paths.append(path)
    return paths


def _settings(**options):
    values = dict(dpi=25.4,media_width_mm=600,margin_mm=0,cutter_mode="dual",
                  cutter_auto_knife=True,cutter_rotation_zone=True,
                  number_images=False)
    return LayoutSettings(**(values|options))


@pytest.mark.parametrize("engine",["pillow","libvips"])
def test_saving_rotation_zone_moves_complete_double_order_and_uses_own_knife(tmp_path,engine):
    paths = _sources(tmp_path)
    baseline = plan_layout(paths,replace(_settings(),cutter_rotation_zone=False),None)
    result = generate_layout(paths,tmp_path/"out",_settings(png_engine=engine))
    assert result["height_px"] < baseline[3]
    regions = result["cut_corridor"]["zones"]
    assert [z["name"] for z in regions] == ["常规区","旋转区"]
    assert result["cut_corridor"]["knife_changes"] == 1
    assert all(z["pixel_verified"] for z in regions)
    assert regions[0]["corridors"]
    assert regions[1]["corridors"] == []  # One rotated column needs no internal knife.
    rotated = [p for p in result["placements"] if p["cut_zone"] == "旋转区"]
    assert len(rotated) == 2
    assert all(p["source"].startswith("BORDER1-") for p in rotated)
    assert all(p["rotation_degrees"] == 90 for p in rotated)
    assert len({p["y_px"] for p in rotated}) == 2
    assert {p["cut_column_count"] for p in rotated} == {1}
    assert set(p["sequence_number"] for p in rotated) == {1,2}
    normal = [p for p in result["placements"] if p["cut_zone"] == "常规区"]
    assert all(p["rotation_degrees"] == 0 for p in normal)


def test_no_saving_keeps_original_plan_and_knife(tmp_path):
    paths = _sources(tmp_path)[2:]
    original = plan_layout(paths,replace(_settings(),cutter_rotation_zone=False),None)
    candidate = plan_layout(paths,_settings(),None)
    assert candidate[0] == original[0]
    assert candidate[3] == original[3]
    assert not any(p.cut_zone for _,p in candidate[0])


def test_order_grouping_includes_all_pieces_and_production_prefixes(tmp_path):
    paths = [tmp_path/n for n in (
        "CVC面料00001-BORDER-1-NO1-1.png",
        "A000007-BORDER-2-NO1-2.png",
        "BOTHER-1-NO1-1.png",
        "CVC面料00003-BORDER-3-NO2-1.png",
    )]
    groups = complete_orders(paths)
    assert groups[0] == [paths[0],paths[1],paths[3]]


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_rotated_zone_can_reuse_fixed_multi_column_knives(tmp_path, engine):
    paths = []
    for index in range(4):
        path = tmp_path/f'B{index}-1-T-Black-M-NO1-1.png'
        Image.new('RGBA', (100, 250), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    result = generate_layout(paths, tmp_path/'rotated-columns', _settings(
        cutter_compare_whole_rotation=True, png_engine=engine))
    rotated = [p for p in result['placements'] if p['cut_zone'] == '旋转区']
    assert len(rotated) == 4
    assert len({p['row_y_px'] for p in rotated}) == 2
    assert {p['cut_column_count'] for p in rotated} == {2}
    assert {tuple(p['cut_knife_xs_px']) for p in rotated} == {(300,)}
    zones = result['cut_corridor']['zones']
    assert len(zones) == 1 and len(zones[0]['corridors']) == 1
    assert zones[0]['pixel_verified']


def test_rotated_zone_does_not_cut_wide_members_to_pair_narrow_members(tmp_path):
    paths = []
    for index, height in enumerate((250, 400, 250, 400)):
        path = tmp_path/f'B{index}-1-T-Black-M-NO1-1.png'
        Image.new('RGBA', (100, height), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    planned, _labels, _height, _knife = _rotated(paths, _settings())
    assert len({p.row_y_px for _path, p in planned}) == 4
    assert {p.cut_column_count for _path, p in planned} == {1}
    assert all(not p.cut_knife_xs_px for _path, p in planned)
