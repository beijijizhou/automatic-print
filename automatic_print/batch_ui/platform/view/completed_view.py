"""Readable labels for supplement batch candidates in platform views."""


def style_label(group) -> str:
    if group.order_composition != '单项单件':
        return '多件整单（不按底款拆分）'
    return f'{group.style_name or "名称未记录"}（ID: {group.style_id or "未记录"}）'


def selected_description(groups) -> str:
    return '\n'.join(
        f'{index}. {style_label(group)}｜颜色：'
        f'{group.color or "未记录" if group.order_composition == "单项单件" else "多件整单"}'
        f'｜物流：{group.logistics_code}｜面别：{group.face}'
        f'｜{len(group.item_ids)} 项 / {sum(qty for _, qty in group.item_quantities)} 件'
        for index, group in enumerate(groups, 1)
    )
