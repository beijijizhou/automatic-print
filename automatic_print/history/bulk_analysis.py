"""Independent folder comparisons, durable partial results and fair totals."""
from uuid import uuid4
from pathlib import Path
from dataclasses import replace
from time import monotonic
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from ..cancellation import TaskCancelled
from ..layout import discover_images
from ..layout_engine.batch_analysis import analyze_batch
from ..layout_engine.film_comparison import compare_films
from .store import save_run


def analyze_folders(folders, settings, progress=None, cancellation=None, path=None, parallelism=4):
    records, errors, group = [], [], uuid4().hex
    folders = list(dict.fromkeys(Path(folder).resolve() for folder in folders))
    workers = max(1, min(8, int(parallelism), len(folders)))
    settings = replace(settings, compare_reference_films=True, film_geometry_workers=max(1, 4//workers))
    started = monotonic()
    stopped = False
    def calculate(index, folder):
        def report(stage, current, total, filename):
            if cancellation:
                cancellation.check()
            if progress:
                progress(index, str(folder), stage, current, total, filename)
        report('扫描文件夹', 0, 0, str(folder))
        images = discover_images(folder)
        if not images:
            raise ValueError('文件夹没有支持的图片')
        analysis = analyze_batch(images, settings)
        analysis['film_comparison'] = compare_films(images, settings, report)
        if cancellation:
            cancellation.check()
        result = {'analysis': analysis, 'preview_only': True,
                  'comparison_only': True, 'group_id': group,
                  'bulk_parallelism': workers}
        record = save_run(f'{group}-{index}', folder, '', settings, result, path)
        # A persisted result remains complete even if stop arrives during the write.
        if progress:
            progress(index, str(folder), '批次分析完成', len(images), len(images), str(folder))
        return record

    def is_stopped():
        try:
            if cancellation:
                cancellation.check()
            return False
        except TaskCancelled:
            return True

    next_index, pending = 0, {}
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='batch-analysis') as pool:
        while pending or next_index < len(folders):
            stopped = stopped or is_stopped()
            while not stopped and len(pending) < workers and next_index < len(folders):
                pending[pool.submit(calculate, next_index, folders[next_index])] = next_index
                next_index += 1
            if not pending:
                break
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index = pending.pop(future)
                try:
                    records.append(future.result())
                except TaskCancelled:
                    stopped = True
                except Exception as error:
                    errors.append({'folder': str(folders[index]), 'error': str(error)})
                    if progress:
                        progress(index, str(folders[index]), '批次失败，继续下一批', 0, 0, str(error))
    records.sort(key=lambda record: int(record['id'].rsplit('-', 1)[1]))
    return {'records': records, 'errors': errors, 'stopped': stopped,
            'seconds': monotonic()-started, 'group_id': group,
            'actual_parallelism': min(workers, next_index)}


def summary_text(records):
    if not records:
        return '尚无完成的批次数据。'
    totals = {}
    for record in records:
        for row in record['comparison']['rows']:
            key = (row['film_mm'], row['rotation_allowed'])
            item = totals.setdefault(key, {'area': 0, 'length': 0, 'images': 0, 'count': 0})
            if not row['error']:
                item['area'] += row['film_area_m2']
                item['length'] += row['length_m']
                item['images'] += row['image_area_m2']
                item['count'] += 1
    complete = [(key, item) for key, item in totals.items() if item['count'] == len(records)]
    best = min(complete, key=lambda entry: entry[1]['area']) if complete else None
    lines = [f'汇总 {len(records)} 个完成批次（不混合排版）；只排名覆盖全部批次的方案。']
    for (width, rotation), item in sorted(totals.items()):
        occupancy = 100*item['images']/item['area'] if item['area'] else 0
        lines.append(f"{width/10:g}厘米 · {'允许旋转' if rotation else '常规'}："
                     f"可用 {item['count']}/{len(records)} 批 · {item['length']:.3f}米"
                     f" · {item['area']:.3f}平方米 · 占位 {occupancy:.1f}%"+
                     ('（部分批次无解，不参与排名）' if item['count'] != len(records) else ''))
    lines.append(f"理论面积最省：{best[0][0]/10:g}厘米 · "
                 f"{'允许旋转' if best[0][1] else '常规'}" if best else '没有覆盖全部批次的安全方案。')
    lines.append('仅供规格评估，不自动更改生产选择；失败、未完成批次不计入上述汇总。')
    return '\n'.join(lines)
