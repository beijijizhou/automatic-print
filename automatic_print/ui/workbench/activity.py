"""Create the live task controls displayed in the main workbench."""

from PySide6.QtWidgets import QPlainTextEdit, QPushButton

from ..activity_hub import ActivityHub, ActivityLabel, ActivityProgressBar
from ..busy_spinner import BusySpinner


def build_activity(window) -> None:
    window.activity_hub = ActivityHub(window)
    window.progress = ActivityProgressBar(window.activity_hub)
    window.progress.setRange(0, 100)
    window.progress.setFormat("尚未开始")
    window.busy_spinner = BusySpinner(window)
    window.status = ActivityLabel(
        "请选择包含图片的文件夹。", window.activity_hub, "message",
    )
    window.current_file = ActivityLabel(
        "当前文件：—", window.activity_hub, "current_object",
    )
    window.run_log = QPlainTextEdit()
    window.run_log.setReadOnly(True)
    window.run_log.setMaximumHeight(115)

    window.generate_button = QPushButton("生成最终打印文件", window)
    window.generate_button.clicked.connect(window.generate)
    window.generate_button.hide()
    window.stop_generation_button = QPushButton("停止当前排版")
    window.stop_generation_button.setEnabled(False)
    window.stop_generation_button.clicked.connect(window.stop_generation)
