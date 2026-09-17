from PIL import Image
import pytest

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.intake.metadata.images import print_dimensions, target_size


def _image(path, width=280, height=350, dpi=True):
    options = {"dpi": (25.4, 25.4)} if dpi else {}
    Image.new("RGB", (width, height), "blue").save(path, **options)
    return path


def _settings(**values):
    defaults = dict(
        media_width_mm=600, dpi=25.4, margin_mm=0,
        number_images=False, cutter_mode="dual", cutter_knife_mm=300,
        color_block_gap_mm=5, allow_rotation=True,
    )
    return LayoutSettings(**(defaults | values))


@pytest.mark.parametrize("engine", ["pillow", "libvips"])
def test_fixed_dual_rows_keep_knife_marker_and_orientation(tmp_path, engine):
    paths = [_image(tmp_path / f"{i}.png", height=300 + i * 10) for i in range(4)]
    result = generate_layout(paths, tmp_path / "out", _settings(png_engine=engine))
    placements = result["placements"]
    assert result["rotation_count"] == 0
    for left, right in zip(placements[::2], placements[1::2]):
        assert left["x_px"] + left["width_px"] <= 297
        assert right["color_block_x_px"] == 303
        assert right["color_block_y_px"] == left["color_block_y_px"]
        assert right["x_px"] >= 303
        assert right["x_px"] + right["width_px"] <= 600
    assert result["source_dimensions"][0]["width_mm"] == pytest.approx(280, abs=0.1)


@pytest.mark.parametrize("engine", ["pillow", "libvips"])
def test_zero_horizontal_knife_clearance_keeps_exact_partition_boundary(tmp_path, engine):
    paths = [_image(tmp_path / f"zero-{i}.png", width=280, height=300)
             for i in range(4)]
    result = generate_layout(paths, tmp_path / "zero-out", _settings(
        png_engine=engine, cutter_safety_mm=0))
    assert result['cutter_safety_mm'] == 0
    for left, right in zip(result['placements'][::2], result['placements'][1::2]):
        knife = right['cut_knife_x_px']
        assert left['x_px'] + left['width_px'] <= knife
        assert right['color_block_x_px'] == knife
        assert right['x_px'] >= knife
    corridor = result['cut_corridor']['zones'][0]['corridors'][0]
    assert corridor['safe_left_px'] == corridor['safe_right_px']
    assert result['cut_corridor']['pixel_verified']


def test_image_that_crosses_partition_uses_safe_original_size_rotation(tmp_path):
    path = _image(tmp_path / "too-wide.png", width=310)
    result = generate_layout([path], tmp_path / "out", _settings())
    placement = result['placements'][0]
    assert result['rotation_count'] == 1
    assert placement['rotation_degrees'] == 90
    assert (placement['width_px'], placement['height_px']) == (350, 310)
    assert placement['cut_zone'] == '旋转区'
    assert result['cut_corridor']['pixel_verified']


def test_single_column_preserves_double_pair_without_rotation(tmp_path):
    paths = [
        _image(tmp_path / f"ORDER-NO1-{side}.png") for side in (1, 2)
    ]
    result = generate_layout(
        paths, tmp_path / "out", _settings(media_width_mm=450, cutter_mode="single")
    )
    first, second = result["placements"]
    assert first["x_px"] == second["x_px"]
    assert second["y_px"] > first["y_px"] + first["height_px"]
    assert result["rotation_count"] == 0


def test_automatic_cutter_columns_are_an_output_of_film_width(tmp_path):
    paths = [_image(tmp_path / f"B{i}-1-T-Black-M-NO1-1.png", width=250, height=100)
             for i in range(6)]
    result = generate_layout(paths, tmp_path / "wide", _settings(
        media_width_mm=900, cutter_auto_knife=True,
        cutter_left_marker_external=True, cutter_safety_mm=0))
    assert result['dual_quality']['column_rows'] == {3: 2}
    assert {tuple(p['cut_knife_xs_px']) for p in result['placements']} == {(300, 600)}
    assert len(result['cut_corridor']['zones'][0]['corridors']) == 2


def test_automatic_cutter_can_resolve_to_one_column(tmp_path):
    paths = [_image(tmp_path / f"B{i}-1-T-Black-M-NO1-1.png", width=250, height=100)
             for i in range(2)]
    result = generate_layout(paths, tmp_path / "narrow", _settings(
        media_width_mm=280, cutter_auto_knife=True,
        cutter_left_marker_external=True))
    assert result['dual_quality']['column_rows'] == {}
    assert {p['cut_column_count'] for p in result['placements']} == {1}
    assert result['cut_corridor']['knife_xs_px'] == []


def test_cutter_mode_rejects_missing_dpi_but_reader_reports_estimate(tmp_path):
    path = _image(tmp_path / "no-dpi.png", dpi=False)
    size = print_dimensions(path, 100)
    assert not size.embedded_dpi
    assert size.width_mm == pytest.approx(71.12)
    with pytest.raises(ValueError, match="没有可靠的内嵌 DPI"):
        generate_layout([path], tmp_path / "out", _settings())


def test_invalid_knife_and_disabled_marker_are_rejected(tmp_path):
    path = _image(tmp_path / "image.png")
    with pytest.raises(ValueError, match="刀位和安全区"):
        generate_layout([path], tmp_path / "one", _settings(cutter_knife_mm=600))
    with pytest.raises(ValueError, match="必须启用"):
        generate_layout([path], tmp_path / "two", _settings(color_block_enabled=False))


def test_print_dimensions_preserve_asymmetric_source_dpi(tmp_path):
    path = tmp_path / "different-dpi.png"
    Image.new("RGB", (200, 200), "white").save(path, dpi=(100, 200))
    size = print_dimensions(path, 300)
    assert size.embedded_dpi
    assert size.width_mm == pytest.approx(50.8, abs=0.01)
    assert size.height_mm == pytest.approx(25.4, abs=0.01)
    assert target_size(path, 300) == (600, 300)
