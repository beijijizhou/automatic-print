"""Build the canonical output format and encoder controls."""
from PySide6.QtWidgets import QComboBox

from ....layout import png_engine_name


def build_output_settings(window):
    compression = QComboBox()
    compression.addItem("等级 1 — 轻度压缩（推荐）", 1)
    compression.addItem("等级 0 — 不压缩（文件最大）", 0)
    compression.addItem("等级 3 — 中度压缩（文件更小）", 3)
    output_format = QComboBox()
    output_format.addItem("PNG（生产默认）", "png")
    output_format.addItem("并行分块 TIFF（实验）", "tiff")
    engine = QComboBox()
    engine.addItem("标准快速模式（推荐）", "pillow")
    if png_engine_name() == "大图节省内存模式":
        engine.addItem("大图节省内存模式", "libvips")
    window.png_compression = compression
    window.output_format = output_format
    window.png_engine = engine
