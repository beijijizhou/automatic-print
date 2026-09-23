"""One bounded RIIN import-to-PRN workflow without physical printing."""
from pathlib import Path

from . import output as riin_output
from .desktop_controls import desktop
from .desktop_controls.dialogs import confirm_import


def automate_layout_to_prn(
    handle, process_id, source, output, paths=None, progress=None
):
    report = progress or (lambda _message: None)
    report('RIIN正在核对待导入的PNG清单…')
    if paths is None:
        paths, _selection = desktop.png_import_paths(source)
    else:
        paths = [Path(path).resolve(strict=True) for path in paths]
        if not paths or any(path.suffix.lower() != '.png' for path in paths):
            raise ValueError('本地排版结果清单必须包含至少一个现有PNG文件。')
    chunks = desktop.import_chunks(paths)
    target = Path(output).resolve()
    if target.exists():
        raise ValueError(f'PRN输出已存在，不会覆盖：{target}')
    report('RIIN正在创建新的打印文档…')
    created = riin_output.new_document(handle)
    steps = [created]
    for index in range(len(chunks)):
        report(f'RIIN正在打开第 {index + 1}/{len(chunks)} 组图片选择窗口…')
        desktop.open_import(handle)
        report(f'RIIN正在提交第 {index + 1}/{len(chunks)} 组PNG路径…')
        submitted = desktop.submit_import_paths(process_id, paths, index)
        report(
            f'RIIN正在核对第 {index + 1}/{len(chunks)} 组导入图像设置…'
        )
        confirmed = confirm_import(process_id, report)
        steps.extend((submitted, confirmed))
    if created.get('title'):
        report('RIIN图片导入完成；正在重新选择本次打印文档…')
        steps.append(desktop.select_document(handle, created['title']))
    report('RIIN正在打开文件输出设置…')
    steps.append(desktop.open_output(handle))
    report('RIIN正在确认输出到文件模式…')
    steps.append(riin_output.begin_file_output(process_id))
    report(f'RIIN正在设置PRN保存位置：{target.name}…')
    steps.append(riin_output.save_print_file(process_id, target))
    report(f'RIIN正在生成PRN文件：{target.name}…')
    file_status = riin_output.wait_for_print_file(target)
    steps.append(file_status)
    report(f'PRN生成完成；正在加载到PrintExp：{target.name}…')
    steps.append(riin_output.load_printexp(target))
    report(f'PRN已加载到PrintExp：{target.name}。')
    return {
        'state': 'completed', 'source': str(Path(source).resolve()),
        'image_count': len(paths), 'chunk_count': len(chunks),
        'output': str(target), 'bytes': file_status['bytes'],
        'riin_complete': file_status['state'] == 'prn_generated',
        'riin_task': file_status.get('riin_task'), 'steps': steps,
    }
