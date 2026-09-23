"""Automatic Print desktop application."""

from .updates.versioning import release_display

__version__ = "0.1.343"
__release_date__ = "2026-09-22"
__release_iteration__ = 5
__version_display__ = release_display(__release_date__, __release_iteration__)
