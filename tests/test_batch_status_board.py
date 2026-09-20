from pathlib import Path
from PySide6.QtCore import Qt
from automatic_print.ui.batch_status_board import BatchStatusBoard
from automatic_print.ui.batch_distribution import BatchDistributionLabel
from test_developer_mode import APP


def test_compact_distribution_sits_above_preview_without_verbose_copy():
    label = BatchDistributionLabel()
    label.show_report({'sizes': {'S': 12, 'M': 8}})
    assert label.text() == '尺码群：S 12件 · M 8件'
    assert '单件批次尺码群分布' in label.toolTip()
    label.show_report({'orders': [
        {'order': 'ORDER-A', 'pieces': 3},
        {'order': 'ORDER-B', 'pieces': 1},
    ]})
    assert label.text() == '订单群：ORDER-A 3件 · ORDER-B 1件'


def test_all_batches_are_visible_in_three_groups_with_live_independent_states(tmp_path):
    board = BatchStatusBoard()
    folders = [Path(tmp_path/f'batch-{i}') for i in range(6)]
    selected = []
    board.currentIndexChanged.connect(selected.append)
    board.reset(folders)
    assert board.groups['未完成'].topLevelItemCount() == 6
    for index in range(4):
        board.update_batch(index, '读取图片尺寸', index+1, 20, f'image-{index}.png')
    assert board.groups['进行中'].topLevelItemCount() == 4
    assert board.groups['未完成'].topLevelItemCount() == 2
    for index in range(4):
        assert f'{index+1}/20' in board.items[index].toolTip(0)
        assert f'image-{index}.png' in board.items[index].toolTip(0)
        assert not board.items[index].icon(0).isNull()
    board.setCurrentIndex(2)
    before = list(selected)
    board.update_batch(2, '批次预览完成')
    board.update_distribution(2, {'sizes': {'S': 12, 'M': 8}})
    assert board.items[2].text(2) == 'S 12件 · M 8件'
    assert board.currentIndex() == 2
    assert selected == before  # Moving between groups does not change the preview.
    assert board.items[2].isSelected()
    board.update_batch(1, '批次失败，继续下一批', 0, 0, 'bad file')
    assert board.groups['已完成'].topLevelItemCount() == 1
    assert board.groups['进行中'].topLevelItemCount() == 2
    assert board.groups['未完成'].topLevelItemCount() == 3
    assert '失败' in board.items[1].toolTip(0)
    board.groups['未完成'].setCurrentItem(board.items[5])
    assert selected[-1] == 5
    board.resize(900, 230)
    board.show()
    APP.processEvents()
    assert board.grab().save(str(tmp_path/'batch-status-board.png'))
    board.reset([folders[0]])
    assert len(board.items) == 1
    assert board.groups['已完成'].topLevelItemCount() == 0
    assert board.groups['进行中'].topLevelItemCount() == 0
    assert board.groups['未完成'].topLevelItemCount() == 1
    board.close()


def test_same_folder_source_is_not_shown_as_dot_and_child_opens_parent(tmp_path):
    root = tmp_path/'batch'
    child = root/'S'
    board = BatchStatusBoard()
    board.reset([root], root, {0: {'source_batches': [
        {'folder': root, 'image_count': 1}, {'folder': child, 'image_count': 2}]}})
    item = board.items[0]
    assert item.childCount() == 1
    assert item.child(0).text(0) == 'S'
    requested = []
    board.recordRequested.connect(requested.append)
    board.groups['未完成'].setCurrentItem(item.child(0))
    assert board.currentIndex() == 0
    board.request_record(item.child(0))
    assert requested == [0]
    board.close()
