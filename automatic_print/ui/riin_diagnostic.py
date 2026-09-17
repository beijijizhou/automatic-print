"""Developer-only RIIN desktop control probe."""
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from ..automation.api.riin import probe_riin


class RiinProbeThread(QThread):
    completed = Signal(object)

    def __init__(self, keyword, parent=None):
        super().__init__(parent)
        self.keyword = keyword

    def run(self):
        self.completed.emit(probe_riin(self.keyword, activate=True))


class RiinDiagnosticDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('RIIN 代码控制测试')
        self.resize(700, 430)
        self.thread = None
        intro = QLabel(
            '仅执行窗口发现、响应探测和置前请求；不会导入文件、点击打印或修改RIIN队列。'
        )
        intro.setWordWrap(True)
        self.keyword = QLineEdit('RIIN')
        self.keyword.setPlaceholderText('RIIN窗口标题中可识别的文字')
        self.run_button = QPushButton('检测并置前RIIN')
        self.run_button.clicked.connect(self.start_probe)
        row = QHBoxLayout()
        row.addWidget(QLabel('窗口标题关键字'))
        row.addWidget(self.keyword, 1)
        row.addWidget(self.run_button)
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlainText('等待检测。请先启动RIIN，并保持当前Windows用户已登录。')
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText('关闭')
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(row)
        layout.addWidget(self.result, 1)
        layout.addWidget(buttons)

    def start_probe(self):
        if self.thread is not None:
            return
        self.run_button.setEnabled(False)
        self.result.setPlainText('正在读取当前交互桌面的顶层窗口并探测响应…')
        self.thread = RiinProbeThread(self.keyword.text(), self)
        self.thread.completed.connect(self.show_report)
        self.thread.finished.connect(self.probe_finished)
        self.thread.start()

    def show_report(self, report):
        if report.error:
            self.result.setPlainText(report.error)
            return
        if not report.windows:
            self.result.setPlainText(
                f'未发现标题包含“{report.keyword}”的可见窗口。\n'
                '请确认RIIN已经启动；如果窗口标题不含RIIN，请修改上方关键字后重试。'
            )
            return
        lines = [f'发现 {len(report.windows)} 个匹配窗口：']
        for index, window in enumerate(report.windows, 1):
            response = '正常响应' if window.responsive else '未在1秒内响应'
            focus = '已接受置前请求' if window.activated else '系统未允许置前'
            lines.extend((
                '', f'{index}. {window.title}',
                f'PID {window.process_id} · HWND {window.handle} · 类 {window.class_name}',
                f'坐标 {window.bounds} · {response} · {focus}',
            ))
        lines.extend((
            '', '请确认RIIN窗口是否出现在前台。若已置前，说明程序能够发现窗口并发送控制请求；',
            '按钮级自动化仍需下一阶段读取RIIN控件树后单独验证。',
        ))
        self.result.setPlainText('\n'.join(lines))

    def probe_finished(self):
        self.thread.deleteLater()
        self.thread = None
        self.run_button.setEnabled(True)
