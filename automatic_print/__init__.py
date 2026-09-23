"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.373"
__release_date__ = "2026-09-23"
__release_iteration__ = 30
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
