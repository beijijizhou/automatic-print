"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.284"
__release_date__ = "2026-09-18"
__release_iteration__ = 24
__version_display__ = release_display(__release_date__, __release_iteration__)
