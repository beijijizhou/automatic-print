"""Render, encode, and validate one already verified production plan."""
from contextlib import nullcontext
from time import perf_counter


def render_output(planned, labels, width, height, settings, progress,
                  cut_check, prepared_plan, output_path, phase):
    from automatic_print.layout_engine.rendering.engines.output_encoder import encoder_plan, save_output
    from automatic_print.layout_engine.rendering.engines.pillow_renderer import build_pillow_canvas
    from automatic_print.layout_engine.rendering.engines.vips_renderer import available, build_vips_canvas, build_vips_rows, demand_lock
    from automatic_print.layout_engine.cutting.geometry.printed_guides import collect_guides, dot_boxes, paint_guides, validate_vips_canvas
    from automatic_print.layout_engine.cutting.geometry.transition_marks import transition_rects, paint_transition_lines
    from automatic_print.layout_engine.cutting.validation.cut_validation import validate_canvas_pixels, validate_vips_output
    from automatic_print.layout_engine.cutting.validation.marked_pixel_validation import validate_marked_pillow

    started = perf_counter()
    phase('图片准备与合成')
    output_format, streaming, use_vips = encoder_plan(settings, width, height)
    native_validation = use_vips or (settings.png_fast_encoding and available())
    with demand_lock if native_validation else nullcontext():
        row_streaming = streaming and use_vips
        if row_streaming:
            rows = build_vips_rows(planned, labels, width, settings, progress)
            canvas = None
        else:
            builder = build_vips_canvas if use_vips else build_pillow_canvas
            canvas = builder(planned, labels, (width, height), settings, progress)
        combining_seconds = perf_counter() - started
        phase('合成像素安全检查')
        if not use_vips:
            validate_canvas_pixels(canvas, cut_check, progress)
        elif not streaming and output_format != 'tiff':
            validate_vips_canvas(canvas, cut_check)
        phase('膜标签与辅助线处理')
        guide_spans, missing_guides = collect_guides(planned, settings, progress)
        guide_boxes = list(dot_boxes(guide_spans, settings.dpi))
        transitions = transition_rects(
            planned, settings, width,
            (prepared_plan or {}).get('end_notice', '批次结束'),
        )
        validation_seconds = 0.0
        if not row_streaming:
            canvas = paint_guides(canvas, guide_boxes, use_vips)
            canvas = paint_transition_lines(canvas, transitions, use_vips)
            if not use_vips:
                validate_marked_pillow(canvas, cut_check, guide_boxes, transitions, progress)
        saving_started = perf_counter()
        phase('保存输出图片')
        if row_streaming:
            from automatic_print.layout_engine.rendering.png.row_stream import save as save_rows
            save_details = save_rows(rows, output_path, width, height, settings,
                                     guide_boxes, transitions, progress, cut_check)
        else:
            save_details = save_output(canvas, output_path, settings, use_vips, progress,
                                       cut_check, guide_boxes, transitions)
        saving_seconds = perf_counter() - saving_started
        if streaming:
            from automatic_print.layout_engine.rendering.png.streaming import validate_saved_output
            validation_seconds = validate_saved_output(
                output_path, width, height, cut_check, guide_boxes,
                transitions, progress, phase, save_details,
            )
        elif native_validation and output_format != 'tiff':
            phase('输出文件安全复核')
            validate_vips_output(output_path, cut_check, progress, guide_boxes, transitions)
        elif settings.png_fast_encoding and cut_check:
            from PIL import Image
            phase('输出文件安全复核')
            try:
                with Image.open(output_path) as saved:
                    validate_marked_pillow(saved, cut_check, guide_boxes, transitions, progress)
            except ValueError:
                output_path.rename(output_path.with_suffix('.生成未完成'))
                raise
        if native_validation:
            import pyvips
            pyvips.cache_set_max(0)
    return (output_format, use_vips, save_details, combining_seconds,
            saving_seconds, validation_seconds, guide_spans, guide_boxes,
            missing_guides, transitions)
