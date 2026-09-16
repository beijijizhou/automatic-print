"""Create the live task controls displayed in the main workbench."""

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QProgressBar, QPushButton

from ..busy_spinner import BusySpinner


def build_activity(window) -> None:
    window.progress = QProgressBar()
    window.progress.setRange(0, 100)
    window.progress.setFormat("尚未开始")
    window.busy_spinner = BusySpinner(window)
    window.status = QLabel("请选择包含图片的文件夹。")
    window.current_file = QLabel("当前文件：—")
    window.run_log = QPlainTextEdit()
    window.run_log.setReadOnly(True)
    window.run_log.setMaximumHeight(115)

    window.generate_button = QPushButton("生成最终打印文件", window)
    window.generate_button.clicked.connect(window.generate)
    window.generate_button.hide()
    window.stop_generation_button = QPushButton("停止当前排版")
    window.stop_generation_button.setEnabled(False)
    window.stop_generation_button.clicked.connect(window.stop_generation)
