"""Restore only compatible whole-batch plans, then return through normal validation."""
from dataclasses import replace
from . import plan_cache
from .measurement_session import verify_sources
from .order_validation import validate_order_placements
from .cut_validation import validate_cut_corridor


def checked_plan(paths, settings, result, knife):
    validate_order_placements(paths, result[0])
    validate_cut_corridor(result[0], replace(settings, cutter_knife_mm=knife), result[2])


def plan_with_cache(make, paths, settings, progress, analysis_ready, session):
    def report(stage, current, total, detail):
        if progress:
            progress(stage, current, total, detail)
    key, cached = None, None
    report('读取排版缓存', 0, 0, '检查图片修改时间、大小、参数与算法版本，不读取整张图片')
    try:
        key = plan_cache.cache_key(paths, settings, session.created_at, report)
        report('读取排版缓存', 0, 0, '文件信息已检查，正在查询本机持久化缓存')
        cached = plan_cache.load(key)
        if cached:
            result, analysis, knife = cached
            checked_plan(paths, settings, result, knife)
    except (OSError, ValueError, TypeError, KeyError, plan_cache.sqlite3.Error) as error:
        cached = None
        report('排版缓存提示', 0, 0, f'缓存不可用，继续正常排版：{error}')
    if cached:
        report('读取排版缓存', len(paths), len(paths), '缓存命中：跳过尺寸、标签、刀位与膜规格重新计算')
        report('批次刀位已确定', round(knife*settings.dpi/25.4), settings.dpi, '复用整批排版缓存；生成安全检查仍执行')
        if analysis_ready:
            analysis_ready(plan_cache.cached_analysis(analysis))
        verify_sources()
        return result
    report('读取排版缓存', 0, 0, '未命中缓存，执行正常测量与排版')
    final_analysis, effective = [], [settings.cutter_knife_mm]

    def capture(stage, current, total, detail):
        if stage == '批次刀位已确定':
            effective[0] = current*25.4/total
        report(stage, current, total, detail)

    def analyzed(data):
        final_analysis[:] = [data]
        if analysis_ready:
            analysis_ready(data)

    result = make(paths, settings, capture, analyzed)
    verify_sources()
    try:
        checked_plan(paths, settings, result, effective[0])
        if key and final_analysis:
            report('保存排版缓存', 0, 0, '将本批尺寸、标签位置、刀位和膜规格结果保存在本机')
            plan_cache.save(key, result, final_analysis[-1], effective[0])
            report('保存排版缓存', 1, 1, '缓存已保存，下次相同图片与参数直接复用')
    except (OSError, ValueError, TypeError, plan_cache.sqlite3.Error) as error:
        report('排版缓存提示', 0, 0, f'未保存缓存，不影响本次正常处理：{error}')
    return result
