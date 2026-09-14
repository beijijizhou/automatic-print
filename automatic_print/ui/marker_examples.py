"""Always-visible four-case cutter preview; all expensive work stays off the GUI."""
from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QGridLayout, QGroupBox, QLabel, QPushButton, QScrollArea, QVBoxLayout

from .marker_example_data import CASES, build_examples


class ExampleWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, paths, settings, parent):
        super().__init__(parent)
        self.paths, self.settings = paths, settings

    def run(self):
        try:
            self.ready.emit(build_examples(self.paths, self.settings))
        except (ValueError, OSError) as error:
            self.failed.emit(str(error))


class MarkerExamples(QGroupBox):
    def __init__(self, window, parent=None):
        super().__init__('刀码与标签 · 四种位置预览', parent)
        self.window, self.paths, self.worker, self.pending = window, [], None, False
        self.results, self.images, self.cards = [], [], []
        self.status = QLabel('正在准备示例，不读取上次批次。')
        self.status.setWordWrap(True)
        layout, grid = QVBoxLayout(self), QGridLayout()
        layout.addWidget(self.status)
        for index, (side, degrees) in enumerate(CASES):
            card = QGroupBox(('膜标签在左' if side == 'left' else '膜标签在右')+
                             (' · 向左旋转90°' if degrees else ' · 不旋转'))
            picture, caption = QLabel('准备中…'), QLabel()
            picture.setAlignment(Qt.AlignCenter)
            picture.setMinimumHeight(190)
            caption.setMinimumHeight(50)
            caption.setWordWrap(True)
            caption.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body = QVBoxLayout(card)
            body.addWidget(picture)
            body.addWidget(caption)
            from .action_icons import action_icon
            enlarge = QPushButton('放大检查')
            enlarge.setIcon(action_icon('expand'))
            enlarge.clicked.connect(lambda checked=False, i=index: self.enlarge(i))
            body.addWidget(enlarge)
            grid.addWidget(card, index//2, index%2)
            self.cards.append((picture, caption))
        layout.addLayout(grid)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.refresh)
        for signal in (window.label_settings.settings_changed,
                       window.color_block_settings.settings_changed, window.dpi.valueChanged,
                       window.follow_source_dpi.toggled,
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
        self.worker.failed.connect(lambda text: self.status.setText(f'示例读取失败：{text}'), Qt.QueuedConnection)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def receive(self, results):
        if self.pending:
            return  # Never install an obsolete batch or parameter result.
        self.results, self.images = results, []
        from .marker_example_annotations import annotated_example
        settings = self.window._layout_settings()
        for data, (picture, caption) in zip(results, self.cards):
            image = QImage(data['pixels'], *data['size'], QImage.Format_RGBA8888).copy()
            image = annotated_example(image, data, settings)
            self.images.append(image)
            kind = '当前批次生产图' if data['production'] else '示意图：当前抽样未找到该侧膜标签'
            caption.setText(kind+'\n'+data['detail'])
            picture.setToolTip(data['source'] or '示意样板；位置由生产排版模块计算，不生成打印文件。')
        count = sum(r['production'] for r in results)
        mode = {'free':'自由排版','single':'单列切膜','dual':'双列切膜'}.get(settings.cutter_mode,settings.cutter_mode)
        self.status.setText(f'四种情况已更新 · {mode} · {count}种使用当前批次生产图。使用当前模式标记位置；'
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
        caption.setWordWrap(True)
        caption.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.addWidget(caption)
        picture = QLabel()
        picture.setPixmap(QPixmap.fromImage(self.images[index]))
        scroll = QScrollArea()
        scroll.setWidget(picture)
        body.addWidget(scroll)
        self.detail_dialog.show()  # Reuse existing pixels; no reading or new planning.

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.draw_images()
