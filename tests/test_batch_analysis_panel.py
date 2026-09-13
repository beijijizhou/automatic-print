import os
from preview_wait import wait_preview
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.batch_analysis import analyze_batch
from automatic_print.ui.batch_analysis_panel import BatchAnalysisPanel
from automatic_print.ui.main_window import MainWindow


def test_analysis_panel_uses_category_size_order_hierarchy_and_clears(tmp_path):
    app=QApplication.instance() or QApplication([])
    paths=[]
    for i, size in enumerate(('XXL','2XL','M')):
        path=tmp_path/f'B{i}-1-T-Black-{size}-NO1-1.png'
        Image.new('RGBA',(100,160),'blue').save(path,dpi=(25.4,25.4))
        paths.append(path)
    panel=BatchAnalysisPanel()
    report=analyze_batch(paths,LayoutSettings())
    panel.show_report(report)
    assert panel.tree.topLevelItemCount()==1
    category=panel.tree.topLevelItem(0)
    assert category.text(0)=='单件单面'
    assert category.childCount()==2
    sizes={category.child(i).text(0):category.child(i) for i in range(category.childCount())}
    assert sizes['2XL'].childCount()==2
    assert '2XL 2 件' in panel.sizes.text()
    selected=[]
    panel.source_selected.connect(selected.append)
    leaf=sizes['2XL'].child(0).child(0).child(0)
    panel._selected(leaf,0)
    assert selected==[str(paths[0])]
    panel.clear()
    assert panel.report is None
    assert panel.tree.topLevelItemCount()==0
    panel.close()


def test_worker_analysis_reaches_gui_and_image_selection_matches_rotation_control(tmp_path):
    app=QApplication.instance() or QApplication([])
    folder=tmp_path/'images'; folder.mkdir()
    paths=[]
    for i in range(2):
        path=folder/f'B{i}-1-T-White-S-NO1-1.png'
        Image.new('RGBA',(100,160),'blue').save(path,dpi=(25.4,25.4))
        paths.append(path)
    prefs=QSettings(str(tmp_path/'prefs.ini'),QSettings.IniFormat)
    prefs.setValue('cutter/quick_mode', False)
    window=MainWindow(preferences=prefs)
    window.folder.setText(str(folder))
    panel=window.automation_home.label_quick_panel
    wait_preview(panel.preview)
    assert panel.analysis.report['stage']=='排版结果'
    panel.analysis.source_selected.emit(str(paths[1]))
    assert panel.manual_rotation.images.currentData()==str(paths[1])
    assert panel.preview.path==paths[1]
    window.generation_preview.start()
    assert panel.analysis.report is None
    data=analyze_batch(paths,window._layout_settings())
    window.worker_bridge.layout_analysis.emit(data)
    assert panel.analysis.report==data
    window.generation_preview.end()
    window.close()
