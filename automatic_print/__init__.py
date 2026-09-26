"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.422"
__release_date__ = "2026-09-26"
__release_iteration__ = 9
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
    "新增本机注册：M1–M11 由数据库唯一绑定，旧程序不能再写回错误机器号。",
    "机器号已被占用时必须人工确认换绑，换绑后自动清除旧电脑的重复状态。",
    "标签设置中的机器号只影响打印标签，不再修改后台机器身份。",
    "并排等比缩小不再作用于旋转候选和最终旋转图片，旋转时保持原尺寸。",
    "主界面顶部固定显示版本号与检查更新按钮，并纳入 Windows 发布门禁。",
    "无刀码模式恢复旋转求解，可比较原方向、局部旋转和整批旋转。",
    "打印机状态页新增 Realtime 全机信号测试，绕过 UDP 验证跨网络通信和实际版本。",
    "新增标签文字位置设计器，并让刀码未旋转与旋转标签使用用户选择的安全对齐。",
)
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
