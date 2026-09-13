from dataclasses import replace

from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.layout_engine.rotation_zones import complete_orders
from automatic_print.layout_engine.cut_validation import validate_cut_corridor


def _sources(tmp_path):
    paths = []
    for order,width,height in (("BORDER1",100,300),("BORDER2",200,150)):
        for side in (1,2):
            path = tmp_path/f"{order}-1-T-Black-L-NO1-{side}.png"
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
    assert regions[0]["knife_x_px"] != regions[1]["knife_x_px"]
    rotated = [p for p in result["placements"] if p["cut_zone"] == "旋转区"]
    assert len(rotated) == 2
    assert all(p["source"].startswith("BORDER1-") for p in rotated)
    assert all(p["rotation_degrees"] == 90 for p in rotated)
    assert len({p["row_y_px"] for p in rotated}) == 2
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


def test_rotated_zone_cannot_have_two_images_on_one_row(tmp_path):
    paths = _sources(tmp_path)
    planned,_,width,_,_ = plan_layout(paths,_settings(),None)
    rotated_rows = [i for i,(_,p) in enumerate(planned) if p.cut_zone == "旋转区"]
    a,b = rotated_rows
    path,p = planned[b]
    planned[b] = path,replace(p,row_y_px=planned[a][1].row_y_px)
    with pytest.raises(ValueError,match="每一行只有一张"):
        validate_cut_corridor(planned,_settings(),width)
