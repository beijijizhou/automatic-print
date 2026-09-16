"""Cooperative pause routing; closing the window remains the explicit hard exit."""


def stop_active_layout(window):
    bulk = getattr(window, 'bulk_controller', None)
    if bulk and bulk.thread is not None:
        bulk.cancel()
        return
    controller = getattr(window, 'layout_generation', None)
    if controller is not None and controller.request_cancel():
        window.stop_generation_button.setEnabled(False)
        window.status.setText('正在停止当前排版；已完成文件保留，软件不会退出…')
        window.run_log.appendPlainText('已请求停止当前排版；等待当前可中断步骤结束。')
        return
    home = getattr(window, 'automation_home', None)
    if home and home.thread is not None:
        home.stop_current_task()
        return
    window.stop_generation_button.setEnabled(False)
    window.status.setText('当前没有正在运行的排版任务。')
