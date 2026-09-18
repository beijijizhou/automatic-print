"""Read native RIIN controls from an elevated interactive desktop session."""
import ctypes
from ctypes import wintypes
import time
from pathlib import Path


def png_import_paths(source):
    root = Path(source).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('导入来源必须是文件夹。')
    paths = sorted((p.resolve() for p in root.rglob('*')
                    if p.is_file() and p.suffix.lower() == '.png'), key=str)
    if not paths:
        raise ValueError('来源目录没有PNG图片。')
    if any(not p.is_relative_to(root) for p in paths):
        raise ValueError('来源包含指向目录外的文件链接，请单独确认。')
    selection = ' '.join('"' + str(p) + '"' for p in paths)
    if len(selection) > 30000:
        raise ValueError('文件列表超过文件选择框容量，请按子批次导入。')
    return paths, selection


def import_chunks(paths, limit=3800):
    chunks, current, length = [], [], 0
    for path in paths:
        size = len(str(path)) + 3
        if size > limit:
            raise ValueError('单个路径超过文件选择框容量。')
        if current and length + size > limit:
            chunks.append(current)
            current, length = [], 0
        current.append(path)
        length += size
    if current:
        chunks.append(current)
    return chunks


def submit_import(process_id, source, chunk_index=0):
    from pywinauto import Desktop
    all_paths, _selection = png_import_paths(source)
    chunks = import_chunks(all_paths)
    if not 0 <= chunk_index < len(chunks):
        raise ValueError('导入分段索引超出范围。')
    paths = chunks[chunk_index]
    selection = ' '.join('"' + str(p) + '"' for p in paths)
    dialogs = [w for w in Desktop(backend='win32').windows(process=process_id)
               if w.window_text() in ('打开', 'Open') and w.is_visible()]
    if len(dialogs) != 1:
        raise RuntimeError('请先打开唯一的RIIN导入窗口，再提交图片。')
    dialog = Desktop(backend='uia').window(handle=dialogs[0].handle)
    field = dialog.child_window(auto_id='1148', control_type='Edit')
    field.set_edit_text(selection)
    actual = field.get_value()
    if actual != selection:
        raise RuntimeError(f'文件选择框未完整接收图片清单，尚未执行导入。'
                           f'预期{len(selection)}字符，实际{len(actual)}字符：{actual[:120]!r}')
    dialog.child_window(auto_id='1', control_type='Button').invoke()
    return dict(submitted_count=len(paths), files=[str(p) for p in paths],
                chunk_index=chunk_index, chunk_count=len(chunks), total_count=len(all_paths),
                state='submitted', message='已提交导入；需在RIIN核对加载完成后的图片数量。')


def open_import(handle):
    """Open the observed RIIN ribbon's import dialog without starting production."""
    from pywinauto import Desktop
    desktop = Desktop(backend='win32')
    window = desktop.window(handle=handle)
    window.restore()
    window.set_focus()
    ribbon = window.child_window(control_id=59398).wrapper_object()
    rect = ribbon.rectangle()
    if rect.height() != 107 or rect.width() < 1000:
        raise RuntimeError('RIIN工具栏布局与已验证版本不同，请重新校准导入位置。')
    # This legacy MFC ribbon exposes no named buttons through UI Automation.
    ribbon.click(coords=(187, 58))
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        dialogs = [w for w in desktop.windows(process=window.process_id())
                   if w.class_name() == '#32770' and w.is_visible()
                   and w.window_text() in ('打开', 'Open')]
        if dialogs:
            return [dict(handle=w.handle, title=w.window_text(),
                         controls=window_inventory(w.handle)) for w in dialogs]
        time.sleep(0.2)
    raise RuntimeError('导入请求已发送，但未检测到文件选择窗口；请检查RIIN当前状态。')


def dialog_inventory(process_id):
    from pywinauto import Desktop
    return [dict(handle=w.handle, title=w.window_text(),
                 controls=window_inventory(w.handle),
                 accessible_controls=accessible_inventory(w.handle))
            for w in Desktop(backend='win32').windows(process=process_id)
            if w.class_name() == '#32770' and w.is_visible() and w.window_text()]


def confirm_import(process_id):
    from pywinauto import Desktop
    dialog = Desktop(backend='win32').window(process=process_id, title='导入图像设置', class_name='#32770')
    dialog.wait('visible', timeout=5)
    dialog.child_window(title='确定', class_name='Button').click()
    return {'state': 'import_settings_accepted', 'parameters': '沿用当前导入参数'}


def import_menu(handle):
    from pywinauto import Desktop
    window = Desktop(backend='win32').window(handle=handle)
    window.set_focus()
    ribbon = window.child_window(control_id=59398).wrapper_object()
    if ribbon.rectangle().height() != 107:
        raise RuntimeError('工具栏布局改变，需要重新校准。')
    ribbon.click_input(coords=(187, 96))
    return {'state': 'import_menu_requested'}


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


def select_document(handle, title):
    from pywinauto import Desktop
    window = Desktop(backend='win32').window(handle=handle)
    document = window.child_window(title=title).wrapper_object()
    mdi = window.child_window(class_name='MDIClient').wrapper_object()
    mdi.send_message(0x0222, document.handle, 0)
    return {'state': 'document_selected', 'title': title}


def open_output(handle):
    from pywinauto import Desktop
    window = Desktop(backend='win32').window(handle=handle)
    ribbon = window.child_window(control_id=59398).wrapper_object()
    if ribbon.rectangle().height() != 107:
        raise RuntimeError('工具栏布局改变，需要重新校准。')
    ribbon.click(coords=(136, 58))
    return {'state': 'output_dialog_requested'}


def accessible_inventory(handle):
    from pywinauto import Desktop
    window = Desktop(backend='uia').window(handle=handle).wrapper_object()
    return [dict(name=item.element_info.name, kind=item.element_info.control_type,
                 automation_id=item.element_info.automation_id,
                 bounds=[item.rectangle().left, item.rectangle().top,
                         item.rectangle().right, item.rectangle().bottom])
            for item in window.descendants()[:500]]


def window_inventory(handle):
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumChildWindows.argtypes = (wintypes.HWND, callback_type, wintypes.LPARAM)
    user.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user.GetDlgCtrlID.argtypes = (wintypes.HWND,)
    user.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user.IsWindowVisible.argtypes = (wintypes.HWND,)
    controls = []

    @callback_type
    def collect(hwnd, _param):
        title, kind = ctypes.create_unicode_buffer(2048), ctypes.create_unicode_buffer(256)
        user.GetWindowTextW(hwnd, title, len(title))
        user.GetClassNameW(hwnd, kind, len(kind))
        rect = wintypes.RECT()
        user.GetWindowRect(hwnd, ctypes.byref(rect))
        controls.append(dict(handle=int(hwnd), text=title.value, class_name=kind.value,
                             control_id=user.GetDlgCtrlID(hwnd),
                             visible=bool(user.IsWindowVisible(hwnd)),
                             bounds=[rect.left, rect.top, rect.right, rect.bottom]))
        return True

    user.EnumChildWindows(handle, collect, 0)
    return controls
