"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.410"
__release_date__ = "2026-09-25"
__release_iteration__ = 13
__command_protocol__ = 1
__command_capabilities__ = (
    "probe", "printer_history", "source_update", "launch_app",
    "download_layout", "start_print", "pause_print", "clean_resume",
)
__release_notes__ = (
    "远程更新后自动探测新进程，同时核对版本、完整提交号、指令协议和功能清单。",
    "版本号一致但提交或功能不完整时不再显示更新完成。",
    "远程生产任务发送前会确认目标机支持 download_layout 能力。",
)
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
