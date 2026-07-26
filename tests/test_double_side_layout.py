from PIL import Image

from automatic_print.layout import LayoutSettings, generate_layout


def _double_side_images(folder):
    folder.mkdir()
    paths = [
        folder / "B9UV77Y-2-1000M--102-黑色-XXL-NO1-1.png",
        folder / "B9UV77Y-2-1000M--102-黑色-XXL-NO1-2.png",
    ]
    for path in paths:
        Image.new("RGB", (40, 30), "red").save(
            path, dpi=(100, 100)
        )
    return paths


def test_double_sides_stay_horizontal_when_that_is_shorter(tmp_path) -> None:
    paths = _double_side_images(tmp_path / "source")
    result = generate_layout(
        paths,
        tmp_path / "output",
        LayoutSettings(
            media_width_mm=30,
            spacing_mm=2.54,
            margin_mm=0,
            dpi=100,
            number_images=False,
            allow_rotation=False,
        ),
    )

    first, second = result["placements"]
    assert first["y_px"] == second["y_px"]
    assert second["x_px"] == first["x_px"] + first["width_px"] + 10


def test_double_sides_stack_when_horizontal_pair_cannot_fit(tmp_path) -> None:
    paths = _double_side_images(tmp_path / "source")
    result = generate_layout(
        paths,
        tmp_path / "output",
        LayoutSettings(
            media_width_mm=15,
            spacing_mm=2.54,
            margin_mm=0,
            dpi=100,
            number_images=False,
            allow_rotation=False,
        ),
    )

    first, second = result["placements"]
    assert first["x_px"] == second["x_px"]
    assert second["y_px"] == first["y_px"] + first["height_px"] + 10
