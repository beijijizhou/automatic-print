"""One shared S2B metadata read before preview or final generation."""
from collections import Counter

from .batch_name import find_s2b_batch_folder
from .store import color_for_path, register_batch_records


def gateway_config():
    from .client import gateway_config as implementation
    return implementation()


def fetch_s2b_batch_info(batch_number):
    from .client import fetch_s2b_batch_info as implementation
    return implementation(batch_number)


def prepare_s2b_metadata(paths, settings, progress=None):
    grouped = {}
    for path in paths:
        batch = find_s2b_batch_folder(path)
        if batch:
            grouped.setdefault(batch, []).append(path)
    if not grouped:
        return []
    from .client import S2BBatchInfoError
    endpoint, key = gateway_config()
    if not endpoint or not key:
        message = (
            "订单颜色服务尚未配置；已保留本地订单信息继续排版，"
            "结果需要用户确认后使用"
        )
        if progress:
            progress("S2B批次信息", 0, len(grouped), message)
        return [
            _result(batch, members, warning=f"{batch.batch_number}：{message}")
            for batch, members in grouped.items()
        ]
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
            message = (
                f"{batch.batch_number}：订单颜色读取失败：{error}；"
                "已使用本地信息继续排版，结果需要用户确认后使用"
            )
            if progress:
                progress("S2B批次信息", index, len(grouped), message)
            results.append(_result(batch, members, warning=message))
            continue
        unresolved = [path for path in members if not color_for_path(path)]
        if unresolved:
            names = "、".join(path.name for path in unresolved[:5])
            more = f"等{len(unresolved)}张" if len(unresolved) > 5 else ""
            message = (
                f"{batch.batch_number}：订单颜色仅匹配{matched}/{len(members)}张，"
                f"未匹配：{names}{more}；已使用本地信息继续排版，"
                "结果需要用户确认后使用"
            )
            if progress:
                progress("S2B批次信息", index, len(grouped), message)
            results.append(_result(
                batch, members, payload, matched, warning=message,
                unmatched=[path.name for path in unresolved],
            ))
            continue
        colors = Counter(color_for_path(path) for path in members)
        results.append(_result(batch, members, payload, matched, colors=colors))
        if progress:
            detail = "、".join(f"{color}{count}张" for color, count in sorted(colors.items()))
            progress("S2B批次信息", index, len(grouped), f"{batch.batch_number}：{detail}")
    return results


def _result(
    batch, members, payload=None, matched=0, *, colors=None, warning="",
    unmatched=None,
):
    payload = payload or {}
    return {
        "batch_number": batch.batch_number,
        "folder_count": batch.expected_count,
        "local_images": len(members),
        "api_total": payload.get("source_total"),
        "matched_images": matched,
        "colors": dict(sorted((colors or {}).items())),
        "warning": warning,
        "unmatched_files": list(unmatched or ()),
    }


def metadata_warning_text(records):
    warnings = [str(record.get("warning") or "").strip() for record in records]
    warnings = [warning for warning in warnings if warning]
    return "\n".join(warnings)
