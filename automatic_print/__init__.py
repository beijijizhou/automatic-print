"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.411"
__release_date__ = "2026-09-25"
__release_iteration__ = 14
__command_protocol__ = 1
__command_capabilities__ = (
    "probe", "printer_history", "source_update", "launch_app",
    "download_layout", "start_print", "pause_print", "clean_resume",
)
__release_notes__ = (
    "修复部分电脑源码更新后后台监控未能自动重新启动的问题。",
    "重启时只结束旧监控进程，不再结束承载重启辅助程序的计划任务。",
)
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
