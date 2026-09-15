from dataclasses import replace
import json

from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.film_comparison import compare_films, comparison_text
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.layout_engine import cutter_planner, rotation_zones
from automatic_print.layout_engine import film_comparison


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
                              number_images=False, transition_lines=True, compare_reference_films=True)
    progress = []
    result = compare_films(paths, settings, lambda *args: progress.append(args))
    assert len(result['rows']) == 4
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
    assert progress[-1][:3] == ('膜规格比较', 4, 4)
    assert {r['film_mm'] for r in result['rows']} == {450, 600}
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
                              number_images=False, allow_rotation=False, cutter_auto_knife=True,
                              compare_reference_films=True)
    expected = plan_layout(paths, settings, None)
    reports = []
    actual = plan_layout(paths, replace(settings, compare_film_sizes=True), None, reports.append)
    assert actual == expected
    assert len(reports[-1]['film_comparison']['rows']) == 4


def test_production_rotation_and_film_comparison_measure_cutter_batch_once(tmp_path, monkeypatch):
    paths = sources(tmp_path)
    calls = []
    original_cutter = cutter_planner.read_items
    original_rotation = rotation_zones.read_items

    def cutter_read(*args, **kwargs):
        calls.append('cutter')
        return original_cutter(*args, **kwargs)

    def rotation_read(*args, **kwargs):
        calls.append('rotation')
        return original_rotation(*args, **kwargs)

    monkeypatch.setattr(cutter_planner, 'read_items', cutter_read)
    monkeypatch.setattr(rotation_zones, 'read_items', rotation_read)
    plan_layout(paths, LayoutSettings(
        dpi=25.4, cutter_mode='dual', media_width_mm=580,
        number_images=False, cutter_auto_knife=True,
        compare_film_sizes=True, cutter_compare_whole_rotation=True,
    ), None)
    assert calls == ['cutter']


def test_reference_widths_stay_out_of_current_comparison(tmp_path):
    path = tmp_path / 'B1-1-T-Black-M-NO1-1.png'
    Image.new('RGBA', (650, 650), 'blue').save(path, dpi=(25.4, 25.4))
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, number_images=False, compare_reference_films=True)
    result = compare_films([path], settings)
    assert {row['film_mm'] for row in result['rows']} == {450, 600}
    assert all(row['error'] for row in result['rows'])
    assert result['best_name'] == ''
    assert settings.media_width_mm == 580
    assert '不代表当前设备可生产' in comparison_text(result)


def test_normal_comparison_computes_only_current_widths(tmp_path):
    result = compare_films(sources(tmp_path), LayoutSettings(dpi=25.4, number_images=False))
    assert len(result['rows']) == 4
    assert {row['film_mm'] for row in result['rows']} == {450, 600}
    assert '45/60厘米' in comparison_text(result)


def test_current_production_scheme_is_not_recalculated(tmp_path, monkeypatch):
    paths = sources(tmp_path)
    settings = LayoutSettings(
        dpi=25.4, cutter_mode='dual', media_width_mm=580,
        number_images=False, cutter_auto_knife=True,
        cutter_rotation_zone=True, cutter_majority_two_zone=True,
    )
    production = plan_layout(paths, settings, None)
    original, widths = film_comparison.plan_rotation_zones, []

    def counted(paths, config, *args, **kwargs):
        widths.append(config.media_width_mm)
        return original(paths, config, *args, **kwargs)

    monkeypatch.setattr(film_comparison, 'plan_rotation_zones', counted)
    result = compare_films(paths, settings, production=production)
    assert widths == [430]
    selected = [row for row in result['rows'] if row.get('production_selected')]
    assert len(selected) == 1
    assert selected[0]['film_mm'] == 600
