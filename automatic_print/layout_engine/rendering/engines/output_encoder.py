"""Select and invoke one output encoder without leaking format branches into service."""
from automatic_print.layout_engine.rendering.storage.atomic_png import save_png
from automatic_print.layout_engine.rendering.engines.vips_renderer import available


def encoder_plan(settings, width, height):
    output_format = settings.output_format.lower()
    streaming = (output_format == 'png' and settings.png_streaming
                 and not settings.png_fast_encoding)
    if output_format == 'tiff' and not available():
        raise RuntimeError('并行分块 TIFF 需要大图分块引擎，当前运行环境不可用。')
    use_vips = available() and (
        output_format == 'tiff' or settings.png_engine == 'libvips'
        or (streaming and width * height * 4 >= 64 * 1024 * 1024))
    return output_format, streaming, use_vips


def save_output(canvas, target, settings, use_vips, progress=None,
                cut_check=None, guide_boxes=(), rectangles=()):
    if settings.output_format.lower() == 'tiff':
        # TIFF is an optional developer output.  Its native codec must not be
        # loaded while ordinary PNG users are starting the application.
        from automatic_print.layout_engine.rendering.storage.atomic_tiff import save_tiff
        return save_tiff(
            canvas, target, settings, progress,
            cut_check, guide_boxes, rectangles,
        )
    return save_png(canvas, target, settings, use_vips, progress)
