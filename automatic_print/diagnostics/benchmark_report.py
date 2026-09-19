"""Readable report for the developer cold-cache batch timing run."""


def format_report(report: dict) -> str:
    lines = ["DTF随机批次冷启动耗时", f"来源：{report['source_root']}",
             f"输出：{report['output_root']}", f"随机种子：{report['seed']}",
             f"口径：{report['cache_policy']}", f"状态：{report['status']}"]
    if "scan_seconds" in report:
        lines.append(f"发现与抽样：{report['scan_seconds']:.3f} 秒；候选批次 {report.get('candidate_count', 0)} 个")
    for item in report["batches"]:
        lines.extend(("", f"第{item['index']:02d}批 · {item['folder']} · {item['images']}张 · {item['status']}",
                      f"本批完整耗时：{item['wall_seconds']:.3f} 秒 · 累计：{item['cumulative_seconds']:.3f} 秒",
                      f"独立空缓存：{item['cache_directory']} · 图片线程：{item['worker_threads']}"))
        for step in (item.get("operation_timings") or {}).get("steps", []):
            lines.append(f"  {step['name']}：{step['seconds']:.3f} 秒")
        if item.get("engine_timings"):
            lines.append("  引擎子阶段：" + " · ".join(
                f"{name} {seconds:.3f}秒" for name, seconds in item["engine_timings"].items()
                if isinstance(seconds, (float, int))))
        if item.get("error"):
            lines.append("  失败诊断：" + item["error"])
    if "total_seconds" in report:
        lines.extend(("", f"全部总耗时：{report['total_seconds']:.3f} 秒",
                      f"成功 {report['completed']} 批 · 失败 {report['failed']} 批"))
        totals = {}
        for item in report["batches"]:
            for step in (item.get("operation_timings") or {}).get("steps", []):
                totals[step["name"]] = totals.get(step["name"], 0.0) + step["seconds"]
        lines.append("各阶段累计（逐批顺序执行）：")
        lines.extend(f"  {name}：{seconds:.3f} 秒" for name, seconds in
                     sorted(totals.items(), key=lambda pair: -pair[1]))
    if report.get("error"):
        lines.append("错误：" + report["error"])
    return "\n".join(lines) + "\n"
