"""GUI-thread presentation: batch → kind → size/order → piece → source image."""
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication, QGroupBox, QHeaderView, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from ..layout_engine.source_metadata import size_key


class AnalysisTree(QTreeWidget):
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            QApplication.clipboard().setText('\n'.join(
                '\t'.join(item.text(col) for col in range(self.columnCount()))
                for item in self.selectedItems()))
            return
        super().keyPressEvent(event)


class BatchAnalysisPanel(QGroupBox):
    source_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__('批次分析与分区结果', parent)
        self.report = None
        self.summary = QLabel('选择文件夹后，先分析订单、单双面和尺码，再比较分区。')
        self.sizes = QLabel('')
        for label in (self.summary, self.sizes):
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.tree = AnalysisTree()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(['分类 / 订单 / 图片', '数量 / 尺码', '分区判断', '依据 / 实测尺寸'])
        self.tree.setMinimumHeight(220)
        self.tree.setMaximumHeight(340)
        self.tree.setColumnWidth(0, 235)
        self.tree.setColumnWidth(1, 135)
        self.tree.setColumnWidth(2, 190)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tree.setToolTip('按分类逐层展开。选中内容后可复制；双击图片查看实际预览。')
        self.tree.itemActivated.connect(self._selected)
        layout = QVBoxLayout(self)
        for widget in (self.summary, self.sizes, self.tree):
            layout.addWidget(widget)

    @Slot()
    def clear(self):
        self.report = None
        self.tree.clear()
        self.summary.setText('正在分析新批次的文件名、订单和尺码…')
        self.sizes.clear()

    @Slot(str)
    def failed(self, message):
        self.summary.setText('本次分析 / 排版未完成：'+message)
        self.report = None
        self.tree.clear()
        self.sizes.clear()

    @Slot(object)
    def show_report(self, report):
        self.report = report
        self.tree.clear()
        summary = (f"{report['stage']} · {report['batch_type']} · {report['order_count']} 个订单组"
                   f" · 已识别 {report['piece_count']} 件 / {report['image_count']} 张图"
                   f" · {report['double_pairs']} 组双面")
        if 'height_m' in report:
            summary += f" · 长度 {report['height_m']:.3f} 米 · 节省 {report['saved_m']:.3f} 米"
        self.summary.setText(summary)
        sizes = report['single_sizes']
        total_sizes = report['sizes']
        size_summary = '商品尺码：'+'、'.join(f'{s} {total_sizes[s]} 件' for s in sorted(total_sizes, key=size_key))
        self.sizes.setText(size_summary+'。\n单件单面尺码：'+('、'.join(
            f'{s} {sizes[s]} 件' for s in sorted(sizes, key=size_key)) if sizes else '无')+
            '。大尺码按实测宽度判断；细长图比较旋转，小幅图尝试搭配。')
        categories, size_nodes = {}, {}
        for order in report['orders']:
            kind = order['kind']
            if kind not in categories:
                categories[kind] = QTreeWidgetItem(self.tree, [kind, f"{report['kinds'][kind]} 个订单组"])
            parent = categories[kind]
            if kind == '单件单面':
                size = next(iter(order['sizes']))
                key = kind, size
                if key not in size_nodes:
                    size_nodes[key] = QTreeWidgetItem(parent, [size, f'{sizes[size]} 件'])
                parent = size_nodes[key]
            node = QTreeWidgetItem(parent, [order['order'],
                f"{order['pieces'] if order['pieces'] is not None else '待核对'} 件 / {order['image_count']} 图",
                order['decision'], order['reason']])
            node.setToolTip(3, order['reason'])
            for index, item in enumerate(order['items'], 1):
                piece = QTreeWidgetItem(node, [f"商品 {index} · {'双面' if item['sides']==2 else '单图'}", item['size']])
                for image in item['images']:
                    dimensions = (f"{image['width_mm']:.1f} × {image['height_mm']:.1f} 毫米"
                                  if 'width_mm' in image else '待测量')
                    if image.get('reliable_dpi') is False:
                        dimensions += '（估算，禁止用于切膜）'
                    leaf = QTreeWidgetItem(piece, [image['name'], item['size'],
                                                  '、'.join(image.get('hints', [])), dimensions])
                    leaf.setToolTip(0, image['name'])
                    leaf.setData(0, Qt.UserRole, image['path'])
        self.tree.expandToDepth(0)

    def _selected(self, item, _column):
        path = item.data(0, Qt.UserRole)
        if path:
            self.source_selected.emit(path)
