__all__ = ["AutomationDialog"]


def __getattr__(name: str):
    if name == "AutomationDialog":
        from .dialog import AutomationDialog

        return AutomationDialog
    raise AttributeError(name)
