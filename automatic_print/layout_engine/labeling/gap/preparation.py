"""Measure and stream lossless transparent label-gap copies."""
import numpy as np
from PIL import Image


def _seam_tolerance(width):
    """Allow a short opaque label footer below the detected QR card."""
    return max(128, round(width * .12))


def gap_geometry(source, region, minimum_px):
    """Return the insertion row and required transparent rows."""
    bottom = min(source.height, max(0, round(region.bottom * source.height)))
    tolerance = _seam_tolerance(source.width)
    end = min(source.height, bottom + tolerance + minimum_px + 1)
    with source.crop((0, bottom, source.width, end)) as strip:
        with strip.getchannel('A') as alpha:
            occupied = np.asarray(alpha).max(axis=1) > 0
    empty = np.flatnonzero(~occupied[:tolerance + 1])
    if not len(empty):
        raise ValueError('膜标签下方没有可确认的透明分界，保留原图，请人工核对')
    split = bottom + int(empty[0])
    following = np.flatnonzero(occupied[int(empty[0]):])
    existing = int(following[0]) if len(following) else end - split
    return split, max(0, minimum_px - existing)


def gap_geometry_file(path, region, minimum_px):
    """Measure only the bounded seam strip; avoid decoding the complete PNG."""
    from automatic_print.layout_engine.measurement.measurement_session import (
        active_source,
        source_pixels,
    )
    if active_source(path) is not None:
        with source_pixels(path) as source:
            return gap_geometry(source, region, minimum_px)
    try:
        import pyvips
        from automatic_print.layout_engine.rendering.engines.vips_renderer import demand_lock
        with demand_lock:
            source = pyvips.Image.new_from_file(str(path), access='sequential')
            bottom = min(source.height, max(0, round(region.bottom * source.height)))
            tolerance = _seam_tolerance(source.width)
            end = min(source.height, bottom + tolerance + minimum_px + 1)
            strip = source.crop(0, bottom, source.width, end - bottom)
            if strip.bands >= 4:
                alpha = strip[3]
                occupied = np.frombuffer((alpha > 0).write_to_memory(), dtype=np.uint8)
                occupied = occupied.reshape(strip.height, strip.width).max(axis=1) > 0
            else:
                occupied = np.ones(strip.height, dtype=bool)
            empty = np.flatnonzero(~occupied[:tolerance + 1])
            if not len(empty):
                raise ValueError('膜标签下方没有可确认的透明分界，保留原图，请人工核对')
            split = bottom + int(empty[0])
            following = np.flatnonzero(occupied[int(empty[0]):])
            existing = int(following[0]) if len(following) else end - split
            return split, max(0, minimum_px - existing)
    except (ImportError, OSError):
        with Image.open(path) as opened, opened.convert('RGBA') as source:
            return gap_geometry(source, region, minimum_px)


def insert_gap(source, split, added):
    canvas = Image.new('RGBA', (source.width, source.height + added))
    with source.crop((0, 0, source.width, split)) as top:
        canvas.paste(top, (0, 0))
    with source.crop((0, split, source.width, source.height)) as body:
        canvas.paste(body, (0, split + added))
    return canvas


def save_gap_copy(path, target, split, added, dimensions):
    """Stream the expanded PNG with libvips, retaining Pillow as a fallback."""
    def save_with_pillow():
        with Image.open(path) as opened, opened.convert('RGBA') as source:
            with insert_gap(source, split, added) as canvas:
                canvas.save(target, format='PNG', dpi=(dimensions.x_dpi, dimensions.y_dpi),
                            icc_profile=opened.info.get('icc_profile'), compress_level=1)

    try:
        import pyvips
    except ImportError:
        save_with_pillow()
        return 'Pillow兼容补距'
    try:
        from automatic_print.layout_engine.rendering.engines.vips_renderer import demand_lock
        with demand_lock:
            # The joined top/blank/body graph can request source rows again while PNG is
            # encoded.  `sequential` rejects that demand pattern on Windows as
            # "out of order read"; random access keeps the streaming output valid.
            source = pyvips.Image.new_from_file(str(path), access='random')
            if source.format != 'uchar' or source.bands != 4:
                raise ValueError('需要兼容像素路径')
            top = source.crop(0, 0, source.width, split)
            body = source.crop(0, split, source.width, source.height - split)
            blank = pyvips.Image.black(source.width, added, bands=4).cast('uchar')
            expanded = top.join(blank, 'vertical').join(body, 'vertical').copy(
                interpretation='srgb',
                xres=dimensions.x_dpi / 25.4,
                yres=dimensions.y_dpi / 25.4,
            )
            expanded.pngsave(str(target), compression=1, strip=True)
        return 'libvips流式补距'
    except (OSError, ValueError, pyvips.Error):
        save_with_pillow()
        return 'Pillow兼容补距'
