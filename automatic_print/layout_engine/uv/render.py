"""Memory-bounded rendering and verification for UV fixed sheets."""

from dataclasses import dataclass
from pathlib import Path

from ..output.output_name import label_output_name, unused_output_path
from .sheet import CANVAS_HEIGHT_MM, CANVAS_WIDTH_MM, plan_uv_sheet


@dataclass(frozen=True)
class _TiffSettings:
    dpi: float
    png_compression_level: int = 1
    save_memory_unlimited: bool = False
    save_memory_mb: int = 512
    worker_threads: int = 4


def generate_uv_sheet(folder, progress=None, output_root=None, spec="2030_iron"):
    plan = plan_uv_sheet(folder, spec=spec, progress=progress)
    from ..rendering.engines.vips_renderer import available, demand_lock
    if not available():
        raise RuntimeError("UV 固定大画布需要大图节省内存引擎，当前环境不可用。")
    import pyvips
    output_root = (
        plan.source_folder.parent / "UV合成文件"
        if output_root is None else output_root
    )
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    filename = label_output_name(
        f"{plan.source_folder.name}_UV_{plan.spec.label}_{len(plan.placements)}张",
        extension=".tif",
    )
    target = unused_output_path(output_root, filename)
    with demand_lock:
        canvas = _render(plan, pyvips, progress)
        from ..rendering.storage.atomic_tiff import save_tiff
        save_tiff(canvas, target, _TiffSettings(plan.dpi), progress)
        try:
            _validate_saved(target, plan, pyvips)
        except Exception:
            incomplete = target.with_suffix(".生成未完成.tif")
            target.replace(incomplete)
            raise
        finally:
            pyvips.cache_set_max(0)
    return {
        "output": str(target),
        "image_count": len(plan.placements),
        "dpi": plan.dpi,
        "canvas_px": (plan.canvas_width_px, plan.canvas_height_px),
        "canvas_mm": (CANVAS_WIDTH_MM, CANVAS_HEIGHT_MM),
        "item_mm": (plan.spec.item_width_mm, plan.spec.item_height_mm),
        "material": plan.spec.label,
        "columns": plan.columns,
        "rows": plan.rows,
        "start_corner": "右下",
        "fill_direction": "同行向左，满行后向上",
        "output_format": "BigTIFF",
    }


def _render(plan, pyvips, progress):
    base = pyvips.Image.black(
        plan.canvas_width_px, plan.canvas_height_px, bands=4
    ).copy(interpretation="srgb")
    layers, xs, ys = [], [], []
    for index, placement in enumerate(plan.placements, 1):
        image = _rgba(pyvips.Image.new_from_file(
            str(placement.source), access="random"
        ))
        if placement.rotation_degrees:
            image = image.rot("d90")
        if image.width != placement.width_px or image.height != placement.height_px:
            image = image.thumbnail_image(
                placement.width_px, height=placement.height_px,
                size="force", no_rotate=True,
            )
        layers.append(image)
        xs.append(placement.x_px)
        ys.append(placement.y_px)
        if progress:
            progress("合成UV图片", index, len(plan.placements), placement.source.name)
    ppm = plan.dpi / 25.4
    return base.composite(layers, ["over"] * len(layers), x=xs, y=ys).copy(
        xres=ppm, yres=ppm, interpretation="srgb"
    )


def _rgba(image):
    if image.format != "uchar":
        image = image.cast("uchar")
    if image.bands == 1:
        grey = image[0]
        image = grey.bandjoin([grey, grey, 255])
    elif image.bands == 2:
        grey = image[0]
        image = grey.bandjoin([grey, grey, image[1]])
    elif image.bands == 3:
        image = image.bandjoin(255)
    elif image.bands > 4:
        image = image.extract_band(0, n=4)
    return image.copy(interpretation="srgb")


def _validate_saved(path, plan, pyvips):
    import tifffile
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        if page.shape != (plan.canvas_height_px, plan.canvas_width_px, 4):
            raise ValueError("UV TIFF 的画布尺寸或 RGBA 通道与计划不一致，禁止采用。")
        if not tif.is_bigtiff or page.extrasamples[0].name != "UNASSALPHA":
            raise ValueError("UV 输出不是带透明通道的 BigTIFF，禁止采用。")
    saved = pyvips.Image.new_from_file(str(path), access="random")
    if (saved.width, saved.height, saved.bands) != (
        plan.canvas_width_px, plan.canvas_height_px, 4
    ):
        raise ValueError("UV TIFF 的画布尺寸或 RGBA 通道与计划不一致，禁止采用。")
    for placement in plan.placements:
        alpha = saved[3].crop(
            placement.x_px, placement.y_px,
            placement.width_px, placement.height_px,
        )
        if alpha.max() <= 0:
            raise ValueError(f"{placement.source.name} 的输出区域没有实际像素，禁止采用。")
