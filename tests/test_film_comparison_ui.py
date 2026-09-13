import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.ui.batch_summary import BatchSummaryPanel
from test_film_comparison import sources


def test_four_options_are_visible_and_copyable(tmp_path):
    app = QApplication.instance() or QApplication([])
    reports = []
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual',
                              cutter_auto_knife=True, allow_rotation=False,
                              number_images=False, compare_film_sizes=True)
    plan_layout(sources(tmp_path), settings, None, reports.append)
    panel = BatchSummaryPanel()
    panel.start(tmp_path)
    panel.show_analysis(reports[-1])
    panel.resize(1300, 470)
    panel.show()
    app.processEvents()
    text = panel.metrics.text()
    for film in ('60', '45'):
        for option in ('不旋转', '允许旋转'):
            assert f'{film} 厘米 · {option}' in text
    assert '平方米' in text
    assert '图片占位' in text
    assert panel.metrics.textInteractionFlags() & Qt.TextSelectableByMouse
    assert panel.grab().save(str(tmp_path/'four-film-comparison.png'))
    panel.close()
