"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.399"
__release_date__ = "2026-09-25"
__release_iteration__ = 2
__release_notes__ = (
    "新增分布式 PrintExp 打印历史：任意机器可按需查询 M1–M11。",
    "打印历史默认显示今天和昨天，并包含开始时间、结束时间、实际用时和 PRN 文件名。",
    "历史保留在打印机本地，不建立云端历史表；远程查询结果读取后立即删除。",
    "版本管理和检查更新现在会用中文显示本次新功能。",
)
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
