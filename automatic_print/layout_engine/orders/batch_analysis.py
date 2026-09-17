"""Serializable pre-layout inventory and the actual whole-order layout decisions."""
from collections import Counter, OrderedDict
from copy import deepcopy

from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.layout_engine.orders.order_groups import complete_orders, order_key, pair_identity, ordered_paths
from automatic_print.layout_engine.intake.metadata.source_metadata import (
    color_key, shape_hints, size_key, source_color, source_size,
)


def batch_inventory(paths):
    """Build batch, size, and locally-known color facts without decoding images."""
    orders, total_sizes = [], Counter()
    for group in complete_orders(ordered_paths(paths)):
        pieces = OrderedDict()
        for path in group:
            identity = pair_identity(path)
            pieces.setdefault(identity[0] if identity else str(path), []).append(path)
        known = order_key(group[0]) != '未识别订单组'
        orphan_back = any(len(members)==1 and pair_identity(members[0]) and
                          pair_identity(members[0])[1]=='2' for members in pieces.values())
        known = known and not orphan_back
        doubles = sum(len(members) == 2 for members in pieces.values())
        kind = ('多件订单' if len(pieces) > 1 else '单件双面' if doubles else '单件单面') if known else '待核对归属'
        rows, sizes = [], Counter()
        for members in pieces.values():
            size = source_size(members[0])
            sizes[size] += 1
            if known:
                total_sizes[size] += 1
            rows.append({'size': size, 'sides': len(members),
                         'images': [{'path': str(p), 'name': p.name} for p in members]})
        orders.append({'order': order_key(group[0]).upper(), 'kind': kind,
                       'pieces': len(pieces) if known else None, 'image_count': len(group),
                       'double_pairs': doubles, 'sizes': dict(sizes), 'items': rows,
                       'decision': '待测量', 'reason': '完整订单参与比较，不拆开正反面或多件商品'})
    kinds = Counter(order['kind'] for order in orders)
    batch_type = next(iter(kinds))+'批次' if len(kinds) == 1 else '混合批次'
    colors = Counter(source_color(path) for path in paths)
    unknown_colors = colors.pop('未识别颜色', 0)
    report = {'stage': '文件名分析', 'batch_type': batch_type, 'image_count': len(paths),
              'order_count': len(orders), 'kinds': dict(kinds), 'orders': orders,
              'piece_count': sum(o['pieces'] or 0 for o in orders),
              'double_pairs': sum(o['double_pairs'] for o in orders),
              'sizes': dict(sorted(total_sizes.items(), key=lambda entry: size_key(entry[0]))),
              'colors': dict(sorted(colors.items(), key=lambda entry: color_key(entry[0]))),
              'unrecognized_color_count': unknown_colors,
              'single_sizes': dict(Counter(size for o in orders if o['kind']=='单件单面'
                                           for size in o['sizes']))}
    report['group_distribution'] = group_distribution(report)
    return report


def analyze_batch(paths, settings, progress=None, ready=None):
    report = batch_inventory(paths)
    orders = report['orders']
    if ready:
        ready(deepcopy(report))
    count = 0
    for order in orders:
        hints, unreliable = set(), False
        for item in order['items']:
            for image in item['images']:
                from pathlib import Path
                size = print_dimensions(Path(image['path']), settings.dpi)
                flags = shape_hints(size.width_mm, size.height_mm)
                image.update(width_mm=round(size.width_mm,2), height_mm=round(size.height_mm,2),
                             reliable_dpi=size.embedded_dpi, hints=flags)
                hints.update(flags)
                unreliable |= not size.embedded_dpi
                count += 1
                if progress:
                    progress('分析批次', count, len(paths), image['name'])
        order['hints'] = sorted(hints)
        order['large_sizes'] = [s for s in order['sizes'] if s in {'2XL','3XL','4XL','5XL'}]
        order['decision'] = '待核对 DPI' if unreliable else '等待整批分区比较'
        reasons = ['尺寸为估算，不能确认切膜安全'] if unreliable else []
        if order['large_sizes']:
            reasons.append('大尺码重点核对实测宽度，不强行并排')
        if '竖向细长图' in hints:
            reasons.append('竖向细长图优先比较整单旋转')
        if '小幅图' in hints:
            reasons.append('小幅图可尝试搭配；多件与双面保持完整')
        order['reason'] = '；'.join(reasons) or '按尺码聚集并比较实际占位'
    report['stage'] = '排版前分析'
    if ready:
        ready(deepcopy(report))
    return report


def group_distribution(report):
    orders = [order for order in report.get('orders', ()) if order.get('pieces')]
    if any(order['pieces'] > 1 for order in orders):
        return {'kind': 'orders', 'title': '多件批次订单群分布',
                'items': [(order['order'], order['pieces']) for order in orders]}
    return {'kind': 'sizes', 'title': '单件批次尺码群分布',
            'items': list(report.get('sizes', {}).items())}


def distribution_text(report, limit=None):
    distribution = report.get('group_distribution') or group_distribution(report)
    items = distribution['items']
    shown = items if limit is None else items[:limit]
    suffix = f'，另有{len(items)-len(shown)}项' if len(shown) < len(items) else ''
    unit = '件' if distribution['kind'] == 'orders' else ''
    values = '、'.join(f'{name}-{count}{unit}' for name, count in shown) or '无可识别数据'
    return f"{distribution['title']}：{values}{suffix}"


def compact_distribution_text(report, limit=None):
    """Short table text; the column heading already explains the grouping."""
    distribution = report.get('group_distribution') or group_distribution(report)
    items = distribution['items']
    shown = items if limit is None else items[:limit]
    values = ' · '.join(f'{name} {count}件' for name, count in shown)
    if len(shown) < len(items):
        values += f' · +{len(items)-len(shown)}项'
    return values or '—'


def finish_analysis(report, planned, settings, height, baseline):
    result = deepcopy(report)
    placements = {str(path): p for path, p in planned}
    owners = {image['path']: index for index, order in enumerate(result['orders'])
              for item in order['items'] for image in item['images']}
    rows = {}
    for path, p in planned:
        rows.setdefault((p.cut_zone, p.row_y_px), {})[owners[str(path)]] = order_key(path).upper()
    peers = [{} for _ in result['orders']]
    for row in rows.values():
        for index in row:
            for other, name in row.items():
                if index != other:
                    peers[index][name] = None
    for index, order in enumerate(result['orders']):
        members = [placements[image['path']] for item in order['items'] for image in item['images']]
        zones = {p.cut_zone or '常规区' for p in members}
        order['decision'] = ' / '.join(sorted(zones))
        companions = list(peers[index])
        order['companions'] = companions
        if zones == {'旋转区'}:
            reason = ('整单旋转后可安全放入；计入区域间隔后整批方案更短' if baseline > height
                      else '整单旋转后可安全放入；常规区没有可行的整批固定刀位')
        elif companions:
            reason = '与 '+ '、'.join(companions) + ' 安全并排'
        elif order.get('rotation_policy_skip'):
            reason = '单件并排优先；保留常规尺码块，不拆尺码或改变生产顺序'
        elif order.get('rotation_eligible') is False:
            reason = '整单中有图片不具备安全旋转条件（膜标签或可用空间），无法整体进入旋转区，保留完整订单在常规区'
        elif order.get('rotation_eligible'):
            reason = '尺寸允许旋转；整批比较后保留常规区，避免增加用膜'
        else:
            reason = '按当前模式保持整单，旋转区未启用'
        if order['kind'] == '单件单面':
            reason += '；同尺码保持连续，不跨尺码搭配'
        if order.get('large_sizes'):
            reason += '；'+ '/'.join(order['large_sizes'])+' 已核对实际宽度'
        order['reason'] = reason
    result.update(stage='排版结果', height_m=height*25.4/settings.dpi/1000,
                  saved_m=max(0,baseline-height)*25.4/settings.dpi/1000)
    return result


def attach_rotation_options(report, rotated_items, settings, ready=None):
    from pathlib import Path
    spacing = settings.spacing_mm
    for order in report['orders']:
        paths = [Path(image['path']) for item in order['items'] for image in item['images']]
        unfit = [p.name for p in paths if p not in rotated_items]
        order['rotation_eligible'] = not unfit
        order['rotation_unfit'] = unfit
        if unfit:
            order['decision'] = '不适合整单旋转'
            order['reason'] = '膜标签或旋转占位不满足安全条件：'+'、'.join(unfit)
        else:
            order['rotation_length_mm'] = sum(rotated_items[p].footprint_height*25.4/settings.dpi for p in paths)+(len(paths)-1)*spacing+2*settings.margin_mm
            order['decision'] = '可以整单旋转，比较整批长度'
    report['stage'] = '分区候选分析'
    if ready:
        ready(deepcopy(report))
