"""One remembered browser location; never replace the production source."""
from pathlib import Path

KEY = 'dialogs/last_image_directory'
DEFAULT_DTF_SHARE = Path(r'\\192.168.11.28\dtf')


def image_dialog_start(window):
    current = getattr(window, 'folder', None)
    candidates = (window.preferences.value(KEY, '', str),
                  current.text().strip() if current is not None else '',
                  window.preferences.value('source_location', '', str),
                  str(DEFAULT_DTF_SHARE))
    for value in candidates:
        if value and Path(value).is_dir():
            return str(Path(value).resolve())
    return ''


def remember_image_directory(window, directory):
    path = Path(directory)
    if path.is_dir():
        window.preferences.setValue(KEY, str(path.resolve()))
        window.preferences.sync()
