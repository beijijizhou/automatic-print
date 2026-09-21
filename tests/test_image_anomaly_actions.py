import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QPushButton

from automatic_print.layout_engine.labeling.gap.report import annotate_analysis
from automatic_print.ui import image_anomaly_actions
from automatic_print.ui.batch_summary import BatchSummaryPanel


def test_each_failed_image_opens_its_own_original_and_clears_for_next_batch(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    first = tmp_path / 'small-gap.png'
    second = tmp_path / 'missing-qr.png'
    opened = []
    monkeypatch.setattr(image_anomaly_actions, 'QDesktopServices',
                        SimpleNamespace(openUrl=lambda url: opened.append(url.toLocalFile()) or True))
    report = {
        'batch_type': '测试', 'order_count': 2, 'piece_count': 2,
        'image_count': 2, 'double_pairs': 0,
        'image_anomalies': [{'source': second.name, 'path': str(second),
                             'kind': '未找到膜标签', 'action': '原图保留'}],
    }
    annotate_analysis(report, [{'source': str(first), 'filename': first.name,
                                'minimum_mm': 40, 'added_px': 0,
                                'warning': '补足膜标签间距失败'}])
    panel = BatchSummaryPanel()
    panel.show()
    panel.show_analysis(report)
    app.processEvents()

    buttons = panel.anomaly_actions.findChildren(QPushButton)
    assert len(buttons) == 2
    assert all(button.text() == '打开原图' for button in buttons)
    for button in buttons:
        button.click()
    assert [path.replace('\\', '/') for path in opened] == [
        second.as_posix(), first.as_posix()]

    panel.start(tmp_path / 'next-batch')
    app.processEvents()
    assert panel.anomaly_actions.isHidden()
    assert not panel.anomaly_actions.findChildren(QPushButton)
    panel.close()
