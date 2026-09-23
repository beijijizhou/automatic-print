"""Readable labels for supplement batch candidates in platform views."""


def style_label(group) -> str:
    if group.order_composition != '单项单件':
        return '多件整单（不按底款拆分）'
    if not group.style_id and not group.style_name:
        return '不按底款拆分'
    return f'{group.style_name or "名称未记录"}（ID: {group.style_id or "未记录"}）'


def selected_description(groups) -> str:
    return '\n'.join(
        f'{index}. {style_label(group)}｜颜色：'
        f'{_color_label(group)}'
        f'｜物流：{group.logistics_code or "不分物流"}｜面别：{group.face}'
        f'｜尺码档：{group.size_group or "不分尺码"}'
        f'｜{len(group.item_ids)} 项 / {sum(qty for _, qty in group.item_quantities)} 件'
        for index, group in enumerate(groups, 1)
    )


def _color_label(group) -> str:
    if group.order_composition != '单项单件':
        return '多件整单'
    if group.color:
        return group.color
    if group.face == '双面':
        return '不分颜色'
    return '未记录'
