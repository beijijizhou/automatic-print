"""Non-destructive RIIN desktop automation diagnostics."""

from .desktop_controls.window_control import RiinProbeReport, RiinWindow, probe_riin

__all__ = ('RiinProbeReport', 'RiinWindow', 'probe_riin')
