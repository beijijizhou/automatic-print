from ..runtime.restart import request_application_restart


def restart_updated_app(window):
    window.automation_home.setEnabled(True)
    window.settings_dialog.setEnabled(True)
    if window.source_update_busy():
        window.show_update_progress('更新完成；仍有任务运行，请完成后手动重新启动。')
        return
    window.show_update_progress('更新完成，正在请求安全重启…')
    if not request_application_restart(window):
        window.show_update_progress('更新完成，但自动启动失败；请使用桌面入口重新打开。')
