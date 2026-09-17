"""GUI-thread-only animation identifies the active layout entry point."""
from math import cos, sin, pi
from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QPixmap, QPainter, QIcon, QColor


class LayoutActivity(QObject):
    def __init__(self, single, multiple, parent):
        super().__init__(parent)
        self.buttons = {'single': single, 'multiple': multiple}
        self.original = {key: (b.text(), b.icon(), b.styleSheet(), b.toolTip())
                         for key,b in self.buttons.items()}
        self.active, self.frame = None, 0
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self.tick)

    def start(self, mode):
        if self.active is not None:
            self.stop()
        self.original = {key: (b.text(), b.icon(), b.styleSheet(), b.toolTip())
                         for key,b in self.buttons.items()}
        self.active = self.buttons[mode]
        self.active.setText(self.original[mode][0]+' · 进行中')
        self.active.setStyleSheet('QPushButton:disabled {background:#dbeafe; color:#1d4ed8;'
            'border:2px solid #3b82f6; border-radius:8px; font-weight:bold;}')
        self.tick()
        self.timer.start()

    def update_phase(self, phase, seconds, total_seconds, fraction):
        if self.active is None:
            return
        mode = next(key for key, button in self.buttons.items() if button is self.active)
        title = self.original[mode][0]
        self.active.setText(
            f'{title} · {phase} · 当前 {seconds:.2f}秒 · 总计 {total_seconds:.2f}秒 · {fraction:.1%}'
        )
        self.active.setToolTip(
            f'当前操作：{phase}\n本步骤耗时：{seconds:.2f}秒\n'
            f'本次总耗时：{total_seconds:.2f}秒\n占当前总耗时：{fraction:.1%}'
        )

    def tick(self):
        if self.active is None:
            return
        pixmap = QPixmap(48,48)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            for i in range(12):
                color = QColor('#2563eb')
                color.setAlpha(40+((i-self.frame)%12)*19)
                painter.setBrush(color)
                angle = i*pi/6
                painter.drawEllipse(int(21+16*cos(angle)),int(21+16*sin(angle)),6,6)
        finally:
            painter.end()
        pixmap.setDevicePixelRatio(2)
        icon = QIcon()
        for mode in (QIcon.Normal,QIcon.Disabled):
            icon.addPixmap(pixmap,mode)
        self.active.setIcon(icon)
        self.frame = (self.frame+1)%12

    def stop(self):
        self.timer.stop()
        for key,button in self.buttons.items():
            text,icon,style,tooltip = self.original[key]
            button.setText(text)
            button.setIcon(icon)
            button.setStyleSheet(style)
            button.setToolTip(tooltip)
        self.active = None
