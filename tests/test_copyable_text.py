import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QLabel, QCheckBox, QPushButton,
    QGroupBox, QTabBar, QComboBox, QTableWidget, QTableWidgetItem, QLineEdit,
    QMenu, QProgressBar)
from automatic_print.ui.copyable_text import install_text_copying, text_at, selected_text

APP = QApplication.instance() or QApplication([])
OWNERS = []


def context_copy(widget, pos=None):
    pos = pos or widget.rect().center()
    APP.clipboard().clear()
    def choose():
        menu = APP.activePopupWidget()
        assert isinstance(menu, QMenu)
        assert menu.actions()[0].text() == '复制文字'
        menu.actions()[0].trigger()
        menu.close()
    QTimer.singleShot(0, choose)
    APP.sendEvent(widget, QContextMenuEvent(QContextMenuEvent.Mouse, pos, widget.mapToGlobal(pos)))
    return APP.clipboard().text()


def show(widget):
    OWNERS.append(widget)
    widget.resize(300, 100)
    widget.show()
    APP.processEvents()
    return widget


def test_labels_are_selectable_including_future_widgets_and_links():
    install_text_copying()
    label = QLabel('仅预览，不生成文件')
    label.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
    show(label)
    flags = label.textInteractionFlags()
    assert flags & Qt.TextSelectableByMouse
    assert flags & Qt.TextSelectableByKeyboard
    assert flags & Qt.LinksAccessibleByMouse
    label.setSelection(0, 3)
    label.setFocus()
    QTest.keyClick(label, Qt.Key_C, Qt.ControlModifier)
    assert APP.clipboard().text() == '仅预览'
    handler = APP.automatic_print_text_copy_filter
    install_text_copying()
    assert APP.automatic_print_text_copy_filter is handler
    assert context_copy(label) == '仅预览，不生成文件'
    rich = show(QLabel('<b>当前批次</b>：58张'))
    assert context_copy(rich) == '当前批次：58张'


def test_checkbox_and_button_right_copy_does_not_activate():
    install_text_copying()
    checkbox = show(QCheckBox('仅预览，不生成文件'))
    assert context_copy(checkbox) == '仅预览，不生成文件'
    assert not checkbox.isChecked()
    QTest.mouseClick(checkbox, Qt.LeftButton, pos=QPoint(10, 50))
    assert checkbox.isChecked()
    calls = []
    button = show(QPushButton('单批次排版'))
    button.clicked.connect(lambda: calls.append(True))
    assert context_copy(button) == '单批次排版'
    assert calls == []
    QTest.mouseClick(button, Qt.LeftButton)
    assert calls == [True]


def test_titles_tabs_progress_and_dropdown_are_copyable():
    install_text_copying()
    group = show(QGroupBox('排版规则'))
    assert context_copy(group) == '排版规则'
    tabs = show(QTabBar())
    tabs.addTab('当前批次耗时')
    tabs.addTab('58张实图基准')
    assert context_copy(tabs, tabs.tabRect(1).center()) == '58张实图基准'
    assert tabs.currentIndex() == 0
    combo = show(QComboBox())
    combo.addItems(['隆丰', '其他平台'])
    assert context_copy(combo) == '隆丰'
    assert combo.currentIndex() == 0
    progress = show(QProgressBar())
    progress.setValue(50)
    assert context_copy(progress) == '50%'


def test_tables_copy_cells_headers_and_selection_without_losing_zero():
    install_text_copying()
    table = show(QTableWidget(2, 2))
    table.setHorizontalHeaderLabels(['步骤', '耗时'])
    for row, values in enumerate([['扫描文件名', '0'], ['保存输出图片', '8.87秒']]):
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(value))
    table.selectAll()
    assert selected_text(table) == '扫描文件名\t0\n保存输出图片\t8.87秒'
    table.setFocus()
    QTest.keyClick(table, Qt.Key_C, Qt.ControlModifier)
    assert APP.clipboard().text() == selected_text(table)
    pos = table.visualItemRect(table.item(0, 1)).center()
    assert context_copy(table.viewport(), pos) == '0'
    header = table.horizontalHeader()
    assert context_copy(header.viewport(), QPoint(10, 10)) == '步骤'


def test_editable_text_keeps_native_actions():
    install_text_copying()
    line = show(QLineEdit('可编辑标签'))
    line.selectAll()
    line.setFocus()
    QTest.keyClick(line, Qt.Key_C, Qt.ControlModifier)
    assert APP.clipboard().text() == '可编辑标签'
    assert line.text() == '可编辑标签'
