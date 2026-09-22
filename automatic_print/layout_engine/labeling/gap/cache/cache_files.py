"""Atomic cache publication tolerant of transient Windows file ownership."""
from time import sleep


def replace_with_busy_retry(source, target, attempts=8):
    for attempt in range(attempts):
        try:
            source.replace(target)
            return
        except OSError as error:
            retryable = (getattr(error, 'winerror', None) in {32, 33}
                         or getattr(error, 'errno', None) in {1, 13, 16})
            if not retryable or attempt + 1 == attempts:
                raise
            sleep(.05 * (attempt + 1))


def unlink_temporary(path):
    staged = path.with_name(path.name + '.待清理')
    try:
        replace_with_busy_retry(path, staged, attempts=3)
        staged.unlink(missing_ok=True)
    except OSError:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass  # A scanner still owns only this disposable cache file.
