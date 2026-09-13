"""Explicit cross-platform step controls, rather than tiny native QSS fallbacks."""
from ..resources import asset_path


def spinbox_style():
    plus = asset_path('spin-plus.svg').as_posix()
    minus = asset_path('spin-minus.svg').as_posix()
    return '''
QSpinBox, QDoubleSpinBox { padding-right: 34px; min-height: 28px; }
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border; subcontrol-position: top right;
    width: 28px; height: 18px; background: #f1f5f9;
    border-left: 1px solid #cbd5e1; border-bottom: 1px solid #cbd5e1;
    border-top-right-radius: 5px; }
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 28px; height: 18px; background: #f1f5f9;
    border-left: 1px solid #cbd5e1; border-bottom-right-radius: 5px; }
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background: #dbeafe; }
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed { background: #bfdbfe; }
QSpinBox::up-button:disabled, QDoubleSpinBox::up-button:disabled,
QSpinBox::down-button:disabled, QDoubleSpinBox::down-button:disabled { background: #e2e8f0; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url("PLUS"); width: 12px; height: 12px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url("MINUS"); width: 12px; height: 12px; }
'''.replace('PLUS', plus).replace('MINUS', minus)
