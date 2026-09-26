"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.416"
__release_date__ = "2026-09-26"
__release_iteration__ = 3
__command_protocol__ = 1
__command_capabilities__ = (
    "probe", "printer_history", "source_update", "launch_app",
    "download_layout", "start_print", "pause_print", "clean_resume",
)
__release_notes__ = (
    "修复部分电脑源码更新后后台监控未能自动重新启动的问题。",
    "重启时只结束旧监控进程，不再结束承载重启辅助程序的计划任务。",
    "固定主界面菜单并集中打印参数、DTF平台账号和开发者功能入口。",
    "软件更新继续后台执行，不再显示步骤、状态文字或进度条。",
    "发布包含最新主界面与本地排版配置的 Windows 安装包。",
    "在主界面顶部版本号旁恢复“检查更新”按钮。",
)
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
