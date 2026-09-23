import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
from types import SimpleNamespace
from time import monotonic, sleep

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QPushButton

from automatic_print.layout_engine import LayoutSettings
from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.previews.text_layout import inventory_text, layout_text

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def sample_report():
    def image(name):
        return {'path': f'/batch/{name}.png'}
    return {'image_count': 7, 'orders': [
        {'order': 'ORDER123', 'kind': '多件订单', 'pieces': 3,
         'sizes': {'S': 1, 'M': 2}, 'items': [
             {'size': 'S', 'images': [image('a'), image('b')]},
             {'size': 'M', 'images': [image('c')]},
             {'size': 'M', 'images': [image('d')]},
         ]},
        {'order': 'SINGLE', 'kind': '单件单面', 'pieces': 1,
         'sizes': {'L': 1}, 'items': [{'size': 'L', 'images': [image('e')]}]},
        {'order': 'DOUBLE', 'kind': '单件双面', 'pieces': 1,
         'sizes': {'XL': 1}, 'items': [
             {'size': 'XL', 'images': [image('f'), image('g')]},
         ]},
    ]}


def sample_payload():
    positions = [('a', 0, 10, '并排区'), ('b', 0, 20, '并排区'),
                 ('c', 0, 30, '并排区'), ('d', 0, 40, '并排区'),
                 ('e', 110, 10, '并排区'),
                 ('f', 0, 50, '旋转区'), ('g', 0, 60, '旋转区')]
    planned = [(Path(f'/batch/{name}.png'), SimpleNamespace(
        x_px=x, y_px=y, row_y_px=y, sequence_number=index,
        cut_zone=zone, cut_knife_x_px=100))
        for index, (name, x, y, zone) in enumerate(positions, 1)]
    return {'analysis': sample_report(), 'planned': planned,
            'settings': LayoutSettings(dpi=25.4, cutter_mode='dual', cutter_knife_mm=100)}


def test_text_preview_formats_multi_single_and_two_faces_without_images():
    early = inventory_text(sample_report())
    assert '尚未计算排版，暂时无法判断单排或双排' in early
    assert 'ORDER123-3件-S、M×2（第1件 S A面＋B面）' in early
    assert '单件单面尺码统计（不是排版位置）\nL' in early
    assert '单件双面尺码统计（不是排版位置）\nXL A面＋B面' in early
    text = layout_text(sample_payload())
    assert '本次排版：双排' in text
    assert '常规区 · 双排 · 分割线 100 毫米' in text
    assert '排次 左侧' in text and '│ 右侧' in text
    assert '01   ORDER123-3件-S（第1件 A面）' in text
    assert '│ L' in text
    assert '02   ORDER123-3件-S（第1件 B面）' in text
    assert '旋转区 · 双排' in text
    assert 'XL A面' in text and 'XL B面' in text
    assert '\n常规区\n' in text
    assert '第1排  ORDER123-3件-S、M×2' in text
    assert '第1排  L' in text
    assert '旋转区\n第5排  XL A面＋B面' in text


def test_single_row_layout_has_no_middle_divider():
    payload = sample_payload()
    payload['planned'] = [(path, SimpleNamespace(
        x_px=0, row_y_px=index, y_px=index, sequence_number=index,
        cut_zone='单排区', cut_knife_x_px=None, cut_knife_xs_px=()))
        for index, (path, _) in enumerate(payload['planned'], 1)]
    text = layout_text(payload)
    assert '本次排版：单排（无中间分割线）' in text
    assert '单排区 · 单排' in text
    assert '排次 内容' in text
    assert '│ 右侧' not in text


def test_main_page_shows_filename_text_then_actual_layout(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'text.ini'), QSettings.IniFormat))
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    window.department_selector.setCurrentIndex(
        window.department_selector.findData('dtf'))
    window.show()
    APP.processEvents()
    panel = window.automation_home.label_quick_panel
    assert panel.preview_tabs.currentIndex() == 0
    assert panel.text_preview.isReadOnly() and panel.text_preview.isVisible()
    assert panel.text_preview.lineWrapMode() == QPlainTextEdit.NoWrap
    panel.preview.analysis_ready.emit(sample_report())
    assert 'ORDER123-3件-S、M×2' in panel.text_preview.toPlainText()
    panel.preview.plan_loaded.emit(sample_payload())
    assert '常规区' in panel.text_preview.toPlainText()
    assert '旋转区' in panel.text_preview.toPlainText()
    copy_button = next(button for button in panel.preview_tabs.findChildren(QPushButton)
                       if button.text() == '复制文字预览')
    copy_button.click()
    assert APP.clipboard().text() == panel.text_preview.toPlainText()
    assert panel.text_preview.grab().save(str(tmp_path / 'text-preview.png'))
    window.close()


def test_inventory_groups_repeated_sizes_instead_of_implying_vertical_placement():
    report = {'image_count': 5, 'orders': [
        {'order': f'SINGLE-{index}', 'kind': '单件单面', 'pieces': 1,
         'sizes': {size: 1}, 'items': [{'size': size, 'images': [
             {'path': f'/batch/{index}.png'}]}]}
        for index, size in enumerate(('3XL', '3XL', '4XL', '5XL', '5XL'), 1)
    ]}

    text = inventory_text(report)

    assert '单件单面尺码统计（不是排版位置）' in text
    assert '3XL×2 · 4XL · 5XL×2' in text
    assert text.count('\n3XL') == 1


def test_saved_folder_shows_fast_text_inventory_without_layout(tmp_path):
    source = tmp_path / 'saved_batch'
    source.mkdir()
    Image.new('RGB', (20, 20), 'blue').save(
        source / 'A-1-T-Black-M-NO1-1.png', dpi=(25.4, 25.4))
    prefs = QSettings(str(tmp_path / 'saved.ini'), QSettings.IniFormat)
    prefs.setValue('source_location', str(source))
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    window.department_selector.setCurrentIndex(
        window.department_selector.findData('dtf'))
    window.show()
    deadline = monotonic() + 3
    panel = window.automation_home.label_quick_panel
    while '\nM' not in panel.text_preview.toPlainText() and monotonic() < deadline:
        APP.processEvents()
        sleep(.01)
    assert '\nM' in panel.text_preview.toPlainText()
    assert panel.preview.batch_payload is None
    window.close()
