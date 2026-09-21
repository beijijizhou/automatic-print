"""Reset production preferences only; never touch files or ERP login state."""
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox, QPushButton
from ..runtime.restart import request_application_restart

GROUPS = ('department', 'uv', 'layout', 'label', 'color_block', 'cutter', 'riin', 'output')
KEYS = ('source_location', 'output_location', 'local/test_mode', 'local/merge_batches',
        'dialogs/last_image_directory', 'developer/bulk_parallelism')


def clear_layout_preferences(preferences):
    removed = {key: preferences.value(key) for key in preferences.allKeys()
               if key in KEYS or any(key.startswith(group+'/') for group in GROUPS)}
    for group in GROUPS:
        preferences.remove(group)
    for key in KEYS:
        preferences.remove(key)
    preferences.sync()
    if preferences.status() != QSettings.NoError:
        for key, value in removed.items():
            preferences.setValue(key, value)
        preferences.sync()
        raise OSError('无法写入默认设置，请检查当前用户的配置写入权限。')
    return len(removed)


def reset_settings(window):
    preview = window.automation_home.label_quick_panel.preview
    if window.has_active_tasks() or preview.loader.active:
        QMessageBox.warning(window, '任务正在运行', '请先停止任务并等待线程结束，再恢复默认设置。')
        return False
    answer = QMessageBox.question(window, '恢复默认设置',
        '清除保存的膜宽、间距、标签文字、机器号、手动旋转、分段并行参数及上次文件路径。'
        '\n不删除源图片、输出文件、批次报告或平台登录信息。'
        '\n恢复后软件会自动重启并加载出厂参数。是否继续？',
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if answer != QMessageBox.Yes:
        return False
    window.preference_autosave.timer.stop()
    window.settings_reset_pending = True
    try:
        clear_layout_preferences(window.preferences)
    except OSError as exc:
        window.settings_reset_pending = False
        QMessageBox.warning(window, '恢复失败', str(exc))
        return False
    preview.stop_loading()
    window.centralWidget().setEnabled(False)
    window.settings_dialog.setEnabled(False)
    QMessageBox.information(window, '已恢复默认设置',
        '保存的排版参数已清除。软件现在自动重启；图片和输出文件未删除。')
    if request_application_restart(window):
        return True
    window.centralWidget().setEnabled(True)
    window.settings_dialog.setEnabled(True)
    QMessageBox.warning(window, '自动重启失败',
        '出厂参数已恢复，但软件无法自动重启。请手动重新打开软件。')
    return False


def reset_button(window):
    button = QPushButton('恢出厂设置并重启')
    button.clicked.connect(lambda: reset_settings(window))
    button.setToolTip('清除保存的排版参数，不删除图片；重启后立即生效。')
    return button
