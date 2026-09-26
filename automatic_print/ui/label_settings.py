from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from .setting_preview import SettingPreview
from .spinbox_style import double_spinbox
from ..layout_engine.labeling.base.labels import compact_label_text
class LabelSettingsDialog(QDialog):
    settings_changed = Signal()
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("标签与文字设置")
        self.setMinimumWidth(520)
        self.enabled = QCheckBox("为每张图片添加编号或文字标签")
        self.enabled.setChecked(True)
        self.sequence = QCheckBox('自动添加序号（每批从 1 到最后一张，不重复添加）')
        self.sequence.setChecked(True)
        self.source_order = QCheckBox('标注批次文件夹名、正序和倒序（测试中）')
        self.source_order.setChecked(True)
        self.platform = QComboBox()
        self.platform.setEditable(True)
        self.platform.addItem('隆丰')
        self.platform.addItem('S2B')
        self.platform.addItem('Haloo')
        self.platform_enabled = QCheckBox('显示平台＋尺码标签（关闭后仍保留切膜刀码）')
        self.platform_enabled.setChecked(True)
        self.platform_enabled.setToolTip(
            '只控制程序新增的平台和尺码文字；不会关闭左侧识别刀码、纵向刀位或原图二维码。'
        )
        self.platform_font_height = double_spinbox(6, 0, 50)
        self.platform_font_height.setSuffix(' 毫米')
        self.platform_font_height.setSpecialValueText('自动：膜标签等高')
        self.platform_font_height.setToolTip('平台字独立大小，默认高度 6 毫米；0 为自动等高。不会改变标签或序号字号。')
        self.follow_qr = QCheckBox(
            "识别膜标签与真实二维码，优先把文字放到二维码同行空白"
        )
        self.follow_qr.setChecked(True)
        self.machine = QComboBox()
        for index in range(1, 12):
            self.machine.addItem(f"M{index}", f"M{index}")
        self.text_template = QLineEdit()
        self.text_template.setPlaceholderText(
            "手动输入标签文字；机器号和序号自动显示"
        )
        self.text_template.editingFinished.connect(
            lambda: self.text_template.setText(compact_label_text(self.text_template.text()))
        )
        help_label = QLabel(
            "平台名、当前机器号和序号自动显示；开启批次顺序标注时，原图尺码也写入同一生产标签。"
            "可选变量：{日期}、{批次}、{尺码}、{完整文件名}、{文件名}。"
        )
        help_label.setWordWrap(True)
        help_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        qr_help = QLabel(
            "平台、尺码、机器号和批次信息写在同一张生产标签中；程序先识别真实二维码，"
            "使用二维码同一行内经像素确认的空白卡面。图片旋转时文字位置和方向一起旋转；"
            "同行空白不足时，才按位置设计器设置搜索卡片外安全区。"
        )
        qr_help.setWordWrap(True)
        qr_help.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.position = QComboBox()
        for text, value in (
            ("色块下方（固定标记组）", "block_below"),
            ("图片下方", "bottom"),
            ("图片上方", "top"),
            ("图片左侧", "left"),
            ("图片右侧", "right"),
            ("左上角（图片外）", "top_left"),
            ("右上角（图片外）", "top_right"),
            ("左下角（图片外）", "bottom_left"),
            ("右下角（图片外）", "bottom_right"),
        ):
            self.position.addItem(text, value)
        self.cutter_vertical = QComboBox()
        for text, value in (("靠上", "top"), ("居中", "center"), ("靠下", "bottom")):
            self.cutter_vertical.addItem(text, value)
        self.cutter_rotated = QComboBox()
        for text, value in (("靠左", "left"), ("居中", "center"), ("靠右", "right")):
            self.cutter_rotated.addItem(text, value)
        self.position_designer_button = QPushButton("打开标签文字位置设计器…")
        self.position_designer_button.clicked.connect(self._open_position_designer)
        self.font_size = double_spinbox(7.5 * 25.4 / 72, 0.5, 50)
        self.detect_region = QCheckBox("识别原图膜标签，文字区域与其等高并限制宽度")
        self.detect_region.setChecked(True)
        self.fit_height = QCheckBox("限制整段文字高度（字号不超过手动设置）")
        self.fit_height.setChecked(True)
        self.reference_height = double_spinbox(10, 2, 100)
        self.reference_height.setToolTip("填写原图膜标签的实际高度；程序会同时核验标签卡片和真实二维码。")
        self.gap = double_spinbox(5, 0, 100)
        self.offset_x = double_spinbox(0, -100, 100)
        self.offset_y = double_spinbox(0, -100, 100)
        self.date_format = QLineEdit("%Y-%m-%d")
        self.preview = SettingPreview("label", self._preview_values, self)
        self._connect_preview()
        form = QFormLayout()
        for label, widget in (
            ("启用标签", self.enabled),
            ('图片序号', self.sequence),
            ('批次顺序标注', self.source_order),
            ('生产平台', self.platform),
            ('平台尺码标签', self.platform_enabled),
            ('平台文字高度', self.platform_font_height),
            ("机器号", self.machine),
            ("膜标签区域定位", self.follow_qr),
            ("", qr_help),
            ("标签文字", self.text_template),
            ("", help_label),
            ("标签位置", self.position),
            ("位置设计", self.position_designer_button),
            ("文字大小（毫米）", self.font_size),
            ("高度适配", self.fit_height),
            ("动态识别", self.detect_region),
            ("膜标签实际高度（毫米）", self.reference_height),
            ("与图片距离（毫米）", self.gap),
            ("水平微调（毫米）", self.offset_x),
            ("垂直微调（毫米）", self.offset_y),
            ("日期格式", self.date_format),
        ):
            form.addRow(label, widget)
        self.form = form; form.setRowVisible(self.source_order, False)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview)
        layout.addWidget(buttons)
    def _preview_values(self) -> dict:
        return {
            "enabled": self.enabled.isChecked(),
            "follow_qr": self.follow_qr.isChecked(),
            "text": self.text_template.text(),
            "position": self.position.currentData(),
            "font_size": self.font_size.value(),
            "gap": self.gap.value(),
            "offset_x": self.offset_x.value(),
            "offset_y": self.offset_y.value(),
            "date_format": self.date_format.text(),
            "machine_number": self.machine.currentData(),
            'sequence_enabled': self.sequence.isChecked(),
            'source_order_enabled': self.source_order.isChecked(),
            'machine_enabled': True,
            'platform_name': self.platform.currentText() if self.platform_enabled.isChecked() else '',
            'platform_font_height_mm': self.platform_font_height.value(),
            'cutter_vertical_align': self.cutter_vertical.currentData(),
            'cutter_rotated_align': self.cutter_rotated.currentData(),
        }
    def _connect_preview(self) -> None:
        self.enabled.toggled.connect(self.preview.update)
        self.follow_qr.toggled.connect(self.preview.update)
        self.text_template.textChanged.connect(self.preview.update)
        self.position.currentIndexChanged.connect(self.preview.update)
        self.cutter_vertical.currentIndexChanged.connect(self.preview.update)
        self.cutter_rotated.currentIndexChanged.connect(self.preview.update)
        self.machine.currentIndexChanged.connect(self.preview.update)
        self.sequence.toggled.connect(self.preview.update)
        self.source_order.toggled.connect(self.preview.update)
        self.platform.currentTextChanged.connect(self.preview.update)
        self.platform_enabled.toggled.connect(self.preview.update)
        self.platform_font_height.valueChanged.connect(self.preview.update)
        self.position.currentIndexChanged.connect(self._sync_position)
        self.date_format.textChanged.connect(self.preview.update)
        for box in (self.font_size, self.gap, self.offset_x, self.offset_y):
            box.valueChanged.connect(self.preview.update)
        signals = [
            self.sequence.toggled, self.source_order.toggled, self.platform.currentTextChanged, self.platform_enabled.toggled,
            self.platform_font_height.valueChanged,
            self.detect_region.toggled,
            self.fit_height.toggled, self.reference_height.valueChanged,
            self.enabled.toggled, self.follow_qr.toggled,
            self.text_template.textChanged, self.position.currentIndexChanged,
            self.cutter_vertical.currentIndexChanged,
            self.cutter_rotated.currentIndexChanged,
            self.date_format.textChanged,
            self.machine.currentIndexChanged,
        ] + [box.valueChanged for box in (
            self.font_size, self.gap, self.offset_x, self.offset_y
        )]
        for signal in signals:
            signal.connect(lambda *_args: self.settings_changed.emit())
        self._sync_position()
        self.fit_height.toggled.connect(self._sync_fit)
        self.detect_region.toggled.connect(self._sync_fit)
        self._sync_fit()
    def _sync_fit(self, *_args):
        dynamic = self.detect_region.isChecked()
        self.font_size.setEnabled(not dynamic)
        self.fit_height.setEnabled(not dynamic)
        self.reference_height.setEnabled(not dynamic and self.fit_height.isChecked())
    def _sync_position(self, *_args):
        below = self.position.currentData() == "block_below"
        self.follow_qr.setEnabled(not below)
        if below:
            self.follow_qr.setChecked(False)

    def _open_position_designer(self):
        from .label_position_designer import LabelPositionDesigner
        if not hasattr(self, 'position_designer'):
            self.position_designer = LabelPositionDesigner(
                self.position, self.cutter_vertical, self.cutter_rotated, self)
        self.position_designer.show()
        self.position_designer.raise_()
        self.position_designer.activateWindow()
