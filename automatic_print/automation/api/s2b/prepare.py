"""One shared S2B metadata read before preview or final generation."""
from .batch_name import find_s2b_batch_folder
from .client import S2BBatchInfoError, fetch_s2b_batch_info, gateway_config
from .metadata import batch_metadata, register_batch_records


def prepare_s2b_metadata(paths, settings, progress=None):
    if not getattr(settings, "s2b_batch_api_enabled", False):
        return []
    if str(getattr(settings, "platform_name", "")).casefold() != "s2b":
        return []
    endpoint, key = gateway_config()
    if not endpoint or not key:
        if progress:
            progress("S2B批次信息", 0, 0, "中心服务尚未配置，继续使用本地信息")
        return []
    grouped = {}
    for path in paths:
        batch = find_s2b_batch_folder(path)
        if batch:
            grouped.setdefault(batch, []).append(path)
    results = []
    for index, (batch, members) in enumerate(grouped.items(), 1):
        if batch_metadata(batch.batch_number):
            continue
        if progress:
            progress("S2B批次信息", index - 1, len(grouped), batch.batch_number)
        try:
            payload = fetch_s2b_batch_info(batch.batch_number)
            matched = register_batch_records(members, payload)
            results.append({
                "batch_number": batch.batch_number,
                "folder_count": batch.expected_count,
                "local_images": len(members),
                "api_total": payload.get("source_total"),
                "matched_images": matched,
            })
        except S2BBatchInfoError as error:
            if progress:
                progress("S2B批次信息", index, len(grouped), f"{batch.batch_number}：{error}")
            continue
        if progress:
            progress("S2B批次信息", index, len(grouped), batch.batch_number)
    return results
