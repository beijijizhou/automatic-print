"""GUI-thread global text copying without changing controls' left-click actions."""
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtGui import QTextDocumentFragment
import re
from PySide6.QtWidgets import (QApplication, QLabel, QAbstractButton, QGroupBox,
    QProgressBar, QComboBox, QTabBar, QHeaderView, QAbstractItemView, QMenu,
    QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QWidget, QSplashScreen,
    QCheckBox, QHBoxLayout)


def selectable(label):
    label.setTextInteractionFlags(label.textInteractionFlags() |
        Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)


def copyable_checkbox(text, tooltip='', parent=None):
    """Keep the toggle compact while making its visible caption selectable."""
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    checkbox = QCheckBox(container)
    label = QLabel(text, container)
    selectable(label)
    if tooltip:
        for widget in (container, checkbox, label):
            widget.setToolTip(tooltip)
    layout.addWidget(checkbox)
    layout.addWidget(label)
    layout.addStretch()
    return container, checkbox, label


def clean_caption(text):
    return str(text).replace('&&', '\0').replace('&', '').replace('\0', '&')


def display_text(value):
    return '' if value is None else str(value)


def selected_text(view):
    if view.selectionModel() is None:
        return ''
    indexes = sorted(view.selectionModel().selectedIndexes(), key=lambda i: (i.row(), i.column()))
    if not indexes:
        return ''
    rows = {}
    for index in indexes:
        rows.setdefault(index.row(), {})[index.column()] = display_text(index.data())
    columns = sorted({i.column() for i in indexes})
    return '\n'.join('\t'.join(row.get(column, '') for column in columns) for row in rows.values())


def text_at(widget, pos):
    if isinstance(widget, QLabel):
        text = widget.text()
        rich = widget.textFormat() == Qt.RichText or (widget.textFormat() == Qt.AutoText and
            re.search(r'<(?:html|qt|p|b|strong|span|font|a|div|i|u|br)(?:\s|/?>)', text, re.I))
        return QTextDocumentFragment.fromHtml(text).toPlainText() if rich else text
    if isinstance(widget, QHeaderView):
        if widget.model() is None:
            return ''
        section = widget.logicalIndexAt(pos)
        return display_text(widget.model().headerData(section, widget.orientation())) if section >= 0 else ''
    if isinstance(widget, QAbstractItemView):
        index = widget.indexAt(widget.viewport().mapFrom(widget, pos))
        return display_text(index.data()) if index.isValid() else ''
    if isinstance(widget, QTabBar):
        index = widget.tabAt(pos)
        return clean_caption(widget.tabText(index)) if index >= 0 else ''
    if isinstance(widget, QGroupBox):
        return clean_caption(widget.title())
    if isinstance(widget, QComboBox):
        return widget.currentText()
    if isinstance(widget, (QAbstractButton, QProgressBar)):
        return clean_caption(widget.text())
    if isinstance(widget, QSplashScreen):
        return widget.message()
    if widget.isWindow():
        return widget.windowTitle()
    return ''


class TextCopyFilter(QObject):
    def eventFilter(self, watched, event):
        kind = event.type()
        if isinstance(watched, QLabel) and kind in (QEvent.Polish, QEvent.Show):
            selectable(watched)
        if kind == QEvent.KeyPress and isinstance(watched, QAbstractItemView):
            if event.matches(QKeySequence.Copy):
                text = selected_text(watched)
                if text:
                    QApplication.clipboard().setText(text)
                    return True
        if kind != QEvent.ContextMenu or not isinstance(watched, QWidget):
            return False
        # Keep editable text's own copy/paste/undo menus and label selection intact.
        if isinstance(watched, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
            return False
        widget, pos = watched, event.pos()
        if isinstance(widget.parentWidget(), QAbstractItemView):
            parent = widget.parentWidget()
            pos, widget = widget.mapTo(parent, pos), parent
        text = text_at(widget, pos)
        if not text:
            return False
        # Do not replace application-specific menus on controls that already own one.
        if widget.contextMenuPolicy() in (Qt.CustomContextMenu, Qt.ActionsContextMenu):
            return False
        menu = QMenu(widget)
        copy = menu.addAction('复制文字')
        copy.triggered.connect(lambda: QApplication.clipboard().setText(text))
        if isinstance(widget, QLabel) and widget.hasSelectedText():
            selection = widget.selectedText()
            action = menu.addAction('复制选中文字')
            action.triggered.connect(lambda: QApplication.clipboard().setText(selection))
        if isinstance(widget, QAbstractItemView):
            selection = selected_text(widget)
            if selection:
                action = menu.addAction('复制选中内容')
                action.triggered.connect(lambda: QApplication.clipboard().setText(selection))
        menu.exec(event.globalPos())
        menu.deleteLater()
        return True


def install_text_copying():
    app = QApplication.instance()
    if app is None or getattr(app, 'automatic_print_text_copy_filter', None):
        return
    handler = TextCopyFilter(app)
    app.automatic_print_text_copy_filter = handler
    app.installEventFilter(handler)
    for window in app.topLevelWidgets():
        if isinstance(window, QLabel):
            selectable(window)
        for label in window.findChildren(QLabel):
            selectable(label)
