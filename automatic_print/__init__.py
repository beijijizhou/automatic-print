"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.407"
__release_date__ = "2026-09-25"
__release_iteration__ = 10
__release_notes__ = (
    "修复 PrintExp 打印历史时间来源：改为读取每日主日志中的真实开始和完成事件。",
    "打印历史默认显示今天和昨天，并包含开始时间、结束时间、实际用时、PRN 文件名和原始路径。",
    "历史保留在打印机本地，不建立云端历史表；远程查询结果读取后立即删除。",
    "按需历史响应包含本机日志匹配诊断，便于识别不同 PrintExp 目录和日志格式。",
    "目标机缺少今天和昨天日志时，明确标注并显示最近两个可用日志，不再误报无历史。",
    "日志没有时间事件时仍显示 PrintExp 本地任务记录，并明确标记开始和结束时间不可用。",
    "历史查询附带任务文件格式诊断，用于识别不同 PrintExp 安装的数据文件差异。",
    "自动从 PrintExp 的四种原生任务文件中选择实际包含历史记录的数据源。",
    "打印历史与机器状态统一读取当前正在运行的 PrintExp 安装目录，避免误读旧空目录。",
    "机器关键功能修改现在必须通过机器子系统测试和真实 PrintExp 节点验证。",
)
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
