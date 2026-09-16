"""Persistent reference to the last successfully generated batch folder."""
from pathlib import Path


PREFERENCE_KEY = 'layout/latest_success_output_folder'


def latest_output_folder(settings):
    value = settings.value(PREFERENCE_KEY, '', str).strip()
    folder = Path(value) if value else None
    return folder if folder is not None and folder.is_dir() else None


def remember_output_folder(settings, output):
    folder = Path(output)
    if not folder.is_dir():
        return None
    resolved = folder.resolve()
    settings.setValue(PREFERENCE_KEY, str(resolved))
    settings.sync()
    return resolved
