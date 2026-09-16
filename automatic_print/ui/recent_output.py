"""View adapter for the most recently completed output folder."""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QPushButton

from ..history.recent_output import latest_output_folder, remember_output_folder


def recent_output_folder(window):
    return latest_output_folder(window.preferences)


def refresh_recent_output_button(window, button=None):
    home = getattr(window, 'automation_home', None)
    button = button or getattr(home, 'recent_output_button', None)
    if button is None:
        button = window.findChild(QPushButton, 'recentOutputButton')
    if button is None:
        return
    folder = recent_output_folder(window)
    button.setEnabled(folder is not None)
    button.setToolTip(
        f'打开最近成功生成的批次：{folder}' if folder else
        '尚无可打开的成功生成批次；仅预览和失败任务不会记录。'
    )


def remember_recent_output(window, output):
    if remember_output_folder(window.preferences, output) is None:
        return
    refresh_recent_output_button(window)


def open_recent_output(window):
    folder = recent_output_folder(window)
    if folder is None:
        refresh_recent_output_button(window)
        QMessageBox.information(window, '最近批次不可用', '最近生成的批次文件夹已不存在。')
        return
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))
