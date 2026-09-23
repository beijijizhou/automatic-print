"""Select completed ERP order groups for separate supplement batches."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QSpinBox, QTableWidgetItem, QVBoxLayout, QWidget,
)
from .view.pages import table_widget
from .view.completed_view import selected_description, style_label
from ..task.reads import CompletedGenerateWorker, ReadWorker

class CompletedErpPage(QWidget):
    def __init__(self, owner, platform_name):
        super().__init__(owner)
        self.owner = owner
        self.platform_name = platform_name
        self.groups = ()
        self.boxes = []
        self.auto_plan_pending = False
        layout = QVBoxLayout(self)
        note = QLabel(self._strategy_note())
        note.setWordWrap(True)
        self.source = QComboBox()
        self.source.addItem('生产中', 5)
        self.source.addItem('已完成', 9)
        self.limit = QSpinBox()
        self.limit.setRange(1, 200)
        self.limit.setValue(30)
        self.limit.setSuffix(' 个生产项（最多200）')
        self.read_button = QPushButton('读取订单分类')
        self.read_button.clicked.connect(self.load)
        self.plan_button = QPushButton('自动化生成计划')
        self.plan_button.setToolTip('按所选订单状态读取，并将完整、未补单的分组加入候选计划；不会提交批次。')
        self.plan_button.clicked.connect(self.load_plan)
        self.rule = QComboBox()
        self.rule.setMinimumWidth(230)
        self.rule.setPlaceholderText('先读取批次规则')
        self.generate_button = QPushButton('按所选分组分别生成批次')
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self.generate)
        controls = QHBoxLayout()
        for widget in (self.source, self.limit, self.read_button, self.plan_button,
                       self.rule, self.generate_button):
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
        preview_title = QLabel('待生成清单（提交前核对分组条件和件数）')
        warning = QLabel('提交前会重新核验订单状态、整单范围、分组字段、来源批次和数量；'
                         '已补单的组不可重复生成。接口提交后若结果不明确，请先到平台核对，不要重试。')
        warning.setWordWrap(True)
        layout.addWidget(note)
        layout.addLayout(controls)
        for widget in (self.summary, self.table, preview_title,
                       self.selection_preview, warning):
            layout.addWidget(widget)
        self.limit.valueChanged.connect(self.invalidate)
        self.source.currentIndexChanged.connect(self.invalidate)

    def invalidate(self, *_):
        self.auto_plan_pending = False
        self.groups = ()
        self.boxes = []
        self.table.setRowCount(0)
        self.rule.clear()
        self.generate_button.setEnabled(False)
        self.summary.setText('读取范围已变化，请重新读取分类。')
        self.selection_preview.clear()

    def load(self):
        self._load(auto_plan=False)

    def load_plan(self):
        self._load(auto_plan=True)

    def _load(self, *, auto_plan):
        if self.owner.thread is not None:
            return
        self.invalidate()
        self.auto_plan_pending = auto_plan
        self.summary.setText(
            f'正在读取{self.source.currentText()}生产项与实际生产图面别…')
        self.owner._start_worker(ReadWorker(self.platform_name, 'completed_erp',
                                           self.limit.value(), self.limit.value(),
                                           source_status=self.source.currentData()))

    def show_result(self, result):
        if (result['scope'] != self.limit.value()
                or result['platform'] != self.platform_name
                or result.get('source_status', 9) != self.source.currentData()):
            return
        data = result['data']
        self.groups = tuple(data['groups'])
        blocked = set(data.get('supplemented') or ())
        order_issues = data.get('order_issues') or {}
        self.table.setRowCount(len(self.groups))
        self.boxes = []
        for row, group in enumerate(self.groups):
            box = QCheckBox()
            issues = [order_issues[order_id] for order_id in getattr(group, 'order_ids', ())
                      if order_id in order_issues]
            if blocked.intersection(group.item_ids) or issues:
                box.setEnabled(False)
                box.setToolTip('；'.join(issues) if issues else
                               '该组含已有补单的生产项，不能重复生成。')
            box.toggled.connect(self.update_generate_enabled)
            self.table.setCellWidget(row, 0, box)
            self.boxes.append(box)
            values = (group.logistics_code or '不分物流', group.order_composition,
                      style_label(group),
                      group.color or ('不分颜色' if group.face == '双面' else '未记录'),
                      group.face, group.size_group or '不分尺码',
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
        planned = 0
        was_auto_plan = self.auto_plan_pending
        if was_auto_plan:
            for box in self.boxes:
                if not box.toolTip():
                    box.setChecked(True)
                    planned += 1
        self.auto_plan_pending = False
        prefix = f'自动候选计划 {planned} 组；' if was_auto_plan else ''
        rule_issue = data.get('rule_issue') or ''
        self.summary.setText(f"{prefix}{self.source.currentText()}已读 {data['count']} 项，"
                             f"分类 {len(self.groups)} 组 / {included} 项；"
                             f"未纳入 {data['count'] - included} 项，"
                             f"已有补单 {len(blocked)} 项，整单异常 {len(order_issues)} 单。"
                             f"异常组已禁用，提交前仍会复核整单。"
                             f"{' ' + rule_issue if rule_issue else ''}")
        self.update_generate_enabled()

    def selected_groups(self):
        return tuple(group for group, box in zip(self.groups, self.boxes) if box.isChecked())

    def update_generate_enabled(self, *_):
        groups = self.selected_groups()
        self.selection_preview.setPlainText(selected_description(groups))
        self.generate_button.setEnabled(
            self.owner.thread is None and bool(groups)
            and self.rule.currentData() is not None
        )

    def set_actions_enabled(self, enabled):
        self.read_button.setEnabled(enabled)
        self.plan_button.setEnabled(enabled)
        self.source.setEnabled(enabled)
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
        dialog.setWindowTitle('生成前核对分组条件')
        dialog.resize(740, 360)
        layout = QVBoxLayout(dialog)
        label = QLabel(f'{self.source.currentText()}来源的 {len(groups)} 个分组将分别生成补单批次。'
                       '请先核对分组条件和件数：')
        layout.addWidget(label)
        details = QPlainTextEdit(selected_description(groups))
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
        self.owner._start_worker(CompletedGenerateWorker(
            self.platform_name, groups, self.rule.currentData()))

    def show_generation_result(self, result):
        if result['platform'] != self.platform_name:
            return
        codes = result['codes']
        self.invalidate()
        self.summary.setText('已确认生成批次：' + ', '.join(codes) + '。请刷新生产批次列表下载。')
        self.owner.log.appendPlainText(self.summary.text())

    def _strategy_note(self):
        if self.platform_name == '隆丰':
            return ('隆丰只使用 A00 默认工艺，不按物流、底款或尺码拆分；多件按订单组成，'
                    '单项单件分单双面，单面再按颜色分组。始终保持整单。')
        if self.platform_name == 'Haloo':
            return ('Haloo 按物流和订单组成分组；单项单件分单双面，单面按黑色、白色、'
                    '混色分组，黑白再分 S–XL 与 2XL–5XL。始终保持整单。')
        return ('生产中与已完成共用补单分组策略：单项单件按物流、底款、颜色、面别和'
                '尺码档分类；多件按物流、订单组成和面别分组。始终保持整单。')
