"""Visible top-level workbench surfaces.

The package mirrors the main window: ``home`` owns the workspace shell and
``settings`` owns the print-parameter dialog.  ``main_window`` only composes
those surfaces and application-level controllers.
"""

from .activity import build_activity
from .home import build_home
from .settings import build_settings

__all__ = ["build_activity", "build_home", "build_settings"]
