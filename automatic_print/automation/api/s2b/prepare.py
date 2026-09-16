"""One shared S2B metadata read before preview or final generation."""
from collections import Counter

from .batch_name import find_s2b_batch_folder
from .client import S2BBatchInfoError, fetch_s2b_batch_info, gateway_config
from .metadata import color_for_path, register_batch_records


def prepare_s2b_metadata(paths, settings, progress=None):
    grouped = {}
    for path in paths:
        batch = find_s2b_batch_folder(path)
        if batch:
            grouped.setdefault(batch, []).append(path)
    if not grouped:
        return []
    endpoint, key = gateway_config()
    if not endpoint or not key:
        message = "识别到S2B批次，但订单颜色服务尚未配置，已停止排版"
        if progress:
            progress("S2B批次信息", 0, len(grouped), message)
        raise S2BBatchInfoError(message)
    results = []
    for index, (batch, members) in enumerate(grouped.items(), 1):
        if all(color_for_path(path) for path in members):
            continue
        if progress:
            progress("S2B批次信息", index - 1, len(grouped), batch.batch_number)
        try:
            payload = fetch_s2b_batch_info(batch.batch_number)
            matched = register_batch_records(members, payload)
        except S2BBatchInfoError as error:
            message = f"{batch.batch_number}：订单颜色读取失败，已停止排版：{error}"
            if progress:
                progress("S2B批次信息", index, len(grouped), message)
            raise S2BBatchInfoError(message) from error
        unresolved = [path for path in members if not color_for_path(path)]
        if unresolved:
            message = (
                f"{batch.batch_number}：订单颜色仅匹配{matched}/{len(members)}张，"
                "已停止排版"
            )
            if progress:
                progress("S2B批次信息", index, len(grouped), message)
            raise S2BBatchInfoError(message)
        colors = Counter(color_for_path(path) for path in members)
        results.append({
            "batch_number": batch.batch_number,
            "folder_count": batch.expected_count,
            "local_images": len(members),
            "api_total": payload.get("source_total"),
            "matched_images": matched,
            "colors": dict(sorted(colors.items())),
        })
        if progress:
            detail = "、".join(f"{color}{count}张" for color, count in sorted(colors.items()))
            progress("S2B批次信息", index, len(grouped), f"{batch.batch_number}：{detail}")
    return results
