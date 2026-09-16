"""Compact label fields plus identities owned by the pinned parameter area."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel


def show_selected_source(panel, value, mode='single', window=None):
    """Input root is distinct from the currently rendered child batch."""
    path = Path(str(value).strip()) if str(value).strip() else None
    prefix = '已选择排版目录' if mode in {'layout', 'multiple'} else '已选择'
    panel.selected_source.setText(f'{prefix}：{path.name}  ·  {path}' if path else '尚未选择图片文件夹')
    panel.selected_source.setStyleSheet('QLabel { background: #dbeafe; color: #1e40af; '
        'border: 1px solid #60a5fa; border-radius: 5px; padding: 7px; font-weight: bold; }'
        if path else 'QLabel { color: #64748b; padding: 5px; }')
    if window is not None:
        window.preferences.setValue('layout/input_root', str(path) if path else '')
        window.preferences.setValue('layout/input_mode', mode)
        window.preferences.sync()


def quick_fields(panel, date_button, window):
    row = QHBoxLayout()
    controls = (("标签与文字", panel.text, 3), ("生产平台", panel.platform, 1),
                ("平台文字高度", panel.platform_font_height, 1), ("机器号", panel.machine, 0))
    for name, control, stretch in controls:
        row.addWidget(QLabel(name))
        row.addWidget(control, stretch)
        control.setMinimumWidth(60)
        control.setToolTip(name)
    panel.platform_font_height.setMaximumWidth(125)
    panel.machine.setMaximumWidth(75)
    panel.platform.setMaximumWidth(145)
    panel.text.setMinimumWidth(120)
    panel.sequence.setParent(panel)
    panel.sequence.hide()  # Canonical sequence option remains in label settings.
    date_button.setParent(panel)
    date_button.hide()  # Date insertion remains available in the full settings.
    panel.selected_source = QLabel()
    panel.selected_source.setWordWrap(True)
    panel.selected_source.setTextInteractionFlags(Qt.TextSelectableByMouse)
    def show_source(value):
        show_selected_source(panel, value, window=window)
    window.folder.textChanged.connect(show_source)
    show_selected_source(panel, window.preferences.value('layout/input_root', window.folder.text(), str),
                         window.preferences.value('layout/input_mode', 'single', str))
    from .current_film import CurrentFilmLabel
    panel.current_film = CurrentFilmLabel(window, panel)
    # The batch input panel places both identities above all everyday options.
    # Creating them here keeps the existing data bindings owned by this module.
    return row
