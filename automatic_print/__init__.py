"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.317"
__release_date__ = "2026-09-20"
__release_iteration__ = 1
__version_display__ = release_display(__release_date__, __release_iteration__)
