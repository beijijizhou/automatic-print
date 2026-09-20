"""Always-visible four-case cutter preview; all expensive work stays off the GUI."""
from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QGridLayout, QGroupBox, QLabel, QPushButton, QScrollArea, QVBoxLayout

from .data import CASES, build_examples


class ExampleWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, paths, settings, parent):
        super().__init__(parent)
        self.paths, self.settings = paths, settings

    def run(self):
        try:
            self.ready.emit(build_examples(self.paths, self.settings))
        except Exception as error:
            self.failed.emit(str(error))


class MarkerExamples(QGroupBox):
    def __init__(self, window, parent=None):
        super().__init__('刀码与标签 · 四种位置预览', parent)
        self.window, self.paths, self.worker, self.pending = window, [], None, False
        self.results, self.images, self.cards, self.label_readouts = [], [], [], []
        self.status = QLabel('正在准备示例，不读取上次批次。')
        self.status.setWordWrap(True)
        layout, grid = QVBoxLayout(self), QGridLayout()
        layout.addWidget(self.status)
        for index, (side, degrees) in enumerate(CASES):
            card = QGroupBox(('膜标签在左' if side == 'left' else '膜标签在右')+
                             (' · 向左旋转90°' if degrees else ' · 不旋转'))
            card.setMinimumHeight(760)
            picture, caption = QLabel('准备中…'), QLabel()
            label_readout = QLabel('标签内容放大阅读：准备中…')
            picture.setAlignment(Qt.AlignCenter)
            picture.setMinimumHeight(390)
            caption.setMinimumHeight(50)
            caption.setWordWrap(True)
            caption.setTextInteractionFlags(Qt.TextSelectableByMouse)
            caption.setStyleSheet('QLabel { font-size: 19px; }')
            label_readout.setWordWrap(True)
            label_readout.setTextFormat(Qt.PlainText)
            label_readout.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label_readout.setMinimumHeight(88)
            label_readout.setStyleSheet('QLabel { color: #581c87; background: #faf5ff; '
                                        'font-size: 26px; font-weight: 700; '
                                        'padding: 10px; border: 2px solid #a21caf; '
                                        'border-radius: 4px; }')
            body = QVBoxLayout(card)
            body.addWidget(picture)
            body.addWidget(label_readout)
            body.addWidget(caption)
            from ...action_icons import action_icon
            enlarge = QPushButton('放大检查')
            enlarge.setIcon(action_icon('expand'))
            enlarge.clicked.connect(lambda checked=False, i=index: self.enlarge(i))
            body.addWidget(enlarge)
            grid.addWidget(card, index//2, index%2)
            self.cards.append((picture, caption))
            self.label_readouts.append(label_readout)
        layout.addLayout(grid)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.refresh)
        for signal in (window.label_settings.settings_changed,
                       window.color_block_settings.settings_changed, window.dpi.valueChanged,
                       window.follow_source_dpi.toggled,
                       window.membrane_gap_enabled.toggled,
                       window.membrane_gap.valueChanged,
                       window.cutter_settings.mode.currentIndexChanged,
                       window.cutter_settings.left_marker_lift.valueChanged):
            signal.connect(self.schedule)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.results:
            self.schedule()

    def use_batch(self, payload):
        self.paths = list(dict.fromkeys(path for path, _ in payload['planned']))
        self.schedule()

    def clear_batch(self):
        self.paths = []
        self.schedule()

    def schedule(self, *_):
        self.pending = True
        self.timer.start()

    def refresh(self):
        if not self.window.isVisible():
            return  # Constructing a hidden window never starts image work.
        if self.worker is not None:
            return
        try:
            settings = self.window._layout_settings()
        except ValueError as error:
            self.status.setText(f'参数无效：{error}')
            return
        self.pending = False
        self.status.setText('正在后台更新四种刀码/标签位置…')
        self.worker = ExampleWorker(list(self.paths), settings, self)
        self.worker.ready.connect(self.receive, Qt.QueuedConnection)
        self.worker.failed.connect(self.failed, Qt.QueuedConnection)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def failed(self, text):
        self.status.setText(f'示例读取失败：{text}')
        if self.results:
            return  # Keep the last valid diagrams visible during a failed refresh.
        for (picture, caption), readout in zip(self.cards, self.label_readouts):
            picture.setText('示意图暂不可用')
            caption.setText(text)
            readout.setText('标签内容放大阅读：暂不可用')

    def receive(self, results):
        if self.pending:
            return  # Never install an obsolete batch or parameter result.
        self.results, self.images = results, []
        from .annotations import annotated_example
        settings = self.window._layout_settings()
        for data, (picture, caption), readout in zip(results, self.cards, self.label_readouts):
            image = QImage(data['pixels'], *data['size'], QImage.Format_RGBA8888).copy()
            image = annotated_example(image, data, settings)
            self.images.append(image)
            kind = {'production': '当前批次生产图',
                    'haloo': '内置 Haloo 示意样本（非当前生产图）',
                    'code': '代码绘制示意图（非当前生产图）',
                    'haloo-direction': '内置 Haloo 样本 · 仅方向示意（不可作为生产坐标）',
                    'code-direction': '代码绘制 · 仅方向示意（不可作为生产坐标）'}[data['sample_kind']]
            reason = data['fallback_reason']
            short_reason = reason.split('；', 1)[0][:70] if reason else ''
            caption.setText(kind + (f' · {short_reason}' if short_reason else '') + '\n' + data['detail'])
            label_text = data.get('label_text', '').strip()
            readout.setText('紫框标签文字放大（非打印比例）：\n' + label_text if label_text else
                            '仅方向示意：当前参数没有可安全定位的标签文字。')
            picture.setToolTip(data['source'] or reason or
                '示意图使用生产排版模块计算位置，不生成打印文件。')
        count = sum(r['production'] for r in results)
        mode = {'free':'自由排版','single':'单列切膜','dual':'自动多列切膜'}.get(settings.cutter_mode,settings.cutter_mode)
        self.status.setText(f'四种情况已更新 · {mode} · {count}种使用当前批次生产图，其余使用内置样本或代码示意。使用当前模式标记位置；'
                           '位置取自当前参数，不预设文字在刀码下方。抽样前24张，示例不替代整批刀位检查。')
        self.draw_images()

    def finished(self):
        self.worker.deleteLater()
        self.worker = None
        if self.pending:
            self.timer.start()

    def draw_images(self):
        for image, (picture, _) in zip(self.images, self.cards):
            picture.setPixmap(QPixmap.fromImage(image).scaled(max(100, picture.width()-8), max(100, picture.height()-8),
                              Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def enlarge(self, index):
        if index >= len(self.images):
            return
        previous = getattr(self, 'detail_dialog', None)
        if previous:
            previous.close()
        self.detail_dialog = QDialog(self)
        self.detail_dialog.setWindowTitle('刀码与标签 · 放大检查')
        self.detail_dialog.resize(960, 780)
        body = QVBoxLayout(self.detail_dialog)
        caption = QLabel(self.cards[index][1].text()+'\n'+self.results[index]['source'])
        caption.setStyleSheet('QLabel { font-size: 16px; }')
        caption.setWordWrap(True)
        caption.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.addWidget(caption)
        label_text = self.results[index].get('label_text', '').strip()
        if label_text:
            readout = QLabel('紫框标签文字放大（非打印比例）：\n' + label_text)
            readout.setTextFormat(Qt.PlainText)
            readout.setWordWrap(True)
            readout.setStyleSheet('QLabel { color: #581c87; font-size: 28px; font-weight: 700; }')
            readout.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body.addWidget(readout)
        picture = QLabel()
        picture.setPixmap(QPixmap.fromImage(self.images[index]))
        scroll = QScrollArea()
        scroll.setWidget(picture)
        body.addWidget(scroll)
        self.detail_dialog.show()  # Reuse existing pixels; no reading or new planning.

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.draw_images()
