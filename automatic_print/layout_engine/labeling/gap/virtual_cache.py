"""Small persistent geometry records for render-time label gaps."""
import json
from pathlib import Path
from time import time
from uuid import uuid4

from .cache_files import replace_with_busy_retry, unlink_temporary


def load(info, source, identity, ttl_seconds):
    if not info.is_file() or time() - info.stat().st_mtime >= ttl_seconds:
        return None
    try:
        record = json.loads(info.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if record.get('source_identity') != identity:
        return None
    record.update(
        source=str(source), filename=Path(source).name,
        prepared=str(source), virtual_gap=True,
        preparation_engine='合成时虚拟补距', warning='',
    )
    return record


def save(info, record):
    temporary = info.with_name(info.name + '.' + uuid4().hex + '.未完成')
    try:
        info.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        replace_with_busy_retry(temporary, info)
    except OSError:
        pass  # Cache failure never changes production output.
    finally:
        unlink_temporary(temporary)
