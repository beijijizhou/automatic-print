import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QLabel

from automatic_print.ui.quick_fields import show_selected_batch_summary


APP = QApplication.instance() or QApplication([])


class Panel:
    selected_source = QLabel()


def test_selected_batch_card_shows_compact_analysis_and_gap_counts(tmp_path):
    panel = Panel()
    folder = tmp_path / 'HALOO-609162003063'
    report = {
        'batch_type': '单件单面批次',
        'order_count': 63,
        'piece_count': 63,
        'image_count': 63,
        'double_pairs': 0,
        'sizes': {'2XL': 12, '3XL': 18, '4XL': 20, '5XL': 13},
        'orders': [],
        's2b_metadata': [{
            'batch_number': '22UJ9KT4VCZA',
            'local_images': 63,
            'api_total': 63,
            'matched_images': 63,
            'colors': {'白色': 21, '黑色': 42},
        }],
        'header_gap': [
            {'added_px': 32, 'warning': ''},
            {'added_px': 0, 'warning': ''},
            {'added_px': 0, 'warning': '未找到可靠膜标签分界'},
        ],
    }
    show_selected_batch_summary(panel, folder, report)
    text = panel.selected_source.text()
    assert '当前批次：HALOO-609162003063' in text
    assert '63 个订单组 · 63 件 / 63 张图' in text
    assert '尺码群：2XL 12件 · 3XL 18件 · 4XL 20件 · 5XL 13件' in text
    assert '膜间距：扩充 1/3 张，已满足 1 张，未扩充 1 张' in text
    assert 'S2B批次信息：22UJ9KT4VCZA' in text
    assert '颜色：白色21张、黑色42张' in text
    assert str(folder) in text
    assert '单件批次尺码群分布' in panel.selected_source.toolTip()


def test_selected_batch_card_prioritizes_size_and_pending_color(tmp_path):
    panel = Panel()
    folder = tmp_path / 'AS2B014Mt'
    report = {
        'batch_type': '单件单面批次', 'order_count': 2, 'piece_count': 2,
        'image_count': 2, 'double_pairs': 0, 'sizes': {'S': 1, 'M': 1},
        'orders': [], 's2b_metadata_pending': True,
    }
    show_selected_batch_summary(panel, folder, report)
    lines = panel.selected_source.text().splitlines()
    assert lines[1] == '尺码群：S 1件 · M 1件'
    assert lines[2] == '颜色：正在读取 S2B 订单信息…'
