from pathlib import Path
from PySide6.QtCore import Qt
from automatic_print.ui.batch_status_board import BatchStatusBoard
from test_developer_mode import APP


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
        assert f'{index+1}/20' in board.items[index].text(1)
        assert f'image-{index}.png' in board.items[index].toolTip(1)
        assert not board.items[index].icon(0).isNull()
    board.setCurrentIndex(2)
    before = list(selected)
    board.update_batch(2, '批次预览完成')
    assert board.currentIndex() == 2
    assert selected == before  # Moving between groups does not change the preview.
    assert board.items[2].isSelected()
    board.update_batch(1, '批次失败，继续下一批', 0, 0, 'bad file')
    assert board.groups['已完成'].topLevelItemCount() == 1
    assert board.groups['进行中'].topLevelItemCount() == 2
    assert board.groups['未完成'].topLevelItemCount() == 3
    assert '失败' in board.items[1].text(1)
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
