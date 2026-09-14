"""Never expose an encoder's partially written file as a printable PNG."""
from .save_progress import monitor_save


def save_png(canvas, target, settings, use_vips, progress):
    pending = target.with_name(target.name+'.未完成')
    with monitor_save(pending, progress):
        if use_vips:
            canvas.pngsave(str(pending), compression=settings.png_compression_level, interlace=False)
        else:
            try:
                canvas.save(pending, format='PNG', dpi=(settings.dpi, settings.dpi),
                            compress_level=settings.png_compression_level)
            finally:
                canvas.close()
    # Validation follows publication of a fully encoded image; the enclosing
    # production batch remains explicitly marked unfinished until all checks pass.
    pending.rename(target)
