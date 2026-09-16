"""Fast whole-batch preview labels built from existing order analysis."""
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen, QTransform

from .platform_preview import draw_platform_badge


PALETTE = (
    ('#dbeafe', '#1d4ed8'),
    ('#ede9fe', '#6d28d9'),
    ('#fef3c7', '#b45309'),
    ('#dcfce7', '#15803d'),
    ('#ffe4e6', '#be123c'),
    ('#cffafe', '#0e7490'),
)


def schematic_items(report):
    result = {}
    for order_index, order in enumerate(report.get('orders', ())):
        kind = order.get('kind', '待核对归属')
        sizes = _sizes_text(order.get('sizes', {}))
        group_key = sizes if kind in {'单件单面', '单件双面'} else order.get('order', '')
        color = PALETTE[_group_color(group_key, kind, order_index)]
        for item in order.get('items', ()):
            size = item.get('size') or '尺码待核对'
            images = item.get('images', ())
            for face, image in enumerate(images, 1):
                if kind == '单件单面':
                    title, detail = f'{size} 尺码群', '普通单件'
                elif kind == '单件双面':
                    title = f'双面 {size} 尺码群'
                    detail = '正面' if face == 1 else '背面'
                elif kind == '多件订单':
                    title = f"订单 {str(order.get('order', '待核对'))[:12]}"
                    detail = f'尺码群 {sizes} · 当前 {size}'
                    if len(images) == 2:
                        detail += ' · '+('正面' if face == 1 else '背面')
                else:
                    title, detail = f'待核对 · {size}', sizes
                entry = {'title': title, 'detail': detail, 'colors': color, 'kind': kind}
                path = str(image.get('path', ''))
                result[path] = entry
                try:
                    result[str(Path(path).resolve())] = entry
                except OSError:
                    pass
    return result


def fallback_item(path):
    from ..layout_engine.order_groups import order_key, pair_identity
    from ..layout_engine.source_metadata import source_size
    size = source_size(path)
    pair = pair_identity(path)
    order = order_key(path).upper()
    title = f'双面 {size} 尺码群' if pair else f'{size} 尺码群'
    detail = ('正面' if pair and pair[1] == '1' else
              '背面' if pair else f'订单 {order[:12]}' if order != '未识别订单组' else '单件')
    colors = PALETTE[_stable_index(size if not pair else pair[0]) % len(PALETTE)]
    return {'title': title, 'detail': detail, 'colors': colors, 'kind': '待核对归属'}


def draw_preview_placement(preview, painter, path, placement, rect, pending, scale):
    if preview.overview:
        draw_schematic_item(
            painter, rect, _preview_entry(preview, path), placement.sequence_number,
            placement.rotation_degrees, pending, scale,
        )
    else:
        image = preview.images[path].transformed(
            QTransform().rotate(-placement.rotation_degrees))
        painter.drawImage(rect, image)
        painter.setPen(QPen(QColor(
            '#94a3b8' if pending or preview.composed_count is None else '#16a34a'), 0))
        painter.drawRect(rect)
        if pending:
            painter.fillRect(rect, QColor(248, 250, 252, 180))
        if path in preview.badges:
            painter.drawImage(
                QRectF(placement.number_x_px, placement.number_y_px,
                       placement.number_width_px, placement.number_height_px),
                preview.badges[path],
            )
        draw_platform_badge(preview, painter, placement)
    if placement.color_block_width_px:
        painter.fillRect(
            QRectF(placement.color_block_x_px, placement.color_block_y_px,
                   placement.color_block_width_px, placement.color_block_height_px),
            QColor(preview.render_settings.color_block_color),
        )


def _preview_entry(preview, path):
    report = ((preview.batch_payload or {}).get('analysis')
              or preview.analysis_report or {})
    if report is not preview._schematic_report:
        preview._schematic_report = report
        preview._schematic_items = schematic_items(report)
    return (preview._schematic_items.get(str(path))
            or preview._schematic_items.get(str(path.resolve()))
            or fallback_item(path))


def draw_schematic_item(
        painter, rect, entry, sequence, rotation=0, pending=False,
        display_scale=1.0):
    fill, ink = entry['colors']
    display_scale = max(.001, display_scale)
    painter.save()
    try:
        painter.setPen(QPen(QColor(ink), 1/display_scale))
        painter.setBrush(QColor(fill))
        radius = 5/display_scale
        painter.drawRoundedRect(rect, radius, radius)
        inset = max(2/display_scale, min(rect.width(), rect.height())*.04)
        text_rect = rect.adjusted(inset, inset, -inset, -inset)
        suffix = f' · 旋转{rotation}°' if rotation % 360 else ''
        text = f"{entry['title']}\n{entry['detail']}\n#{sequence}{suffix}"
        font = QFont()
        font.setBold(True)
        # The painter is scaled to the film width. Keep labels readable on screen,
        # while still shrinking them when a physical item is genuinely tiny.
        desired = round(13/display_scale)
        available = round(min(rect.width()/8, rect.height()/5))
        font.setPixelSize(max(7, min(desired, available)))
        painter.setFont(font)
        painter.setPen(QColor(ink))
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, text)
        if pending:
            painter.fillRect(rect, QColor(248, 250, 252, 175))
    finally:
        painter.restore()


def _sizes_text(sizes):
    return ' · '.join(f'{size}×{count}' for size, count in sizes.items()) or '尺码待核对'


def _stable_index(value):
    return sum((index+1)*ord(character) for index, character in enumerate(str(value)))


def _group_color(group_key, kind, order_index):
    if kind in {'单件单面', '单件双面'}:
        common_sizes = ('XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL', '5XL')
        normalized = str(group_key).upper().strip()
        if normalized in common_sizes:
            return common_sizes.index(normalized) % len(PALETTE)
    return _stable_index(group_key or str(order_index)) % len(PALETTE)
