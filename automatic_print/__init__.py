"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.400"
__release_date__ = "2026-09-25"
__release_iteration__ = 3
__release_notes__ = (
    "修复 PrintExp 打印历史时间来源：改为读取每日主日志中的真实开始和完成事件。",
    "打印历史默认显示今天和昨天，并包含开始时间、结束时间、实际用时、PRN 文件名和原始路径。",
    "历史保留在打印机本地，不建立云端历史表；远程查询结果读取后立即删除。",
    "机器关键功能修改现在必须通过机器子系统测试和真实 PrintExp 节点验证。",
)
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
