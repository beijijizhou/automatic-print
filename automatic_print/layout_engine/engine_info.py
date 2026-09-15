"""User-facing renderer capability names."""
from .vips_renderer import available


def png_engine_name():
    return "大图节省内存模式" if available() else "标准兼容模式"
