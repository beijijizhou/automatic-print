"""Readable labels for supplement batch candidates in platform views."""


def style_label(group) -> str:
    if group.style_id or group.style_name:
        return f'{group.style_name or "名称未记录"}（ID: {group.style_id or "未记录"}）'
    strategy = getattr(group, 'strategy', None)
    if strategy is not None and not strategy.by_style:
        return '不按底款拆分'
    if getattr(group, 'platform_name', '') in {'隆丰', 'Haloo'}:
        return '不按底款拆分'
    if group.order_composition != '单项单件':
        return '多件整单（不按底款拆分）'
    return '底款未记录'


def selected_description(groups) -> str:
    return '\n'.join(
        f'{index}. {style_label(group)}｜颜色：'
        f'{color_label(group)}'
        f'｜物流：{group.logistics_code or "不分物流"}｜面别：{group.face}'
        f'｜尺码档：{size_label(group)}'
        f'｜{len(group.item_ids)} 项 / {sum(qty for _, qty in group.item_quantities)} 件'
        for index, group in enumerate(groups, 1)
    )


def color_label(group) -> str:
    if group.color:
        return group.color
    strategy = getattr(group, 'strategy', None)
    if strategy is not None and not strategy.by_color:
        return '不分颜色'
    if group.face == '双面':
        return '不分颜色'
    if group.order_composition != '单项单件':
        return '不分颜色'
    return '未记录'


def size_label(group) -> str:
    if group.size_group:
        return group.size_group
    strategy = getattr(group, 'strategy', None)
    if strategy is not None and not strategy.by_size:
        return '不分尺码'
    if group.face == '双面' or group.order_composition != '单项单件':
        return '不分尺码'
    return '未记录'
