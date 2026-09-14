"""Explicit custom film specification, using the existing millimetre width model."""
from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel,QDoubleSpinBox


class CustomFilmWidth(QWidget):
    def __init__(self,preferences,parent=None):
        super().__init__(parent)
        self.value=QDoubleSpinBox()
        self.value.setRange(5,500)
        self.value.setDecimals(2)
        self.value.setSingleStep(.5)
        self.value.setSuffix(' 厘米')
        self.value.setValue(preferences.value('cutter/custom_film_mm',600,float)/10)
        self.value.valueChanged.connect(lambda v:preferences.setValue('cutter/custom_film_mm',v*10))
        layout=QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(QLabel('自定义膜宽'))
        layout.addWidget(self.value)
        layout.addStretch()
        self.hide()

    def millimetres(self):
        return self.value.value()*10
