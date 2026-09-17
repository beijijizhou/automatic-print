"""Pure-data, source-name diagnostics; no extra image decoding on failure."""
from pathlib import Path
from automatic_print.layout_engine.orders.order_groups import complete_orders, order_key


def error_context(error, paths, folder='', stage='', settings=None):
    reason = str(error)
    if '相关订单与原始文件：' in reason:
        return reason
    paths = list(paths or [])
    matched = [p for p in paths if p.name in reason]
    keys = {order_key(p) for p in matched}
    if any(text in reason for text in ('整批图片不存在安全的统一双列刀位','图片无法安全放入固定分区')):
        keys = set()
    selected = [p for p in paths if order_key(p) in keys] if keys else paths
    lines = [f'失败原因：{reason}', f'批次目录：{folder}']
    if stage:
        lines.append('失败步骤：'+stage)
    if settings and '失败点实际限制参数：' not in reason:
        from .error_parameters import limits_text
        lines.append(limits_text(settings,actual=False))
    lines.append('定位：报错明确涉及的订单' if keys else
                 '定位：整批关联范围，当前无法归因于单一订单；以下不是全部坏图')
    lines.append('相关订单与原始文件：')
    for group in complete_orders(selected):
        lines.append(f'订单 {order_key(group[0]).upper()} · {len(group)} 张')
        for p in group:
            lines.append(f'  {p.name}\n  路径：{p}')
            if settings:
                from .error_parameters import source_parameters
                lines.append('  图片参数：'+source_parameters(p,settings.dpi))
    if not selected:
        lines.append('尚未获取图片清单，无法定位订单。')
    lines.append('处理：保留原图与已完成输出；未完成结果禁止打印。请复制本详情核查，不拆订单或绕过刀位检查。')
    return '\n'.join(lines)
