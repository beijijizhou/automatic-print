import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from automatic_print.ui.activity_hub import ActivityHub
from automatic_print.ui.global_activity_center import GlobalActivityCenter


APP = QApplication.instance() or QApplication([])


def test_global_center_keeps_step_progress_and_stop_in_one_surface():
    stopped = []
    hub = ActivityHub()
    center = GlobalActivityCenter(hub)

    hub.begin("task", "隆丰下载排版", "正在读取批次", stop=lambda: stopped.append(True))
    hub.update(
        "task", message="正在下载生产图", current_object="609240119004",
        current=3, total=10, progress_text="3 / 10", new_step=True,
    )

    assert center.selector.currentText() == "隆丰下载排版 · 运行中"
    assert center.step.text() == "步骤 2 · 正在下载生产图"
    assert "609240119004" in center.details.text()
    assert center.progress.maximum() == 10
    assert center.progress.value() == 3
    assert center.stop.isEnabled()
    center.stop.click()
    assert stopped == [True]

    hub.finish("task", "下载排版完成")
    assert center.state.text() == "已完成"
    assert not center.stop.isEnabled()
