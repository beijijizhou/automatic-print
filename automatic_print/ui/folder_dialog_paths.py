"""One remembered browser location; never replace the production source."""
from pathlib import Path
from os.path import commonpath

KEY = 'dialogs/last_image_directory'


def image_dialog_start(window):
    current = getattr(window, 'folder', None)
    candidates = (window.preferences.value(KEY, '', str),
                  current.text().strip() if current is not None else '',
                  window.preferences.value('source_location', '', str))
    for value in candidates:
        if value and Path(value).is_dir():
            return str(Path(value).resolve())
    return ''


def remember_image_directory(window, directory):
    path = Path(directory)
    if path.is_dir():
        window.preferences.setValue(KEY, str(path.resolve()))
        window.preferences.sync()


def remember_multiple_selection(window, folders):
    paths = [Path(folder).resolve() for folder in folders if Path(folder).is_dir()]
    if paths:
        try:
            directory = commonpath([str(path.parent) for path in paths])
        except ValueError:  # Different Windows drives have no common parent.
            directory = paths[0].parent
        remember_image_directory(window, directory)
