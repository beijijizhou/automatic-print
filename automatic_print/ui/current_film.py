"""Visible selection identity, independent of theoretical film comparisons."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class CurrentFilmLabel(QLabel):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.cutter = window.cutter_settings
        self.setWordWrap(True)
        self.setTextFormat(Qt.PlainText)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setMinimumWidth(220)
        for signal in (self.cutter.film.currentIndexChanged,
                       self.cutter.mode.currentIndexChanged,
                       self.cutter.width_control.valueChanged,
                       self.cutter.printable.left.valueChanged,
                       self.cutter.printable.right.valueChanged):
            signal.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args):
        film = self.cutter.width_control.value()
        usable = self.cutter.printable.usable_width()
        modes = {'single': '单列切膜', 'dual': '自动多列切膜', 'free': '正常排版（无刀码）'}
        mode = modes.get(self.cutter.mode.currentData(), '待选择排版模式')
        self.setText(f'当前选用膜：{film/10:g} 厘米\n'
                     f'可打印 {usable:g} 毫米 · {mode}')
        self.setToolTip(f'当前打印参数，不是自动选用面积最省方案。\n'
                        f'物理膜宽 {film:g} 毫米 − RIIN左预留 '
                        f'{self.cutter.printable.left.value():g} 毫米 − 右预留 '
                        f'{self.cutter.printable.right.value():g} 毫米。')
        invalid = usable <= 0
        self.setStyleSheet('QLabel { background: '+('#fee2e2' if invalid else '#fff7ed')+
            '; color: '+('#991b1b' if invalid else '#9a3412')+
            '; border: 2px solid '+('#ef4444' if invalid else '#fb923c')+
            '; border-radius: 7px; padding: 9px; font-size: 17px; font-weight: bold; }')
        if invalid:
            self.setText(self.text()+'\n预留超过膜宽，禁止生成')
