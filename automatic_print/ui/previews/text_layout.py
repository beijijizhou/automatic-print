"""Fast, copyable batch preview from filename facts and planned coordinates."""
from collections import defaultdict
from bisect import bisect_right
from pathlib import Path
from unicodedata import east_asian_width

from ...layout_engine.intake.metadata.source_metadata import size_key


def inventory_text(report):
    orders = report.get('orders') or ()
    if not orders:
        return '等待读取批次文件名…'
    lines = [
        f"文件名已读取 · {report.get('image_count', 0)} 张图 · {len(orders)} 个订单",
        '尚未计算排版，暂时无法判断单排或双排；勾选“仅计算排版（不生成文件）”后点击开始排版。',
        '下列订单、件数和尺码来自文件名。',
    ]
    for title, kind in (('多件订单', '多件订单'),
                        ('单件单面', '单件单面'),
                        ('单件双面', '单件双面')):
        members = [order for order in orders if order.get('kind') == kind]
        if members:
            lines.extend(('', title, *(_order_label(order) for order in members)))
    uncertain = [order for order in orders if order.get('kind') not in {
        '多件订单', '单件单面', '单件双面'}]
    if uncertain:
        lines.extend(('', '归属待核对', *(_order_label(order) for order in uncertain)))
    return '\n'.join(lines)


def layout_text(payload):
    planned = payload.get('planned') or ()
    report = payload.get('analysis') or {}
    orders = report.get('orders') or ()
    if not planned or not orders:
        return inventory_text(report)
    sources = {str(Path(image['path'])): (index, _image_label(order, item, item_index, face))
               for index, order in enumerate(orders)
               for item_index, item in enumerate(order.get('items', ()), 1)
               for face, image in enumerate(item.get('images', ()), 1)}
    placed = defaultdict(list)
    positioned = defaultdict(list)
    unmatched = []
    for path, placement in planned:
        source = sources.get(str(path))
        if source is None:
            unmatched.append(Path(path).name)
        else:
            index, label = source
            placed[index].append(placement)
            positioned[placement.cut_zone or '常规区'].append((placement, label))
    rows = {y: index for index, y in enumerate(sorted({
        placement.row_y_px for _, placement in planned}), 1)}
    settings = payload.get('settings')
    lines = [f'文字排版预览 · {len(orders)} 个订单 · {len(planned)} 张图']
    counts = {len(_knives(p)) + 1 for _, p in planned}
    if counts == {1}:
        lines.append('本次排版：单排（无中间分割线）')
    elif counts == {2}:
        lines.append('本次排版：双排（逐排显示中间分割线）')
    else:
        lines.append('本次排版：混合单排与多列（各区逐排显示）')
    if payload.get('warning'):
        lines.append('仅供检查：' + str(payload['warning']))
    for zone in ('并排区', '常规区', '旋转区', '单排区'):
        if zone in positioned:
            lines.extend(('', *_zone_chart(zone, positioned.pop(zone), rows, settings)))
    for zone, members in positioned.items():
        lines.extend(('', *_zone_chart(zone, members, rows, settings)))
    lines.extend(('', '订单归属'))
    buckets = defaultdict(list)
    for index, order in enumerate(orders):
        placements = placed.get(index, ())
        if not placements:
            buckets['未放入排版'].append((0, _order_label(order)))
            continue
        bucket = _position(placements, settings)
        first_row = min(rows[p.row_y_px] for p in placements)
        buckets[bucket].append((first_row, f'第{first_row}排  {_order_label(order)}'))
    for name in ('并排区 · 左侧', '并排区 · 右侧', '旋转区', '常规区',
                 '跨侧或跨区（需核查）', '未放入排版'):
        if buckets.get(name):
            lines.extend(('', name, *(label for _, label in sorted(buckets.pop(name)))))
    for name, entries in buckets.items():
        lines.extend(('', name, *(label for _, label in sorted(entries))))
    if unmatched:
        lines.extend(('', f'未匹配订单信息：{len(unmatched)} 张', *unmatched))
    return '\n'.join(lines)


def _zone_chart(zone, members, rows, settings):
    knives = next((_knives(p) for p, _ in members if _knives(p)), ())
    count = len(knives) + 1
    mode = '单排' if count == 1 else '双排' if count == 2 else f'{count}列'
    title = f'{zone} · {mode}'
    if knives and settings is not None:
        title += ' · 分割线 ' + '、'.join(f'{x * 25.4 / settings.dpi:g} 毫米'
                                          for x in knives)
    by_row = defaultdict(lambda: [[] for _ in range(count)])
    for placement, label in members:
        by_row[placement.row_y_px][bisect_right(knives, placement.x_px)].append(
            (placement.x_px, placement.y_px, placement.sequence_number, label))
    lines = [title]
    headings = ['左侧', '右侧'] if count == 2 else [f'第{i}列' for i in range(1, count + 1)]
    if count == 1:
        headings = ['内容']
    rendered = []
    for y in sorted(by_row):
        cells = ['、'.join(entry[3] for entry in sorted(column)) or '—'
                 for column in by_row[y]]
        rendered.append((f'{rows[y]:02d}', cells))
    widths = [max(_display_width(headings[i]), *(_display_width(cells[i])
                    for _, cells in rendered)) for i in range(count)]
    lines.append('排次 ' + ' │ '.join(_pad(headings[i], widths[i])
                                     for i in range(count)))
    lines.append('─────' + '─┼─'.join('─' * width for width in widths))
    lines.extend(number + '   ' + ' │ '.join(_pad(cells[i], widths[i])
                                             for i in range(count))
                 for number, cells in rendered)
    return lines


def _knives(placement):
    return tuple(getattr(placement, 'cut_knife_xs_px', ()) or
                 ((placement.cut_knife_x_px,)
                  if placement.cut_knife_x_px is not None else ()))


def _display_width(value):
    return sum(2 if east_asian_width(character) in 'FW' else 1 for character in value)


def _pad(value, width):
    return value + ' ' * (width - _display_width(value))


def _image_label(order, item, item_index, face):
    size = item.get('size') or '尺码待核对'
    images = item.get('images', ())
    side = f' {"A" if face == 1 else "B"}面' if len(images) == 2 else ''
    if order.get('kind') in {'单件单面', '单件双面'}:
        return size + side
    number = order.get('order') or '订单待核对'
    pieces = order.get('pieces')
    return f'{number}-{pieces}件-{size}（第{item_index}件{side}）'


def _position(placements, settings):
    zones = {p.cut_zone or '常规区' for p in placements}
    if len(zones) != 1:
        return '跨侧或跨区（需核查）'
    zone = next(iter(zones))
    if zone != '并排区':
        return zone
    knife = next((p.cut_knife_x_px for p in placements
                  if p.cut_knife_x_px is not None), None)
    if knife is None and settings is not None:
        knife = round(settings.cutter_knife_mm * settings.dpi / 25.4)
    if knife is None:
        return '并排区 · 刀位待核对'
    sides = {'左侧' if p.x_px < knife else '右侧' for p in placements}
    return '并排区 · ' + next(iter(sides)) if len(sides) == 1 else '跨侧或跨区（需核查）'


def _order_label(order):
    sizes = order.get('sizes') or {}
    size_text = '、'.join(
        size if count == 1 else f'{size}×{count}'
        for size, count in sorted(sizes.items(), key=lambda entry: size_key(entry[0]))
    ) or '尺码待核对'
    kind = order.get('kind')
    if kind == '单件单面':
        return size_text
    if kind == '单件双面':
        return f'{size_text} A面＋B面'
    number = order.get('order') or '订单待核对'
    pieces = order.get('pieces')
    title = f'{number}-{pieces}件-{size_text}' if pieces else f'{number}-件数待核对-{size_text}'
    double_items = [f"第{index}件 {item.get('size') or '尺码待核对'} A面＋B面"
                    for index, item in enumerate(order.get('items', ()), 1)
                    if len(item.get('images', ())) == 2]
    return title + (f"（{'；'.join(double_items)}）" if double_items else '')
