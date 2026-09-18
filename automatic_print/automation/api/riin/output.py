"""File-only RIIN output; never select a live printer transport."""
from pathlib import Path
import time


def new_document(handle):
    from pywinauto import Desktop
    window = Desktop(backend='win32').window(handle=handle)
    before = {
        child.handle for child in window.children()
        if child.window_text().startswith(('未命名-', 'Untitled-'))
    }
    ribbon = window.child_window(control_id=59398).wrapper_object()
    if ribbon.rectangle().height() != 107:
        raise RuntimeError('RIIN工具栏布局改变，需要重新校准。')
    ribbon.click(coords=(36, 58))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        created = [
            child for child in window.children()
            if child.handle not in before
            and child.window_text().startswith(('未命名-', 'Untitled-'))
        ]
        if len(created) == 1:
            return {
                'state': 'new_document_created',
                'title': created[0].window_text(),
                'handle': created[0].handle,
            }
        if len(created) > 1:
            raise RuntimeError('RIIN一次创建了多个新文档，未继续自动输出。')
        time.sleep(0.2)
    raise RuntimeError('RIIN没有显示新建文档，未继续自动输出。')


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


def riin_output_task(output):
    """Read the newest RIIN task row for one exact output path."""
    from pywinauto import Desktop

    target = str(Path(output).resolve())
    windows = [
        window for window in Desktop(backend='uia').windows()
        if window.window_text().endswith(' - RIIN')
    ]
    if len(windows) != 1:
        return None
    matches = []
    for item in windows[0].descendants(control_type='ListItem'):
        texts = [item.window_text()]
        texts.extend(
            child.window_text() for child in item.descendants()
            if child.window_text()
        )
        if target not in texts:
            continue
        state = next((text for text in texts if text in {
            '等待打印...', '正在打印...', '打印完成', '打印出错', '停止',
        }), '')
        percent = next((text for text in texts if text.endswith('%')), '')
        matches.append({
            'state': state, 'percent': percent, 'output': target,
            'texts': texts,
        })
    return matches[-1] if matches else None


def wait_for_print_file(output, timeout=7200):
    """Wait for RIIN task completion and a stable, non-placeholder PRN."""
    target = Path(output).resolve()
    deadline = time.monotonic() + timeout
    previous_size = -1
    stable_reads = 0
    observed_task = False
    while time.monotonic() < deadline:
        task = riin_output_task(target)
        observed_task = observed_task or task is not None
        if task and task['state'] in {'打印出错', '停止'}:
            raise RuntimeError(
                f"RIIN文件任务{task['state']}：{target}"
            )
        try:
            size = target.stat().st_size
        except FileNotFoundError:
            size = 0
        task_finished = task is not None and task['state'] == '打印完成'
        legacy_finished = not observed_task and size >= 1024
        if (task_finished or legacy_finished) and size >= 1024 and size == previous_size:
            stable_reads += 1
            if stable_reads >= 3:
                return {
                    'state': 'prn_generated', 'output': str(target),
                    'bytes': size, 'riin_task': task,
                }
        else:
            stable_reads = 0
        previous_size = size
        time.sleep(0.5)
    raise TimeoutError(
        f'等待RIIN生成PRN超过{timeout / 60:g}分钟：{target}'
    )


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
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        controls = [item for item in main.descendants() if item.is_visible()]
        if any(item.window_text() == target.name for item in controls):
            texts = {item.window_text() for item in controls}
            return {
                'state': 'printexp_loaded', 'output': str(target),
                'task': target.name,
                'progress': '0.00%' if '0.00%' in texts else 'loaded',
                'copies': '0 / 1' if '0 / 1' in texts else 'loaded',
            }
        time.sleep(0.2)
    raise RuntimeError(f'PrintExp未显示已加载的PRN任务：{target.name}')
