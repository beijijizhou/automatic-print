"""Select completed Haloo style groups for separate supplement batches."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QSpinBox, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .pages import table_widget
from ..task.reads import CompletedGenerateWorker, ReadWorker


class CompletedHalooPage(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.groups = ()
        self.boxes = []
        layout = QVBoxLayout(self)
        note = QLabel('已完成的单项单件按物流、底款、颜色、面别和尺码档分别分类。'
                      '多件订单只按物流、订单组成和面别分组，始终保持整单。'
                      '选中的每一组会单独生成一个补单批次。')
        note.setWordWrap(True)
        self.limit = QSpinBox()
        self.limit.setRange(1, 200)
        self.limit.setValue(30)
        self.limit.setSuffix(' 个生产项（最多200）')
        self.read_button = QPushButton('读取已生产底款分类')
        self.read_button.clicked.connect(self.load)
        self.rule = QComboBox()
        self.rule.setMinimumWidth(230)
        self.rule.setPlaceholderText('先读取批次规则')
        self.generate_button = QPushButton('按所选分组分别生成批次')
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self.generate)
        controls = QHBoxLayout()
        for widget in (self.limit, self.read_button, self.rule, self.generate_button):
            controls.addWidget(widget)
        self.summary = QLabel('尚未读取。先查看分类，再选择要单独生成的底款组。')
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.table = table_widget(['选择', '物流', '订单组成', '底款名称 / ID', '颜色', '面别', '尺码档',
                                   '生产项数', '来源批次', '生产项ID'], 9)
        self.selection_preview = QPlainTextEdit()
        self.selection_preview.setReadOnly(True)
        self.selection_preview.setFixedHeight(92)
        self.selection_preview.setPlaceholderText('勾选分组后，这里会显示生成前的真实底款和颜色。')
        preview_title = QLabel('待生成清单（提交前核对底款名称、ID、颜色和件数）')
        warning = QLabel('提交前会重新核验已完成状态、整单范围、底款、来源批次和数量；'
                         '已补单的组不可重复生成。接口提交后若结果不明确，请先到平台核对，不要重试。')
        warning.setWordWrap(True)
        layout.addWidget(note)
        layout.addLayout(controls)
        for widget in (self.summary, self.table, preview_title,
                       self.selection_preview, warning):
            layout.addWidget(widget)
        self.limit.valueChanged.connect(self.invalidate)

    def invalidate(self, *_):
        self.groups = ()
        self.boxes = []
        self.table.setRowCount(0)
        self.rule.clear()
        self.generate_button.setEnabled(False)
        self.summary.setText('读取范围已变化，请重新读取分类。')
        self.selection_preview.clear()

    def load(self):
        if self.owner.thread is not None:
            return
        self.invalidate()
        self.summary.setText('正在读取已生产项和实际生产图面别…')
        self.owner._start_worker(ReadWorker('Haloo', 'completed_haloo',
                                           self.limit.value(), self.limit.value()))

    def show_result(self, result):
        if result['scope'] != self.limit.value():
            return
        data = result['data']
        self.groups = tuple(data['groups'])
        blocked = set(data.get('supplemented') or ())
        self.table.setRowCount(len(self.groups))
        self.boxes = []
        for row, group in enumerate(self.groups):
            box = QCheckBox()
            if blocked.intersection(group.item_ids):
                box.setEnabled(False)
                box.setToolTip('该组含已有补单的生产项，不能重复生成。')
            box.toggled.connect(self.update_generate_enabled)
            self.table.setCellWidget(row, 0, box)
            self.boxes.append(box)
            values = (group.logistics_code, group.order_composition,
                      self._style_label(group),
                      group.color or '未记录', group.face, group.size_group or '未记录',
                      str(len(group.item_ids)), ', '.join(group.source_batch_codes) or '未记录',
                      ', '.join(group.item_ids))
            for column, value in enumerate(values, 1):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.rule.clear()
        for rule in data.get('rules') or ():
            self.rule.addItem(rule.name, rule.id)
            if rule.is_default:
                self.rule.setCurrentIndex(self.rule.count() - 1)
        included = sum(len(group.item_ids) for group in self.groups)
        self.summary.setText(f"已读 {data['count']} 项，分类 {len(self.groups)} 组 / {included} 项；"
                             f"未纳入 {data['count'] - included} 项，"
                             f"已有补单 {len(blocked)} 项。快照可能跨页不完整，提交前会复核。")
        self.update_generate_enabled()

    def selected_groups(self):
        return tuple(group for group, box in zip(self.groups, self.boxes) if box.isChecked())

    @staticmethod
    def _style_label(group):
        if group.order_composition != '单项单件':
            return '多件整单（不按底款拆分）'
        return f'{group.style_name or "名称未记录"}（ID: {group.style_id or "未记录"}）'

    def _selected_description(self, groups):
        return '\n'.join(
            f'{index}. {self._style_label(group)}｜颜色：'
            f'{group.color or "未记录" if group.order_composition == "单项单件" else "多件整单"}'
            f'｜物流：{group.logistics_code}｜面别：{group.face}'
            f'｜{len(group.item_ids)} 项 / {sum(qty for _, qty in group.item_quantities)} 件'
            for index, group in enumerate(groups, 1)
        )

    def update_generate_enabled(self, *_):
        groups = self.selected_groups()
        self.selection_preview.setPlainText(self._selected_description(groups))
        self.generate_button.setEnabled(
            self.owner.thread is None and bool(groups)
            and self.rule.currentData() is not None
        )

    def set_actions_enabled(self, enabled):
        self.read_button.setEnabled(enabled)
        self.limit.setEnabled(enabled)
        self.rule.setEnabled(enabled)
        for box in self.boxes:
            box.setEnabled(enabled and not bool(box.toolTip()))
        self.generate_button.setEnabled(enabled and bool(self.selected_groups())
                                        and self.rule.currentData() is not None)

    def generate(self):
        groups = self.selected_groups()
        if not groups or self.owner.thread is not None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('生成前核对底款与颜色')
        dialog.resize(740, 360)
        layout = QVBoxLayout(dialog)
        label = QLabel(f'将下列 {len(groups)} 个分组分别生成批次。请先核对真实底款和颜色：')
        layout.addWidget(label)
        details = QPlainTextEdit(self._selected_description(groups))
        details.setReadOnly(True)
        layout.addWidget(details)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('确认生成')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('返回修改')
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.owner._start_worker(CompletedGenerateWorker(groups, self.rule.currentData()))

    def show_generation_result(self, result):
        codes = result['codes']
        self.invalidate()
        self.summary.setText('已确认生成批次：' + ', '.join(codes) + '。请刷新生产批次列表下载。')
        self.owner.log.appendPlainText(self.summary.text())
