"""Bounded actions for RIIN import dialogs."""
import time


def confirm_import(process_id):
    from pywinauto import Desktop
    dialog = Desktop(backend='win32').window(
        process=process_id, title='导入图像设置', class_name='#32770')
    dialog.wait('visible', timeout=5)
    dialog.child_window(title='确定', class_name='Button').click()
    dialog.wait_not('visible', timeout=30)
    return {'state': 'import_settings_accepted', 'parameters': '沿用当前导入参数'}


def cancel_import(process_id):
    """Cancel only the currently unconfirmed RIIN import settings dialog."""
    from pywinauto import Desktop
    dialog = Desktop(backend='win32').window(
        process=process_id, title='导入图像设置', class_name='#32770')
    dialog.wait('visible', timeout=5)
    dialog.child_window(title='取消', class_name='Button').click()
    dialog.wait_not('visible', timeout=30)
    return {'state': 'unconfirmed_import_cancelled'}


def cancel_crop_warning(process_id):
    """Cancel only RIIN's exact destructive auto-crop confirmation."""
    from pywinauto import Desktop
    expected = '图元超出画布，超出部分将被自动裁切，是否继续打印?'
    dialogs = [
        window for window in Desktop(backend='win32').windows(process=process_id)
        if window.class_name() == '#32770' and window.window_text() == 'RIIN'
        and window.is_visible()
        and expected in {item.window_text() for item in window.descendants()}
    ]
    if len(dialogs) != 1:
        raise RuntimeError(f'应找到一个RIIN自动裁切警告，实际找到{len(dialogs)}个。')
    dialog = Desktop(backend='win32').window(handle=dialogs[0].handle)
    dialog.child_window(title='取消', control_id=7, class_name='Button').click()
    dialog.wait_not('visible', timeout=10)
    return {'state': 'unsafe_crop_cancelled', 'warning': expected}


def acknowledge_import_errors(process_id):
    from pywinauto import Desktop
    errors = []
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and len(errors) < 60:
        dialogs = [w for w in Desktop(backend='win32').windows(process=process_id)
                   if w.class_name() == '#32770' and w.window_text() == 'RIIN']
        if not dialogs:
            time.sleep(0.5)
            continue
        dialog = dialogs[0]
        text = '\n'.join(w.window_text() for w in dialog.descendants())
        if '暂不支持该文件格式' not in text:
            break
        errors.append(text)
        Desktop(backend='win32').window(handle=dialog.handle).child_window(
            title='确定', class_name='Button').click()
        time.sleep(0.2)
    return {'acknowledged_errors': errors}
