"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.409"
__release_date__ = "2026-09-25"
__release_iteration__ = 12
__release_notes__ = (
    "远程版本管理允许选择 origin/main 中已发布的历史版本并安全回滚指定电脑。",
    "控制端有本地代码修改时仍可只读版本列表；目标机执行前仍会拒绝覆盖它的已跟踪修改。",
    "M1 远程唤起和单实例回执已通过实机验证。",
)
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
