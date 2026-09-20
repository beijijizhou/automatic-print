"""Direct, grouped batch visibility without a modal window or dropdown."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem
from .action_icons import action_icon
from .progress_format import file_size_text


class BatchStatusBoard(QWidget):
    currentIndexChanged = Signal(int)
    userSelected = Signal(int)
    recordRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.index = -1
        self.items, self.groups, self.titles = {}, {}, {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        caption = QHBoxLayout()
        caption.addWidget(QLabel('批次状态 · 点击选择，双击查看记录'))
        caption.addStretch()
        self.open_record = QPushButton('查看所选批次记录')
        self.open_record.setEnabled(False)
        self.open_record.clicked.connect(self.request_record)
        caption.addWidget(self.open_record)
        outer.addLayout(caption)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        for name, icon, color in (('已完成', 'done', '#15803d'),
                                  ('进行中', 'refresh', '#2563eb'),
                                  ('未完成', 'waiting', '#b45309')):
            body = QVBoxLayout()
            heading = QHBoxLayout()
            mark = QLabel()
            mark.setPixmap(action_icon(icon, color).pixmap(20, 20))
            title = QLabel(name+'（0）')
            title.setStyleSheet(f'color: {color}; font-weight: bold;')
            heading.addWidget(mark)
            heading.addWidget(title)
            heading.addStretch()
            body.addLayout(heading)
            tree = QTreeWidget()
            tree.setHeaderLabels(['文件夹', '图片数', '尺码群 / 订单群'])
            tree.setRootIsDecorated(True)
            tree.setWordWrap(True)
            tree.setColumnWidth(0, 120)
            tree.setColumnWidth(1, 60)
            tree.itemSelectionChanged.connect(lambda t=tree: self.choose(t))
            tree.itemDoubleClicked.connect(lambda item, _column: self.request_record(item))
            body.addWidget(tree)
            row.addLayout(body, 1)
            self.groups[name], self.titles[name] = tree, title
        outer.addLayout(row)
        self.setMinimumHeight(205)
        self.setMaximumHeight(300)

    def reset(self, folders, root=None, information=None):
        self.blockSignals(True)
        for tree in self.groups.values():
            tree.blockSignals(True)
            tree.clear()
        self.items.clear()
        self.index = -1
        for index, folder in enumerate(folders):
            info = (information or {}).get(index, {})
            name = folder.relative_to(root).as_posix() if root else folder.name
            item = QTreeWidgetItem([name if name != '.' else folder.name,
                                   str(info['image_count']) if 'image_count' in info else '', ''])
            item.setData(0, Qt.UserRole, index)
            item.setIcon(0, action_icon('waiting', '#b45309'))
            source_tip = str(folder)+'\n'+'\n'.join(p.name for p in info.get('images', []))
            item.setData(0, Qt.UserRole+2, source_tip)
            item.setToolTip(0, source_tip+'\n状态：等待开始')
            sources=info.get('source_batches',())
            if sources:
                for source in sources:
                    path=source['folder']
                    if path == folder:
                        continue
                    relative=path.relative_to(root).as_posix() if root else path.name
                    child=QTreeWidgetItem([relative,str(source['image_count']),''])
                    child.setIcon(0,action_icon('folder','#64748b'))
                    child.setData(0,Qt.UserRole+1,str(path))
                    child_tip=str(path)+'\n'+'\n'.join(p.name for p in source.get('images',()))
                    child.setData(0,Qt.UserRole+2,child_tip)
                    child.setToolTip(0,child_tip+'\n状态：已加入合并批次')
                    item.addChild(child)
            self.groups['未完成'].addTopLevelItem(item)
            if sources:
                item.setExpanded(True)
            self.items[index] = item
        for tree in self.groups.values():
            tree.blockSignals(False)
        self.counts()
        self.blockSignals(False)
        if folders:
            self.setCurrentIndex(0)
        self.open_record.setEnabled(bool(folders))

    def counts(self):
        for name, tree in self.groups.items():
            self.titles[name].setText(f'{name}（{tree.topLevelItemCount()}）')

    def update_batch(self, index, stage, current=0, total=0, filename='', group=None):
        item = self.items[index]
        done = stage in ('批次生成完成', '批次预览完成')
        failed = '失败' in stage or '停止' in stage
        group = group or ('已完成' if done else '未完成' if failed else '进行中')
        source, target = item.treeWidget(), self.groups[group]
        for tree in self.groups.values():
            tree.blockSignals(True)
        if source is not target:
            source.takeTopLevelItem(source.indexOfTopLevelItem(item))
            target.addTopLevelItem(item)
        if item.childCount():
            item.setExpanded(True)
        count = f' · {current}/{total}' if total else (
            ' · 已写入 '+file_size_text(current) if stage == '保存图片' else '')
        item.setToolTip(0, item.data(0,Qt.UserRole+2)+'\n状态：'+stage+count+'\n'+filename)
        icon, color = ('done', '#15803d') if done else (
            ('warning', '#be123c') if failed else ('waiting', '#b45309') if group == '未完成'
            else ('refresh', '#2563eb'))
        item.setIcon(0, action_icon(icon, color))
        child_status='已随整批完成' if done else (
            '整批失败，未单独输出' if failed else f'随整批处理 · {stage}')
        if '测量标签与刀码' not in stage:
            for child_index in range(item.childCount()):
                child=item.child(child_index)
                child.setToolTip(0,child.data(0,Qt.UserRole+2)+'\n状态：'+child_status+count)
        item.setSelected(index == self.index)
        for tree in self.groups.values():
            tree.blockSignals(False)
        self.counts()

    def update_source(self,index,folder,stage,current,total,filename):
        item=self.items.get(index)
        if item is None:
            return
        for child_index in range(item.childCount()):
            child=item.child(child_index)
            if child.data(0,Qt.UserRole+1)==folder:
                done=current>=total
                text=f'{stage} · {current}/{total}'+(' · 已完成' if done else '')
                child.setToolTip(0,child.data(0,Qt.UserRole+2)+'\n状态：'+text+'\n'+filename)
                child.setIcon(0,action_icon('done' if done else 'refresh',
                                           '#15803d' if done else '#2563eb'))
                return

    def update_distribution(self, index, report):
        item = self.items.get(index)
        if item is None:
            return
        from ..layout_engine.orders.batch_analysis import compact_distribution_text, distribution_text
        item.setText(2, compact_distribution_text(report, limit=4))
        item.setToolTip(2, distribution_text(report))

    def currentIndex(self):
        return self.index

    def setCurrentIndex(self, index):
        if index not in self.items:
            return
        self.index = index
        for tree in self.groups.values():
            tree.blockSignals(True)
            tree.clearSelection()
        item = self.items[index]
        item.setSelected(True)
        item.treeWidget().scrollToItem(item)
        for tree in self.groups.values():
            tree.blockSignals(False)
        self.currentIndexChanged.emit(index)

    def choose(self, tree):
        selected = tree.selectedItems()
        if selected:
            item = selected[0]
            index = (item.parent() or item).data(0, Qt.UserRole)
            self.setCurrentIndex(index)
            self.userSelected.emit(index)

    def request_record(self, item=None):
        target = (item.parent() or item) if isinstance(item, QTreeWidgetItem) else self.items.get(self.index)
        if target is not None:
            self.recordRequested.emit(target.data(0, Qt.UserRole))
