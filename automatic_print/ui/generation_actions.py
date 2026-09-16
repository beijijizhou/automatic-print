"""Compatibility import for single-task workbench generation UI."""

from .workbench.generation import GenerationActionsMixin
from .workbench.generation.results import QDesktopServices

__all__ = ["GenerationActionsMixin", "QDesktopServices"]
