"""One bounded RIIN import-to-PRN workflow without physical printing."""
from pathlib import Path

from . import output as riin_output
from .desktop_controls import desktop
from .desktop_controls.dialogs import confirm_import


def automate_layout_to_prn(handle, process_id, source, output, paths=None):
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
    created = riin_output.new_document(handle)
    steps = [created]
    for index in range(len(chunks)):
        desktop.open_import(handle)
        submitted = desktop.submit_import_paths(process_id, paths, index)
        steps.extend((submitted, confirm_import(process_id)))
    if created.get('title'):
        steps.append(desktop.select_document(handle, created['title']))
    steps.append(desktop.open_output(handle))
    steps.append(riin_output.begin_file_output(process_id))
    steps.append(riin_output.save_print_file(process_id, target))
    file_status = riin_output.wait_for_print_file(target)
    steps.append(file_status)
    steps.append(riin_output.load_printexp(target))
    return {
        'state': 'completed', 'source': str(Path(source).resolve()),
        'image_count': len(paths), 'chunk_count': len(chunks),
        'output': str(target), 'bytes': file_status['bytes'],
        'riin_complete': file_status['state'] == 'prn_generated',
        'riin_task': file_status.get('riin_task'), 'steps': steps,
    }
