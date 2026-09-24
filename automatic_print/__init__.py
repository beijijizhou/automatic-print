"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.394"
__release_date__ = "2026-09-24"
__release_iteration__ = 15
__version_display__ = release_display(__version__, __release_date__, __release_iteration__)
