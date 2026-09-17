"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.266"
__release_date__ = "2026-09-17"
__release_iteration__ = 6
__version_display__ = release_display(__release_date__, __release_iteration__)
