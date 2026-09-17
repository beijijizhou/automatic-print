import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from PIL import Image
from automatic_print.ui.main_window import MainWindow
from automatic_print.layout_engine import generate_layout


def test_normal_mode_has_no_markers_or_inserted_gap(tmp_path):
    app=QApplication.instance() or QApplication([])
    window=MainWindow(QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat))
    window.startup_update_timer.stop()
    window.developer_mode_enabled=True
    window.membrane_gap.setValue(40)
    window.membrane_gap_enabled.setChecked(True)
    cutter=window.cutter_settings
    assert not cutter.transitions.end_block.isChecked()
    cutter.mode.setCurrentIndex(cutter.mode.findData('free'))
    window.number_images.setChecked(False)
    window.label_settings.platform_enabled.setChecked(False)
    settings=window._layout_settings()
    assert not settings.color_block_enabled and not settings.batch_end_block
    assert settings.membrane_gap_mm==0
    assert not settings.cutter_left_marker_external
    source=tmp_path/'B1-1-T-Black-M-NO1-1.png'
    with Image.new('RGBA',(100,200),'blue') as image:
        image.save(source,dpi=(25.4,25.4))
    plans=[]
    result=generate_layout([source],tmp_path/'out',settings,plan_ready=plans.append)
    assert not result['transition_marks']
    assert all(not p.color_block_width_px for _,p in plans[0]['planned'])
    assert plans[0]['planned'][0][0]==source
    cutter.mode.setCurrentIndex(cutter.mode.findData('single'))
    cut=window._layout_settings()
    assert cut.color_block_enabled and cut.membrane_gap_mm==40
    window.close()
