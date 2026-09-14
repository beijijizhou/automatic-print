"""Automatic Print desktop application."""

from .versioning import release_display

__version__ = "0.1.171"
__release_date__ = "2026-09-14"
__release_iteration__ = 42
__version_display__ = release_display(__release_date__, __release_iteration__)
