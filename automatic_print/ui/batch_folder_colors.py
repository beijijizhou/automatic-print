"""S2B color summaries for the folder picker; never decode source images."""

from collections import Counter

from ..automation.api.s2b.metadata.batch_name import find_s2b_batch_folder
from ..automation.api.s2b.metadata.prepare import prepare_s2b_metadata
from ..automation.api.s2b.metadata.store import color_for_path


def read_folder_colors(batches, cancellation, progress=None):
    """Fetch each S2B batch once, then summarize only its local folder images."""
    groups = {}
    for batch in batches:
        for path in batch["images"]:
            identity = find_s2b_batch_folder(path)
            if identity:
                groups.setdefault(identity, []).append(path)
    if not groups:
        return {}

    paths = []
    for members in groups.values():
        paths.extend(members)
    cancellation.check()
    records = prepare_s2b_metadata(paths, None, progress)
    warnings = {record["batch_number"]: record["warning"] for record in records}
    summaries = {}
    for batch in batches:
        cancellation.check()
        images = batch["images"]
        identity = next((find_s2b_batch_folder(path) for path in images), None)
        if not identity:
            continue
        colors = Counter(filter(None, (color_for_path(path) for path in images)))
        matched = sum(colors.values())
        text = "、".join(f"{name}{count}张" for name, count in sorted(colors.items()))
        if matched < len(images):
            text += ("；" if text else "") + f"未匹配{len(images) - matched}张"
        summaries[str(batch["folder"])] = (
            text or "未取得", warnings.get(identity.batch_number, "")
        )
    return summaries
