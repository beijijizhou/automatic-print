import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PySide6.QtCore import QSettings, QPoint
from PySide6.QtWidgets import QApplication

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.ui.main_window import MainWindow


def test_current_batch_preview_and_summary_are_visible_and_retained(tmp_path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path/'TEST_BATCH'
    source.mkdir()
    paths = []
    for i in range(4):
        path = source/f'B{i}-1-T-White-M-NO1-1.png'
        Image.new('RGBA', (180, 600), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    settings = LayoutSettings(dpi=25.4, cutter_mode='dual', number_images=False)
    payloads = []
    result = generate_layout(paths, tmp_path/'out', settings, plan_ready=payloads.append)
    prefs = QSettings(str(tmp_path/'ui.ini'), QSettings.IniFormat)
    window = MainWindow(prefs)
    window.startup_update_timer.stop()
    window.folder.setText(str(source))
    window.show()
    app.processEvents()
    controller = window.generation_preview
    panel = controller.panel
    window.settings_dialog.show()
    controller.start()
    assert not panel.summary.progress.isVisible()
    assert not window.busy_spinner.isVisible()
    window.worker_bridge.layout_preview.emit(payloads[0])
    app.processEvents()
    assert not window.settings_dialog.isVisible()
    assert panel.summary.isVisible()
    assert panel.summary.title() == '排版数据 · 耗时与总结'
    assert not panel.summary.info.isVisible()
    assert panel.selected_source.isVisible()
    assert not window.progress.isVisible()
    assert not window.status.isVisible()
    assert not window.current_file.isVisible()
    assert panel.summary.isAncestorOf(panel.timings)
    assert panel.timings.title() == ''
    assert 'TEST_BATCH' in panel.summary.info.text()
    assert '4 张' in panel.summary.info.text()
    assert '节省用膜' in panel.summary.metrics.text()
    viewport = window.automation_home.workbench_scroll.viewport()
    summary_top = panel.summary.mapTo(viewport, QPoint(0, 0)).y()
    assert 0 <= summary_top < viewport.height()
    panel.preview_tabs.setCurrentWidget(panel.actual_preview_page)
    app.processEvents()
    assert panel.preview_scroll.isVisible()
    assert panel.preview_scroll.height() <= 720
    assert panel.preview_scroll.verticalScrollBar().maximum() > 0
    controller.progress('保存图片', 0, 100, 'test.png')
    assert '保存图片' in panel.summary.progress.text()
    assert len(panel.preview.planned) == 4
    assert window.grab().save(str(tmp_path/'integrated-workbench.png'))
    panel.summary.finished(str(tmp_path/'out'), result)
    controller.end()
    assert panel.summary.progress.isVisible()
    assert '节省用膜' in panel.summary.metrics.text()
    assert result['filename'] in panel.summary.progress.text()
    assert result['filename'] in panel.summary.cutting.toPlainText()
    assert not panel.summary.cutting.isVisible()
    assert '保存阶段' not in panel.summary.metrics.text()
    assert not hasattr(window, 'batch_record')
    assert panel.summary.isAncestorOf(panel.summary.cutting)
    assert panel.summary.layout().indexOf(panel.summary.cutting) >= 0
    app.processEvents()
    assert panel.summary.grab().save(str(tmp_path/'summary-after-finish.png'))
    window.batch_status_board.open_record.click()
    assert result['filename'] in controller.record_dialog.details.toPlainText()
    assert '输出文件信息' in controller.record_dialog.details.toPlainText()
    controller.record_dialog.close()
    assert len(panel.preview.planned) == 4
    panel.summary.finished('', {'preview_only': True})
    assert '未生成文件' in panel.summary.progress.text()
    assert '节省用膜' in panel.summary.metrics.text()
    controller.start()
    assert not panel.preview.planned
    assert not panel.summary.metrics.isVisible()
    controller.end()
    window.close()


def test_late_qr_result_is_discarded_after_signal_destruction(monkeypatch):
    from shiboken6 import delete
    from automatic_print.ui import cut_guide_cache
    monkeypatch.setattr(cut_guide_cache, 'detect_guide_band', lambda path: None)
    task = cut_guide_cache.BandTask(('unused.png', 0, 0, 0))
    delete(task.signals)
    task.run()
