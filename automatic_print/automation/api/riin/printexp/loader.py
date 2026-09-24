"""Safely submit a generated PRN to PrintExp without starting printing."""

import time
from pathlib import Path


def load_printexp(output):
    from pywinauto import Desktop

    from ...printerexp.status.loaded_task import record_loaded_task

    target = Path(output).resolve()
    if target.suffix.lower() != '.prn' or not target.is_file() or not target.stat().st_size:
        raise ValueError('必须提供已生成的非空.prn文件。')
    main = Desktop(backend='win32').window(title='PrintExp')
    dialog = Desktop(backend='win32').window(
        process=main.process_id(), title='打开', class_name='#32770')
    if not dialog.exists(timeout=1) or not dialog.is_visible():
        button = main.child_window(control_id=5, class_name='Button', title='打开')
        button.parent().post_message(0x0111, 5, button.handle)
    dialog.wait('visible', timeout=5)
    ui_dialog = Desktop(backend='uia').window(handle=dialog.handle)
    field = ui_dialog.child_window(auto_id='1148', control_type='Edit')
    field.set_edit_text(str(target))
    if field.get_value() != str(target):
        raise RuntimeError('PrintExp文件路径核对失败，未提交。')
    field.set_focus()
    field.type_keys('{ENTER}')
    dialog.wait_not('visible', timeout=10)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        controls = [item for item in main.descendants() if item.is_visible()]
        if any(item.window_text() == target.name for item in controls):
            texts = {item.window_text() for item in controls}
            record_loaded_task(target, verified=True)
            return {
                'state': 'printexp_loaded', 'output': str(target),
                'task': target.name,
                'progress': '0.00%' if '0.00%' in texts else 'loaded',
                'copies': '0 / 1' if '0 / 1' in texts else 'loaded',
                'task_name_verified': True,
            }
        time.sleep(0.2)
    receipt = record_loaded_task(target, verified=False)
    return {
        'state': 'printexp_loaded', 'output': str(target),
        'task': target.name, 'progress': 'loaded', 'copies': 'loaded',
        'task_name_verified': False,
        'verification': receipt['verification'],
    }
