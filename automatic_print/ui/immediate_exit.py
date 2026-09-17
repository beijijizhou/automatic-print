"""Keep user work alive and let Qt close normally when the window is idle."""


def close_safely(window, event) -> bool:
    if window.has_active_tasks():
        event.ignore()
        window.status.setText(
            '任务仍在运行，窗口保持打开；完成后可关闭或自动更新重启。'
        )
        window.run_log.appendPlainText(
            '关闭请求未执行：当前任务继续运行，程序没有替用户终止任务。'
        )
        return False
    window.startup_update_timer.stop()
    window.clock.stop()
    window.preference_autosave.flush()
    window.settings_dialog.hide()
    event.accept()
    return True
