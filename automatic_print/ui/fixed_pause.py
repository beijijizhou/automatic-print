"""Keep a synchronized production exit action outside the scrolling workbench."""
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QPushButton
from .action_icons import action_icon


class PauseMirror(QObject):
    def __init__(self, source, button):
        super().__init__(button)
        self.source, self.button = source, button
        source.installEventFilter(self)
        button.setEnabled(source.isEnabled())

    def eventFilter(self, watched, event):
        if watched is self.source and event.type() == QEvent.EnabledChange:
            self.button.setEnabled(self.source.isEnabled())
        return False


def build_fixed_pause(window, footer):
    button = QPushButton('暂停批次')
    button.setIcon(action_icon('stop'))
    button.setMinimumHeight(36)
    button.setProperty('importance', 'danger')
    button.setToolTip('立即退出，不等待单批或多批任务完成；已完成文件保留，未完成结果禁止打印。')
    button.clicked.connect(window.stop_generation)
    button._mirror = PauseMirror(window.stop_generation_button, button)
    window.fixed_pause_button = button
    footer.addWidget(button)
    settings_button = window.automation_home.settings_button
    settings_button.setMinimumHeight(36)
    footer.addWidget(settings_button)
    return button
