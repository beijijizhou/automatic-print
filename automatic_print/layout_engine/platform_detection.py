"""Detect source platform from stable folder structure, not a UI action choice."""
import re
from os import scandir
from pathlib import Path

SIZE=re.compile(r'^(?:XXS|XS|S|M|L|XL|XXL|[2-9]XL)$',re.IGNORECASE)


def is_size_name(name):
    return bool(SIZE.fullmatch(name.strip()))


def s2b_from_names(names):
    sizes={name.strip().upper() for name in names if is_size_name(name)}
    return len(sizes)>=2


def detect_selected_platform(folder):
    folder=Path(folder)
    try:
        with scandir(folder) as entries:
            children=[e.name for e in entries if e.is_dir(follow_symlinks=False)]
        if s2b_from_names(children):
            return 'S2B'
        if is_size_name(folder.name):
            with scandir(folder.parent) as entries:
                siblings=[e.name for e in entries if e.is_dir(follow_symlinks=False)]
            if s2b_from_names(siblings):
                return 'S2B'
    except OSError:
        return ''
    return ''


def detect_scanned_platform(root,batches):
    first=[]
    for batch in batches:
        relative=batch['folder'].relative_to(root).parts
        if relative:
            first.append(relative[0])
    return 'S2B' if s2b_from_names(first) else ''
