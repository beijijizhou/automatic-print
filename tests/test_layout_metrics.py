from automatic_print.layout_engine.metrics import (
    basic_ordered_height,
    saving_metrics,
    saving_text,
)


def test_basic_layout_height_matches_sequential_first_fit() -> None:
    footprints = [(2, 1), (2, 1), (2, 3), (5, 3)]

    assert basic_ordered_height(footprints, 10, 0) == 6


def test_saving_metrics_report_meters_and_percentage() -> None:
    result = saving_metrics(1200, 900, dpi=300)
    result["rotation_count"] = 4

    assert result["saved_length_m"] == 0.025
    assert result["saved_percent"] == 25
    assert saving_text(result) == (
        "智能排版节省 0.025 米（25.0%） · 旋转 4 张"
    )


def test_saving_text_reports_rotations_without_false_saving() -> None:
    assert saving_text(
        {"saved_length_m": 0, "rotation_count": 1}
    ) == "本次排版长度已是最短 · 旋转 1 张"
