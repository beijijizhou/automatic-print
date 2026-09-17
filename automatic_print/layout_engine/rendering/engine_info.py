"""User-facing renderer capability names."""
from automatic_print.layout_engine.rendering.engines.vips_renderer import available


def png_engine_name():
    return "大图节省内存模式" if available() else "标准兼容模式"
