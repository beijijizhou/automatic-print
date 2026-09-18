"""Read-only Haloo completed-item grouping, with explicit sample limitations."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget, QTableWidgetItem
from .pages import table_widget
from ..task.reads import ReadWorker


class CompletedHalooPage(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        layout = QVBoxLayout(self)
        note = QLabel('只读已生产数据，不生成或修改批次。多件先按物流和订单组成分组；'
                      '单件选快照内最多的底款，再分物流、黑白、实际面别和尺码档。')
        note.setWordWrap(True)
        self.limit = QSpinBox()
        self.limit.setRange(1, 200)
        self.limit.setValue(30)
        self.limit.setSuffix(' 个生产项（最多200）')
        self.read_button = QPushButton('读取已生产分类预览')
        self.read_button.clicked.connect(self.load)
        self.summary = QLabel('尚未读取。这里只预览有限快照，不能保证跨页订单完整。')
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.table = table_widget(['物流', '订单组成', '底款', '颜色', '面别', '尺码档',
                                   '生产项数', '来源批次', '生产项ID'], 8)
        warning = QLabel('生成尚未开放：接口没有预演参数，未证实重新生成不会影响正常生产。'
                         '候选不等于可提交批次；缺失字段及跨页整单仍需核验。')
        warning.setWordWrap(True)
        for widget in (note, self.limit, self.read_button, self.summary, self.table, warning):
            layout.addWidget(widget)
        self.limit.valueChanged.connect(self.invalidate)

    def invalidate(self, *_):
        self.table.setRowCount(0)
        self.summary.setText('读取范围已变化，请重新读取分类预览。')

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
        groups = data['groups']
        self.table.setRowCount(len(groups))
        for row, group in enumerate(groups):
            values = (group.logistics_code or '物流缺失', group.order_composition,
                      group.style_name or group.style_id or '整单混合', group.color or '整单混合',
                      group.face, group.size_group or '整单混合', str(len(group.item_ids)),
                      ', '.join(group.source_batch_codes) or '未记录', ', '.join(group.item_ids))
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        included = sum(len(group.item_ids) for group in groups)
        self.summary.setText(f"已读 {data['count']} 项，候选 {len(groups)} 组 / {included} 项；"
                             f"未纳入 {data['count'] - included} 项（其他底款或颜色）。"
                             '这是快照预览，未生成批次，也未确认整单完整。')
