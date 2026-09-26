"""Visual editor for free-layout and cutter label placement policies."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout, QWidget,
)


def _mirror(source: QComboBox) -> QComboBox:
    target = QComboBox()
    for index in range(source.count()):
        target.addItem(source.itemText(index), source.itemData(index))
    target.setCurrentIndex(source.currentIndex())
    target.currentIndexChanged.connect(source.setCurrentIndex)
    source.currentIndexChanged.connect(target.setCurrentIndex)
    return target


class LabelPositionDiagram(QWidget):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.values = values
        self.setMinimumSize(720, 280)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#f8fafc'))
        width = (self.width()-40)/3
        for index, title in enumerate(('无刀码', '刀码 · 未旋转', '刀码 · 旋转90°')):
            panel = QRectF(10+index*(width+10), 12, width, self.height()-24)
            painter.setPen(QPen(QColor('#cbd5e1'), 1))
            painter.setBrush(QColor('white'))
            painter.drawRoundedRect(panel, 8, 8)
            painter.setPen(QColor('#0f172a'))
            painter.setFont(QFont('', 10, QFont.Weight.Bold))
            painter.drawText(QRectF(panel.left(), panel.top()+8, panel.width(), 24),
                             Qt.AlignmentFlag.AlignCenter, title)
            self._draw_case(painter, panel, index)
        painter.end()

    def _draw_case(self, painter, panel, case):
        image = QRectF(panel.left()+30, panel.top()+62, panel.width()-60, 125)
        if case == 2:
            image = QRectF(panel.left()+50, panel.top()+48, panel.width()-100, 165)
        painter.setPen(QPen(QColor('#2563eb'), 2))
        painter.setBrush(QColor('#dbeafe'))
        painter.drawRoundedRect(image, 5, 5)
        label = QRectF(0, 0, min(90, image.width()*.46), 25)
        if case == 0:
            self._free_position(label, image, self.values()['free'])
        elif case == 1:
            card = QRectF(image.left()+8, image.top()+8, 48, 54)
            self._card(painter, card)
            label.moveLeft(card.right()+7)
            align = self.values()['vertical']
            y = {'top': card.top(), 'center': card.center().y()-label.height()/2,
                 'bottom': card.bottom()-label.height()}.get(align, card.top())
            label.moveTop(y)
        else:
            card = QRectF(image.left()+22, image.bottom()-58, image.width()-44, 48)
            self._card(painter, card)
            align = self.values()['rotated']
            x = {'left': card.left(), 'center': card.center().x()-label.width()/2,
                 'right': card.right()-label.width()}.get(align, card.left())
            label.moveLeft(x)
            label.moveBottom(card.top()-7)
        painter.setPen(QPen(QColor('#7e22ce'), 2))
        painter.setBrush(QColor('#f3e8ff'))
        painter.drawRoundedRect(label, 4, 4)
        painter.setPen(QColor('#581c87'))
        painter.setFont(QFont('', 8))
        painter.drawText(label, Qt.AlignmentFlag.AlignCenter, '标签文字')
        painter.setPen(QColor('#64748b'))
        painter.drawText(QRectF(panel.left()+8, panel.bottom()-42, panel.width()-16, 28),
                         Qt.AlignmentFlag.AlignCenter,
                         '最终输出仍逐图检查透明区域')

    @staticmethod
    def _card(painter, rect):
        painter.setPen(QPen(QColor('#f97316'), 2))
        painter.setBrush(QColor('#ffedd5'))
        painter.drawRect(rect)
        painter.setPen(QColor('#9a3412'))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, '膜标签')

    @staticmethod
    def _free_position(label, image, position):
        gap = 8
        if position in {'top', 'top_left', 'top_right'}:
            label.moveBottom(image.top()-gap)
        elif position in {'bottom', 'bottom_left', 'bottom_right', 'block_below'}:
            label.moveTop(image.bottom()+gap)
        else:
            label.moveTop(image.center().y()-label.height()/2)
        if position in {'left'}:
            label.moveRight(image.left()-gap)
        elif position in {'right'}:
            label.moveLeft(image.right()+gap)
        elif position.endswith('_left'):
            label.moveLeft(image.left())
        elif position.endswith('_right'):
            label.moveRight(image.right())
        else:
            label.moveLeft(image.center().x()-label.width()/2)


class LabelPositionDesigner(QDialog):
    def __init__(self, free, vertical, rotated, parent=None):
        super().__init__(parent)
        self.setWindowTitle('标签文字位置设计器')
        self.setMinimumWidth(760)
        self.free = _mirror(free)
        self.vertical = _mirror(vertical)
        self.rotated = _mirror(rotated)
        note = QLabel(
            '分别设置三种生产方向。刀码模式只在膜标签卡片外的透明安全区内采用所选对齐；'
            '某张图的位置不安全时，会在同一安全区内寻找可用位置。')
        note.setWordWrap(True)
        form = QFormLayout()
        form.addRow('无刀码标签位置', self.free)
        form.addRow('刀码未旋转 · 上下对齐', self.vertical)
        form.addRow('刀码旋转90° · 左右对齐', self.rotated)
        preview = LabelPositionDiagram(lambda: {
            'free': self.free.currentData(),
            'vertical': self.vertical.currentData(),
            'rotated': self.rotated.currentData(),
        }, self)
        for control in (self.free, self.vertical, self.rotated):
            control.currentIndexChanged.connect(preview.update)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText('关闭')
        buttons.rejected.connect(self.close)
        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addLayout(form)
        layout.addWidget(preview)
        layout.addWidget(buttons)
