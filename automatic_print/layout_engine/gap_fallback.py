"""Retry only width failures by undoing program-inserted transparent rows."""
from dataclasses import replace
from pathlib import Path
from .planner import plan_layout


def width_failure(error):
    return any(message in str(error) for message in (
        '整批图片不存在安全的统一双列刀位', '旋转与不旋转均超出单排可打印膜宽',
        '图片无法安全放入固定分区；单排必须靠左', '超过了材料可打印宽度',
        '剩余图片旋转后仍超宽', '整批订单无法安全放入常规区或旋转区',
        '当前膜宽不存在安全的自动分栏方案'))


def header_space_failure(error):
    return any(message in str(error) for message in (
        '膜标签高度带内没有批次标签的透明空位',
        '膜标签高度带内没有平台文字的透明空位',
        '平台文字没有可复用的二维码透明空位',
    ))


def recover_header_space(paths, settings, error, progress, analysis_ready):
    """Keep the batch running by reserving external label footprint."""
    if not settings.preserve_header_gap or not header_space_failure(error):
        raise error
    adopted = replace(settings, preserve_header_gap=False)
    detail = str(error)
    source = detail.split('：', 1)[0]
    kind = (
        '原值：复用膜标签透明带；采用值：整批外置标签占位；'
        '原因：原透明带不足；影响：可能增加少量排版长度'
    )
    action = '已继续排版并重算刀位；修改入口：打印参数 > 膜标签与刀码预览'

    def analyzed(data):
        rows = data.setdefault('image_anomalies', [])
        if not any(row.get('kind') == kind for row in rows):
            rows.append({
                'source': source,
                'path': '',
                'kind': kind,
                'action': action,
            })
        data['header_space_recovery'] = {
            'reason': detail,
            'original': '复用膜标签透明带',
            'adopted': '整批外置标签占位',
            'impact': '标签计入真实占位，可能增加少量排版长度',
            'edit_path': '打印参数 > 膜标签与刀码预览',
        }
        if analysis_ready:
            analysis_ready(data)

    if progress:
        progress(
            '膜标签透明空位恢复', 0, 1,
            f'{source} · 透明空位不足，改用整批外置标签占位并继续',
        )
    result = plan_layout(paths, adopted, progress, analyzed)
    if progress:
        progress(
            '膜标签透明空位恢复', 1, 1,
            '外置标签占位排版完成；订单、刀位和像素安全检查继续执行',
        )
    return paths, adopted, result


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
        reports = []
        result = plan_layout(paths, settings, progress, reports.append)
        selected_settings, selected_report = settings, reports[-1] if reports else None
        original_height = result[3]
        comparison = (selected_report or {}).get('rotation_comparison')
        majority_selected = bool(
            comparison
            and comparison.get('selected_strategy') == '多数并排区 + 剩余旋转区'
        )
        if (settings.auto_fit_width and settings.cutter_compare_whole_rotation
                and not majority_selected
                and not any(degrees % 360 for _, degrees in settings.manual_rotations)):
            from .width_fit import fit_rotation_overflow
            candidate_settings = fit_rotation_overflow(paths, settings, progress)
            if candidate_settings.dimension_overrides != settings.dimension_overrides:
                candidate_reports = []
                try:
                    candidate = plan_layout(
                        paths, candidate_settings, progress, candidate_reports.append)
                except ValueError:
                    candidate = None
                if candidate is not None and candidate[3] < result[3]:
                    result, selected_settings = candidate, candidate_settings
                    selected_report = candidate_reports[-1] if candidate_reports else selected_report
                    comparison = (selected_report or {}).get('rotation_comparison')
                    if comparison is not None:
                        scale = 25.4 / selected_settings.dpi / 1000
                        comparison.update(
                            normal_m=original_height * scale,
                            rotation_m=result[3] * scale,
                            saved_m=(original_height - result[3]) * scale,
                            selected_strategy='完整订单局部贪心',
                        )
                    if progress:
                        saved = (original_height - result[3]) * 25.4 / selected_settings.dpi / 1000
                        progress('贪心旋转比较', len(paths), len(paths),
                                 f'已选择完整订单局部最优组合；节省 {max(0, saved):.3f} 米')
        if analysis_ready and selected_report:
            analysis_ready(selected_report)
        return paths, selected_settings, result
    except ValueError as error:
        if header_space_failure(error):
            try:
                return recover_header_space(
                    paths, settings, error, progress, analysis_ready
                )
            except ValueError as recovered_error:
                error = recovered_error
                settings = replace(settings, preserve_header_gap=False)
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
