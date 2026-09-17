from pathlib import Path
from dataclasses import replace

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.domain.models import Placement
from automatic_print.layout_engine.orders.batch_analysis import finish_analysis
from automatic_print.layout_engine.orders.order_groups import order_key


class CountedPlan(list):
    visits = 0

    def __iter__(self):
        for value in super().__iter__():
            self.visits += 1
            yield value


def data(n):
    planned, orders = CountedPlan(), []
    for i in range(n):
        path = Path(f'B{i}-1-T-Black-M-NO1-1.png')
        p = Placement(path.name, i+1, (i % 2)*290, (i//2)*100, 200, 95,
                      0, 0, 0, 0, (i//2)*100, 200, 95)
        planned.append((path, p))
        orders.append({'order': f'B{i}', 'kind': '单件单面',
                       'items': [{'images': [{'path': str(path)}]}]})
    return {'orders': orders}, planned


def test_summary_visits_each_placement_twice_regardless_of_order_count():
    for n in (1000, 4000):
        report, planned = data(n)
        result = finish_analysis(report, planned, LayoutSettings(), 1000, 1000)
        assert planned.visits == 2*n
        assert len(result['orders']) == n
        for i, order in enumerate(result['orders']):
            assert order['companions'] == [f'B{i ^ 1}']
            assert '不跨尺码' in order['reason']
        assert 'companions' not in report['orders'][0]


def test_multi_piece_double_and_zone_rows_match_original_companion_definition():
    report, planned = data(20)
    # Merge several image records into a multi-piece order.
    report['orders'][0]['items'] += [report['orders'][i]['items'][0] for i in (2, 4)]
    report['orders'][0]['kind'] = '多件订单'
    report['orders'] = [o for i, o in enumerate(report['orders']) if i not in (2, 4)]
    planned[5] = planned[5][0], replace(planned[5][1], cut_zone='旋转区')
    result = finish_analysis(report, planned, LayoutSettings(), 1000, 1000)
    placements = dict(planned)
    for original, actual in zip(report['orders'], result['orders']):
        paths = {im['path'] for it in original['items'] for im in it['images']}
        rows = {(placements[Path(p)].cut_zone, placements[Path(p)].row_y_px) for p in paths}
        expected = {order_key(path).upper() for path, p in planned
                    if str(path) not in paths and (p.cut_zone, p.row_y_px) in rows}
        assert set(actual['companions']) == expected
    assert result['orders'][0]['companions'] == ['B1', 'B3']
