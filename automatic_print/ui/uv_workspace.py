"""UV department workspace for fixed-sheet production."""

from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..controllers.uv_generation import UvGenerationController
from ..layout_engine.uv import UV_MATERIALS, UV_MATERIAL_BY_KEY
from ..layout_engine.uv.sheet import CANVAS_WIDTH_MM, uv_sheet_capacity


class UvWorkspace(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.host_window = window
        self.activity_key = "uv-generation"
        self._activity_stage = ""
        self.controller = UvGenerationController(self)
        self.folder = QLineEdit(
            window.preferences.value("uv/input_folder", "", str)
        )
        browse = QPushButton("选择UV批次文件夹…")
        browse.clicked.connect(self.choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(browse)

        facts = QGroupBox("UV 材质与排版参数")
        form = QFormLayout(facts)
        self.material = QComboBox()
        for spec in UV_MATERIALS:
            self.material.addItem(spec.label, spec.key)
        saved_material = window.preferences.value(
            "uv/material", "2030_iron", str
        )
        selected = self.material.findData(saved_material)
        self.material.setCurrentIndex(selected if selected >= 0 else 1)
        self.finished_size = QLabel()
        self.placement_size = QLabel()
        self.capacity = QLabel()
        form.addRow("材质种类", self.material)
        form.addRow("固定画布", QLabel("250 × 130 cm（2500 × 1300 mm）"))
        form.addRow("成品宽 × 长", self.finished_size)
        form.addRow("排版占位尺寸", self.placement_size)
        form.addRow("排版起点", QLabel("右下角"))
        form.addRow("填充方向", QLabel("同行从右向左，满行后向上"))
        form.addRow("单行 / 单画布容量", self.capacity)
        form.addRow("输出规则", QLabel("整批合成一张透明 RGBA BigTIFF，DPI 跟随源图"))

        self.generate_button = QPushButton("生成一张UV合成TIFF")
        self.generate_button.setMinimumHeight(42)
        self.generate_button.clicked.connect(self.generate)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status = QLabel("请选择包含 20 × 30 cm 源图的 UV 批次文件夹。")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout = QVBoxLayout(self)
        title = QLabel("UV 部门自动化打印")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        layout.addLayout(folder_row)
        layout.addWidget(facts)
        layout.addWidget(self.generate_button)
        layout.addStretch()

        self.controller.progress.connect(self.show_progress)
        self.controller.finished.connect(self.completed)
        self.controller.failed.connect(self.failed)
        self.material.currentIndexChanged.connect(self.sync_material)
        self.sync_material()

    def sync_material(self):
        spec = UV_MATERIAL_BY_KEY[self.material.currentData()]
        columns = int(CANVAS_WIDTH_MM // spec.item_width_mm)
        self.finished_size.setText(
            f"{spec.width_mm / 10:g} × {spec.length_mm / 10:g} cm"
        )
        self.placement_size.setText(
            f"{spec.item_width_mm / 10:g} × {spec.item_height_mm / 10:g} cm"
            + ("（横版）" if spec.landscape else "")
        )
        self.capacity.setText(f"{columns} 张 / {uv_sheet_capacity(spec)} 张")
        self.host_window.preferences.setValue("uv/material", spec.key)
        if not self.controller.active:
            self.status.setText(
                f"当前材质：{spec.label}；请选择对应的 UV 批次文件夹。"
            )

    def choose_folder(self):
        initial = self.folder.text().strip() or QStandardPaths.writableLocation(
            QStandardPaths.DownloadLocation
        )
        folder = QFileDialog.getExistingDirectory(self, "选择UV批次文件夹", initial)
        if folder:
            self.folder.setText(folder)
            self.host_window.preferences.setValue("uv/input_folder", folder)

    def generate(self):
        folder = Path(self.folder.text().strip())
        if not folder.is_dir():
            self.status.setText("UV 批次文件夹不存在；请选择有效文件夹后重新生成。")
            self.host_window.activity_hub.finish(
                self.activity_key, self.status.text(), state="failed",
            )
            return
        if self.controller.start(folder, self.material.currentData()):
            self.generate_button.setEnabled(False)
            self.material.setEnabled(False)
            self.progress.setRange(0, 0)
            self.status.setText(f"正在检查 UV 批次：{folder}")
            self._activity_stage = ""
            self.host_window.activity_hub.begin(
                self.activity_key, "UV 合成", self.status.text(),
                current_object=folder.name,
            )

    def show_progress(self, stage, current, total, name):
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
            self.progress.setFormat(f"{stage} · {current}/{total}")
        else:
            self.progress.setRange(0, 0)
        self.status.setText(f"{stage}：{name}")
        self.host_window.activity_hub.update(
            self.activity_key, title="UV 合成", message=self.status.text(),
            current_object=name, current=current if total else None,
            total=total or None, progress_text=f"{stage} · {current}/{total}" if total else stage,
            new_step=stage != self._activity_stage,
        )
        self._activity_stage = stage

    def completed(self, result):
        self.generate_button.setEnabled(True)
        self.material.setEnabled(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.status.setText(
            f"UV BigTIFF 合成完成：{result['material']} · "
            f"{result['image_count']} 张 · "
            f"{result['columns']} 列 × {result['rows']} 行 · "
            f"{result['dpi']:g} DPI\n右下起排，同行向左，满行后向上\n"
            f"输出：{result['output']}"
        )
        self.host_window.activity_hub.finish(
            self.activity_key, self.status.text(),
            current_object=result["output"],
        )

    def failed(self, message):
        self.generate_button.setEnabled(True)
        self.material.setEnabled(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status.setText(f"UV 合成未生成可打印文件：\n{message}")
        self.host_window.activity_hub.finish(
            self.activity_key, self.status.text(), state="failed",
        )
