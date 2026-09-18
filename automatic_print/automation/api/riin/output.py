"""File-only RIIN output; never select a live printer transport."""
from pathlib import Path


def new_document(handle):
    from pywinauto import Desktop
    window = Desktop(backend='win32').window(handle=handle)
    ribbon = window.child_window(control_id=59398).wrapper_object()
    if ribbon.rectangle().height() != 107:
        raise RuntimeError('RIIN工具栏布局改变，需要重新校准。')
    ribbon.click(coords=(36, 58))
    return {'state': 'new_document_requested'}


def begin_file_output(process_id):
    from pywinauto import Desktop
    dialog = Desktop(backend='win32').window(
        process=process_id, title='打印确认', class_name='#32770')
    dialog.wait('visible', timeout=5)
    mode = dialog.child_window(control_id=13006, class_name='ComboBox').selected_text()
    if mode not in ('文件', 'File'):
        raise RuntimeError(f'发送方式为{mode!r}，不是文件输出，未执行。')
    dialog.child_window(control_id=1, class_name='Button').click()
    return {'state': 'file_output_requested', 'transport': mode}


def save_print_file(process_id, output):
    from pywinauto import Desktop
    target = Path(output).resolve()
    if target.suffix.lower() != '.prn' or target.exists():
        raise ValueError('输出必须是尚不存在的.prn文件。')
    target.parent.mkdir(parents=True, exist_ok=True)
    native = Desktop(backend='win32').window(
        process=process_id, title='另存为', class_name='#32770')
    native.wait('visible', timeout=5)
    dialog = Desktop(backend='uia').window(handle=native.handle)
    field = dialog.child_window(auto_id='1001', control_type='Edit')
    field.set_edit_text(str(target))
    if field.get_value() != str(target):
        raise RuntimeError('输出文件路径核对失败，未提交。')
    dialog.child_window(auto_id='1', control_type='Button').invoke()
    return {'state': 'file_generation_requested', 'output': str(target)}


def inspect_printexp():
    from pywinauto import Desktop
    from .desktop import accessible_inventory, dialog_inventory
    window = Desktop(backend='win32').window(title='PrintExp').wrapper_object()
    return dict(handle=window.handle, process_id=window.process_id(),
                controls=accessible_inventory(window.handle),
                dialogs=dialog_inventory(window.process_id()))


def load_printexp(output):
    """Load an existing PRN into the open dialog; do not start printing."""
    from pywinauto import Desktop
    target = Path(output).resolve()
    if target.suffix.lower() != '.prn' or not target.is_file() or not target.stat().st_size:
        raise ValueError('必须提供已生成的非空.prn文件。')
    main = Desktop(backend='win32').window(title='PrintExp')
    dialog = Desktop(backend='win32').window(
        process=main.process_id(), title='打开', class_name='#32770')
    if not dialog.exists(timeout=1) or not dialog.is_visible():
        main.set_focus()
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
    return {'state': 'load_requested', 'output': str(target)}
