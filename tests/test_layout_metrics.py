from automatic_print.layout_engine.reporting.metrics import (
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


def test_completed_output_summary_uses_actual_batch_result():
    from automatic_print.layout_engine.output.output_file_info import production_summary_text
    text = production_summary_text({
        'analysis': {'batch_type': '单件单面批次', 'order_count': 60,
                     'piece_count': 60, 'image_count': 60, 'double_pairs': 0},
        'dual_quality': {'paired_rows': 5, 'single_images': [{}] * 20,
                         'rotation_zone_images': 30, 'rotated_images': 28},
        'placements': [{'width_px': 100, 'height_px': 200}] * 60,
        'output_dpi': 100, 'film_width_mm': 600, 'height_mm': 50000,
        'cutter_mode': 'dual', 'rotation_count': 30,
        'saved_length_m': 32.635, 'saved_percent': 42,
        'filename': '批次60单 60件.png',
    })
    assert '60 个订单组 · 60 件 · 60 张图' in text
    assert '双排 5 行 / 10 张 · 常规单排 20 张 · 旋转区 30 张（实际旋转 30 张）' in text
    assert '实际用膜：50.000 米 · 30.000 平方米' in text


def test_dual_quality_does_not_count_unrotated_row_members_as_rotated():
    from automatic_print.layout_engine import LayoutSettings
    from automatic_print.layout_engine.diagnostics.dual_quality import dual_quality
    from automatic_print.layout_engine.domain.models import Placement

    def placement(source, x, rotation):
        return Placement(
            source=source, sequence_number=1, x_px=x, y_px=0,
            width_px=100, height_px=200, number_x_px=0, number_y_px=0,
            number_width_px=0, number_height_px=0, row_y_px=0,
            footprint_width_px=100, footprint_height_px=200,
            rotation_degrees=rotation, cut_zone='旋转区',
        )

    quality = dual_quality(
        [('rotated.png', placement('rotated.png', 0, 90)),
         ('normal.png', placement('normal.png', 100, 0))],
        LayoutSettings(cutter_mode='dual'),
    )

    assert quality['rotation_zone_images'] == 2
    assert quality['rotated_images'] == 1
    assert '旋转区 2 张（实际旋转 1 张）' in quality['text']
