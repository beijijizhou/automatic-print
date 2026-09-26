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
            card = QRectF(image.left()+8, image.top()+8, image.width()-16, 54)
            qr = QRectF(card.left()+6, card.top()+7, 40, 40)
            self._card(painter, card, qr)
            label.setWidth(min(label.width(), card.right()-qr.right()-14))
            label.moveLeft(qr.right()+7)
            label.moveTop(qr.center().y()-label.height()/2)
        else:
            card = QRectF(image.left()+10, image.top()+8, 48, image.height()-16)
            qr = QRectF(card.left()+6, card.bottom()-46, 36, 36)
            self._card(painter, card, qr)
            label.setSize(QRectF(0, 0, 25, min(72, qr.top()-card.top()-12)).size())
            label.moveLeft(card.center().x()-label.width()/2)
            label.moveBottom(qr.top()-6)
        painter.setPen(QPen(QColor('#7e22ce'), 2))
        painter.setBrush(QColor('#f3e8ff'))
        painter.drawRoundedRect(label, 4, 4)
        painter.setPen(QColor('#581c87'))
        painter.setFont(QFont('', 8))
        if case == 2:
            painter.save()
            painter.translate(label.center())
            painter.rotate(-90)
            painter.drawText(
                QRectF(-label.height()/2, -label.width()/2,
                       label.height(), label.width()),
                Qt.AlignmentFlag.AlignCenter, '标签文字',
            )
            painter.restore()
        else:
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, '标签文字')
        painter.setPen(QColor('#64748b'))
        painter.drawText(QRectF(panel.left()+8, panel.bottom()-42, panel.width()-16, 28),
                         Qt.AlignmentFlag.AlignCenter,
                         '逐图核验二维码与空白像素')

    @staticmethod
    def _card(painter, rect, qr):
        painter.setPen(QPen(QColor('#f97316'), 2))
        painter.setBrush(QColor('#ffedd5'))
        painter.drawRect(rect)
        painter.setPen(QPen(QColor('#111827'), 2))
        painter.setBrush(QColor('white'))
        painter.drawRect(qr)
        painter.setBrush(QColor('#111827'))
        size = qr.width()/5
        for column, row in ((0, 0), (3, 0), (0, 3), (2, 2), (4, 4)):
            painter.drawRect(QRectF(qr.left()+column*size, qr.top()+row*size,
                                    size, size))

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
            '刀码模式会先把文字放在二维码同行的已核验空白卡面，并随图片一起旋转。'
            '同行空间不足时，以下未旋转和旋转选项决定卡片外安全区的回退对齐。')
        note.setWordWrap(True)
        form = QFormLayout()
        form.addRow('无刀码标签位置', self.free)
        form.addRow('刀码未旋转 · 回退上下对齐', self.vertical)
        form.addRow('刀码旋转90° · 回退左右对齐', self.rotated)
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
