"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.408"
__release_date__ = "2026-09-25"
__release_iteration__ = 11
__release_notes__ = (
    "新增远程打开 AutomaticPrint：后台监控可通过局域网 UDP 或 Supabase Realtime 接收唤起指令。",
    "软件唤起与 PrintExp 状态完全分离，即使打印机关闭也可启动 AutomaticPrint 主界面。",
    "远程唤起只允许固定 AutomaticPrint 入口，不接受任意程序路径或系统命令。",
    "主界面增加 Windows 单实例锁，软件已经运行时只返回现场回执，不会重复打开窗口。",
    "机器状态页的控制与任务区域新增目标电脑选择和远程打开按钮。",
)
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
