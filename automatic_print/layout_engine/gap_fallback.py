"""Retry only width failures by undoing program-inserted transparent rows."""
from dataclasses import replace
from pathlib import Path
from .planner import plan_layout


def width_failure(error):
    return any(message in str(error) for message in (
        '整批图片不存在安全的统一双列刀位', '旋转与不旋转均超出单排可打印膜宽',
        '图片无法安全放入固定分区；单排必须靠左', '超过了材料可打印宽度',
        '剩余图片旋转后仍超宽'))


def recover_width(paths,settings,error,progress,analysis_ready):
    if settings.cutter_mode not in {'single', 'dual'} or not settings.auto_fit_width or not width_failure(error):
        raise error
    from .width_fit import fit_oversized
    fitted,adjusted=fit_oversized(paths,settings,progress)
    if adjusted.width_adjustments==settings.width_adjustments:
        raise error
    def analyzed(data):
        data['width_adjustments']=adjusted.width_adjustments
        rows=data.setdefault('image_anomalies',[])
        rows.extend({'source':name,'path':path,'kind':text,'action':'已自动继续；请核对实际打印尺寸'}
                    for name,text,path in adjusted.width_adjustments)
        if analysis_ready:
            analysis_ready(data)
    result=plan_layout(fitted,adjusted,progress,analyzed)
    return fitted,adjusted,result


def plan_with_gap_fallback(paths, settings, records, progress=None, analysis_ready=None):
    try:
        return paths, settings, plan_layout(paths, settings, progress, analysis_ready)
    except ValueError as error:
        if not width_failure(error) or not any(r.get('added_px') for r in records):
            return recover_width(paths,settings,error,progress,analysis_ready)
        reason = str(error)
    mapping = {str(Path(r.get('prepared',r['source'])).resolve()): str(Path(r['source']).resolve())
               for r in records}
    paths = [Path(mapping.get(str(p.resolve()),str(p))) for p in paths]
    remap = lambda values: tuple((mapping.get(str(Path(p).resolve()),p),v) for p,v in values)
    settings = replace(settings, membrane_gap_mm=0,
        manual_rotations=remap(settings.manual_rotations), sequence_numbers=remap(settings.sequence_numbers))
    for r in records:
        if r.get('added_px'):
            r['rollback_added_mm'] = r.get('added_mm',0)
            r['rollback_reason'] = reason
            r['warning'] = (f"新增间距导致膜宽无安全方案，已回退新增 {r['rollback_added_mm']:.2f} 毫米，"
                            '保留原图已有间距并重算整批刀位；用户设置未修改')
            r['added_px'] = 0
            r['added_mm'] = 0
            r.pop('prepared',None)
    if progress:
        progress('回退新增膜标签间距',0,1,'仅撤销程序新增空白，保留原图与用户设置，重新检查整批刀位')
    try:
        result = plan_layout(paths,settings,progress,analysis_ready)
    except ValueError as error:
        count = sum(bool(r.get('rollback_added_mm')) for r in records)
        if settings.cutter_mode in {'single', 'dual'} and settings.auto_fit_width and width_failure(error):
            return recover_width(paths,settings,error,progress,analysis_ready)
        raise ValueError(f'{error}\n已尝试自动恢复：回退{count}张的程序新增膜标签间距，原间距仍无安全方案；用户参数未修改。') from error
    if progress:
        progress('回退新增膜标签间距',1,1,'原间距重新排版完成，后续继续订单和实际像素安全检查')
    return paths,settings,result
