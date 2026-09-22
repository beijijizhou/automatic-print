import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dataclasses import replace
from time import monotonic
import pytest
from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication

from automatic_print.ui.previews.markers.data import build_examples
from automatic_print.ui.main_window import MainWindow
from test_parallel_film_geometry import settings

APP = QApplication.instance() or QApplication([])


def sources(root):
    paths = []
    for side in ('left', 'right'):
        path = root/f'B{side}-1-T-Black-M-NO1-1.png'
        image = Image.new('RGBA', (270, 300))
        x = 0 if side == 'left' else 160
        image.paste('white', (x, 0, x+110, 45))
        image.paste('blue', (50, 90, 220, 270))
        image.save(path, dpi=(25.4, 25.4))
        paths.append(path)
    return paths


def wait_for(predicate):
    until = monotonic()+15
    while not predicate() and monotonic() < until:
        APP.processEvents()
    assert predicate()


def test_four_cases_use_production_geometry_and_never_modify_sources(tmp_path):
    paths = sources(tmp_path)
    original = [p.read_bytes() for p in paths]
    rows = build_examples(paths, replace(settings(),cutter_left_marker_external=True))
    assert len(rows) == 4
    assert all(r['production'] for r in rows)
    for row in rows:
        item = row['item']
        assert item.rotation_degrees == row['degrees']
        assert item.block_rx == 0
        assert item.image_rx == 0 or item.image_rx >= item.block_width
        assert len(row['pixels']) == row['size'][0]*row['size'][1]*4
        assert row['label_text']
        if row['degrees']:
            from automatic_print.layout_engine.labeling.markers.marker_stack import in_short_edge_space
            assert in_short_edge_space(row['region'], item.width, item.height,
                (item.label_rx-item.image_rx, item.label_ry-item.image_ry,
                 item.label_width, item.label_height))
        else:
            from math import ceil, floor
            if (row['region'].left+row['region'].right)/2 < .5:
                assert item.label_rx-item.image_rx >= ceil(row['region'].right*item.width)
            else:
                assert item.label_rx-item.image_rx+item.label_width <= floor(
                    row['region'].left*item.width)
            assert item.image_rx <= item.label_rx
            assert item.label_rx+item.label_width <= item.image_rx+item.width
    assert [p.read_bytes() for p in paths] == original
    assert set(tmp_path.iterdir()) == set(paths) | {tmp_path/'measurement-cache'}


def test_missing_side_is_explicit_diagram_not_mirrored_production(tmp_path):
    paths = sources(tmp_path)
    rows = build_examples(paths[:1], settings())
    assert [r['production'] for r in rows] == [True, False, True, False]
    assert all(not r['source'] for r in rows if not r['production'])


def test_fallback_diagrams_keep_transparent_label_space_with_everyday_settings():
    config = replace(
        settings(),
        dpi=300,
        follow_source_dpi=True,
        cutter_left_marker_external=True,
        preserve_header_gap=True,
        membrane_gap_mm=40,
        platform_below_marker=True,
        platform_reuse_qr=True,
        label_position='block_below',
        label_fit_height=True,
        label_reference_height_mm=10,
        label_source_order_enabled=True,
        label_machine_enabled=True,
        machine_number='M8',
        platform_name='S2B',
        platform_font_height_mm=6,
    )
    rows = build_examples([], config)
    assert len(rows) == 4
    assert all(not row['production'] for row in rows)
    assert all(row['pixels'] for row in rows)
    assert all(row['item'] is None or row['item'].label_width > 0 for row in rows)
    assert all(row['item'] is not None or '不代表可生产坐标' in row['detail'] for row in rows)


def test_unreadable_batch_image_still_shows_four_haloo_examples(tmp_path):
    broken = tmp_path/'broken.png'
    broken.write_bytes(b'not a png')
    rows = build_examples([broken], settings())
    assert len(rows) == 4
    assert all(not row['production'] for row in rows)
    assert all(row['sample_kind'].startswith('haloo') for row in rows)
    assert all('broken.png' in row['fallback_reason'] for row in rows)
    assert all(len(row['pixels']) == row['size'][0]*row['size'][1]*4 for row in rows)


def test_missing_bundled_asset_uses_code_diagram(tmp_path, monkeypatch):
    from automatic_print.ui.previews.markers import data
    monkeypatch.setattr(data, 'asset_path', lambda name: tmp_path/'missing.png')
    rows = build_examples([], settings())
    assert len(rows) == 4
    assert all(row['sample_kind'].startswith('code') for row in rows)
    assert all(row['pixels'] for row in rows)


@pytest.mark.parametrize('preserve_header_gap', [False, True])
def test_rotated_labels_use_card_short_edge_without_extra_image_footprint(preserve_header_gap):
    from automatic_print.layout_engine.labeling.markers.marker_stack import in_short_edge_space
    config = replace(settings(), preserve_header_gap=preserve_header_gap,
                     cutter_left_marker_external=True)
    rows = build_examples([], config)
    for row in rows:
        if row['degrees'] != 90:
            continue
        assert row['item'] is not None, row['fallback_reason']
        item = row['item']
        assert in_short_edge_space(row['region'], item.width, item.height,
            (item.label_rx-item.image_rx, item.label_ry-item.image_ry,
             item.label_width, item.label_height))
        assert item.image_ry <= item.label_ry
        assert item.label_ry+item.label_height <= item.image_ry+item.height


def test_bundled_haloo_example_is_anonymized_and_packaged():
    from automatic_print.runtime.resources import asset_path
    from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
    asset = asset_path('haloo-preview-sample.png')
    assert asset.is_file()
    with Image.open(asset) as image:
        assert image.mode == 'RGBA'
        assert image.getpixel((0, 0))[3] == 0
    assert detect_guide_band(asset) is not None
    from pathlib import Path
    assert 'haloo-preview-sample.png' in Path('AutomaticPrint.spec').read_text(encoding='utf-8')


def test_bad_image_keeps_default_page_diagrams_visible(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat))
    window.startup_update_timer.stop()
    examples = window.automation_home.label_quick_panel.marker_examples
    bad = tmp_path/'bad.png'
    bad.write_bytes(b'invalid')
    window.show()
    examples.use_batch({'planned': [(bad, None)]})
    wait_for(lambda: len(examples.results) == 4 and examples.worker is None
             and all('bad.png' in row['fallback_reason'] for row in examples.results))
    assert all(not picture.pixmap().isNull() for picture, _ in examples.cards)
    assert all('Haloo' in caption.text() for _, caption in examples.cards)
    assert all('bad.png' in caption.text() for _, caption in examples.cards)
    assert examples.grab().save(str(tmp_path/'bad-image-four-diagrams.png'))
    examples.timer.stop()
    window.preference_autosave.timer.stop()
    window.automation_home.label_quick_panel.preview.stop_loading()
    window.close()


def test_main_page_examples_start_after_show_and_refresh_on_parameters(tmp_path, monkeypatch):
    window = MainWindow(QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat))
    window.department_selector.setCurrentIndex(window.department_selector.findData('dtf'))
    window.startup_update_timer.stop()
    examples = window.automation_home.label_quick_panel.marker_examples
    assert examples.worker is None
    assert window.automation_home.label_quick_panel.preview_tabs.currentIndex() == 0
    window.show()
    wait_for(lambda: len(examples.results) == 4 and examples.worker is None)
    assert examples.isVisible()
    assert all(picture.minimumHeight() >= 280 for picture, _ in examples.cards)
    assert all(picture.geometry().bottom() < readout.y()
               for (picture, _), readout in zip(examples.cards, examples.label_readouts))
    assert all(readout.geometry().bottom() < caption.y()
               for (_, caption), readout in zip(examples.cards, examples.label_readouts))
    assert all(QFontMetrics(caption.font()).height() >= 19
               for _, caption in examples.cards)
    for row, readout in zip(examples.results, examples.label_readouts):
        assert QFontMetrics(readout.font()).height() >= 26
        assert readout.textFormat() == Qt.PlainText
        if row['label_text']:
            assert row['label_text'] in readout.text()
            assert '紫框标签文字放大' in readout.text()
    assert window.automation_home.label_quick_panel.preview_tabs.tabText(0) == '标签与刀码位置（默认）'
    assert window.automation_home.label_quick_panel.preview_tabs.tabText(1) == '批次排版预览'
    assert all(not r['production'] for r in examples.results)
    examples.grab().save(str(tmp_path/'four-case-diagram.png'))
    paths = sources(tmp_path)
    examples.use_batch({'planned': [(p, None) for p in paths]})
    wait_for(lambda: any(r['production'] for r in examples.results)
             and examples.worker is None and not examples.pending)
    for row in examples.results:
        item = row['item']
        if item is None:
            assert row['fallback_reason'] and '仅展示方向' in row['detail']
            continue
        assert item.platform_width == 0 or (
            item.image_rx <= item.platform_rx
            and item.platform_rx+item.platform_width <= item.image_rx+item.width
        )
    index = next(i for i, row in enumerate(examples.results) if row['item'] is not None)
    old = examples.results[index]['item'].block_width
    window.color_block_settings.width.setValue(12)
    wait_for(lambda: examples.results[index]['item'] is not None and
             examples.results[index]['item'].block_width != old and examples.worker is None)
    window.cutter_settings.left_marker_lift.setValue(2.5)
    from automatic_print.layout_engine.domain.models import mm_to_px
    wait_for(lambda: examples.results[index]['item'] is not None and
             examples.results[index]['item'].left_marker_lift_px ==
             mm_to_px(2.5, examples.results[index]['dpi']) and examples.worker is None)
    assert all(('当前批次生产图' if row['production'] else '示意') in caption.text()
               for row, (_, caption) in zip(examples.results, examples.cards))
    snapshot = examples.results
    examples.enlarge(2)
    assert examples.detail_dialog.isVisible()
    assert examples.results is snapshot
    examples.detail_dialog.close()
    window.grab().save(str(tmp_path/'four-case-main.png'))
    examples.timer.stop()
    window.preference_autosave.timer.stop()
    window.automation_home.label_quick_panel.preview.stop_loading()
    window.hide()


def test_batch_preview_remains_independent_second_page(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat))
    window.startup_update_timer.stop()
    panel = window.automation_home.label_quick_panel
    assert panel.preview_tabs.currentWidget() is panel.marker_examples
    panel.preview_tabs.setCurrentIndex(1)
    assert panel.preview_tabs.currentWidget() is panel.actual_preview_page
    assert panel.marker_examples is not panel.actual_preview_page
    window.preference_autosave.timer.stop()
    panel.preview.stop_loading()
    window.close()

