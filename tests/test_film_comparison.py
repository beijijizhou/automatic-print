from dataclasses import replace
import json

from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.film_comparison import compare_films, comparison_text
from automatic_print.layout_engine.planner import plan_layout


def sources(tmp_path):
    paths = []
    for order in ('B1', 'B2', 'B3'):
        for side in (1, 2):
            path = tmp_path/f'{order}-1-T-Black-M-NO1-{side}.png'
            Image.new('RGBA', (260, 320), 'blue').save(path, dpi=(25.4, 25.4))
            paths.append(path)
    return paths


def test_four_real_plans_report_area_not_cross_width_length(tmp_path):
    paths = sources(tmp_path)
    settings = LayoutSettings(dpi=25.4, cutter_mode='dual', media_width_mm=580,
                              cutter_auto_knife=True, allow_rotation=False,
                              number_images=False, transition_lines=True)
    progress = []
    result = compare_films(paths, settings, lambda *args: progress.append(args))
    assert len(result['rows']) == 8
    assert result['parallelism'] == 4
    for row in result['rows']:
        assert not row['error']
        assert row['image_area_m2'] == pytest.approx(6*.260*.320)
        assert row['film_area_m2'] == pytest.approx(row['film_mm']/1000*row['length_m'])
        assert row['usable_mm'] == row['film_mm']-20
        assert row['image_occupancy_percent'] == pytest.approx(
            100*row['image_area_m2']/row['film_area_m2'])
        assert row['usable_occupancy_percent'] > row['image_occupancy_percent']
        assert 0 < row['usable_occupancy_percent'] <= 100
    assert result['rows'][3]['rotated_images'] == 6
    assert result['rows'][3]['length_m'] < result['rows'][2]['length_m']
    best = min(result['rows'], key=lambda row: row['film_area_m2'])
    assert result['best_name'] == best['name']
    assert progress[-1][:3] == ('膜规格比较', 8, 8)
    assert {r['film_mm'] for r in result['rows']} == {400, 450, 600, 800}
    assert all(r['available'] == (r['film_mm'] in (450, 600)) for r in result['rows'])
    assert '不自动选择生产方案' in comparison_text(result)
    assert '不是油墨覆盖率' in comparison_text(result)
    json.dumps(result)
    assert not list(tmp_path.glob('**/print*.png'))


def test_unavailable_width_does_not_hide_other_plans(tmp_path):
    settings = LayoutSettings(dpi=25.4, number_images=False, riin_left_mm=225,
                              riin_right_mm=225)
    result = compare_films(sources(tmp_path), settings)
    assert all(row['error'] for row in result['rows'] if row['film_mm'] <= 450)
    assert '无安全方案' in comparison_text(result)


def test_planner_comparison_is_optional_and_preserves_selected_plan(tmp_path):
    paths = sources(tmp_path)
    settings = LayoutSettings(dpi=25.4, cutter_mode='dual', media_width_mm=580,
                              number_images=False, allow_rotation=False, cutter_auto_knife=True)
    expected = plan_layout(paths, settings, None)
    reports = []
    actual = plan_layout(paths, replace(settings, compare_film_sizes=True), None, reports.append)
    assert actual == expected
    assert len(reports[-1]['film_comparison']['rows']) == 8


def test_future_width_can_fit_without_becoming_production_selection(tmp_path):
    path = tmp_path / 'B1-1-T-Black-M-NO1-1.png'
    Image.new('RGBA', (650, 650), 'blue').save(path, dpi=(25.4, 25.4))
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, number_images=False)
    result = compare_films([path], settings)
    future = [row for row in result['rows'] if row['film_mm'] == 800]
    assert all(not row['error'] and not row['available'] for row in future)
    assert all(row['error'] for row in result['rows'] if row['film_mm'] < 800)
    assert result['best_name'].startswith('80 厘米')
    assert settings.media_width_mm == 580
    assert '不代表当前设备可生产' in comparison_text(result)
