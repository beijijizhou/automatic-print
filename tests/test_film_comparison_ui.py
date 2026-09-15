import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.layout_engine.dual_quality import dual_quality
from automatic_print.ui.batch_summary import BatchSummaryPanel
from test_film_comparison import sources


def test_four_options_are_visible_and_copyable(tmp_path, capfd):
    app = QApplication.instance() or QApplication([])
    reports = []
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual',
                              cutter_auto_knife=True, allow_rotation=False,
                              number_images=False, compare_film_sizes=True, compare_reference_films=True)
    plan = plan_layout(sources(tmp_path), settings, None, reports.append)
    panel = BatchSummaryPanel()
    for _ in range(3):
        panel.film_table.reset_rows()
    panel.start(tmp_path)
    panel.show_analysis(reports[-1])
    panel.resize(1300, 470)
    panel.show()
    app.processEvents()
    assert panel.film_table.rowCount() == 4
    text = '\n'.join(panel.film_table.item(row, 0).text() for row in range(4))
    for film in ('60', '45'):
        for option in ('不旋转', '允许旋转'):
            assert f'{film} 厘米 · {option}' in text
    assert '（参考）' not in text
    assert panel.film_table.horizontalHeaderItem(1).text() == '双排数量'
    assert panel.film_table.horizontalHeaderItem(2).text() == '实际旋转'
    assert not panel.film_table.isColumnHidden(2)
    assert panel.film_table.horizontalHeaderItem(4).text() == '面积 / ㎡'
    assert panel.film_table.horizontalHeaderItem(5).text() == '图片占位'
    assert panel.film_table.horizontalHeaderItem(7).text() == '批次构成'
    assert '尺码群分布' in panel.film_table.item(0, 7).text()
    assert panel.film_table.rowSpan(0, 7) == 4
    assert sum('（当前输出）' in panel.film_table.item(row, 0).text()
               for row in range(4)) == 1
    selected = next(row for row in reports[-1]['film_comparison']['rows']
                    if row.get('production_selected'))
    assert round(selected['length_m'], 6) == round(reports[-1]['height_m'], 6)
    assert selected['paired_rows'] == dual_quality(plan[0], settings)['paired_rows']
    assert selected['rotated_images'] == sum(bool(p.rotation_degrees) for _, p in plan[0])
    selected_row = next(row for row in range(4)
                        if '（当前输出）' in panel.film_table.item(row, 0).text())
    assert panel.film_table.item(selected_row, 2).text() == f"{selected['rotated_images']}张"
    assert panel.metrics.textInteractionFlags() & Qt.TextSelectableByMouse
    assert panel.grab().save(str(tmp_path/'four-film-comparison.png'))
    panel.film_table.set_reference_mode(False)
    assert panel.film_table.rowCount() == 4
    assert all('参考' not in panel.film_table.item(row, 0).text() for row in range(4))
    assert len(reports[-1]['film_comparison']['rows']) == 4
    panel.film_table.set_reference_mode(True)
    assert panel.film_table.rowCount() == 4
    panel.close()
    assert 'Error calling Python override' not in capfd.readouterr().err
