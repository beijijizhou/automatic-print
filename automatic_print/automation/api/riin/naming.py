"""Build safe PRN names from verified production result facts."""
from pathlib import Path

from ....layout_engine.output.output_name import label_output_name


def available_prn_path(folder, stem=None):
    root = Path(folder).resolve()
    candidate = root / f"{stem or root.name}.prn"
    index = 2
    while candidate.exists():
        candidate = root / f"{stem or root.name}-{index}.prn"
        index += 1
    return candidate


def group_piece_count(result, names):
    """Count the production pieces represented by one PRN PNG group."""
    all_names = result.get("files") or [result.get("filename")]
    analysis = result.get("analysis") or {}
    if set(names) == set(all_names) and analysis.get("piece_count") is not None:
        return int(analysis["piece_count"])
    selected = set(names)
    parts = result.get("parts") or [result]
    sources = {
        Path(placement["source"]).name
        for part in parts if part.get("filename") in selected
        for placement in part.get("placements", ()) if placement.get("source")
    }
    pieces, matched = set(), set()
    for order_index, order in enumerate(analysis.get("orders", ())):
        for item_index, item in enumerate(order.get("items", ())):
            item_sources = {
                Path(image.get("path") or image.get("name") or "").name
                for image in item.get("images", ())
            }
            overlap = sources & item_sources
            if overlap:
                pieces.add((order_index, item_index))
                matched.update(overlap)
    return len(pieces) if sources and matched == sources else None


def prn_stem(processed, batch, result, names):
    platform = str(processed.get("platform") or result.get("platform_name")
                   or "未设置平台").strip()
    labels = processed.get("batch_labels") or {}
    batches = processed.get("merged_batches") or []
    batch_number = (
        "_".join(str(labels.get(number) or number) for number in batches)
        if batch == "合并批次" and batches else str(labels.get(batch) or batch)
    )
    pieces = group_piece_count(result, names)
    count = f"{pieces}件" if pieces is not None else "件数待核对"
    platform = Path(label_output_name(platform, extension=".prn")).stem
    batch_number = Path(label_output_name(batch_number, extension=".prn")).stem
    stem = f"{platform}_{batch_number}_{count}"
    while len(stem.encode("utf-8")) > 180 and batch_number:
        batch_number = batch_number[:-1].rstrip(" ._")
        stem = f"{platform}_{batch_number}_{count}"
    return stem
