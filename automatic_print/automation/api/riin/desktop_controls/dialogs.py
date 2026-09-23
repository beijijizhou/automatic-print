"""Bounded actions for RIIN import dialogs."""
import time


ORIGINAL_SIZE_LABELS = (
    '原尺寸', '原始尺寸', '原图尺寸', '实际尺寸', '原始图像大小', '100%'
)


def _normalized_label(value):
    return ''.join(
        character for character in str(value).casefold()
        if character.isalnum() or character == '%'
    )


def _original_size_controls(dialog):
    matches = []
    labels = []
    for control in dialog.descendants():
        try:
            text = control.window_text().strip()
            kind = control.class_name()
        except Exception:
            continue
        if text:
            labels.append(text)
        normalized = _normalized_label(text)
        if (
            kind == 'Button'
            and not any(word in normalized for word in ('缩放', '适应', '填充'))
            and any(
                _normalized_label(label) in normalized
                for label in ORIGINAL_SIZE_LABELS
            )
        ):
            matches.append(control)
    return matches, labels


def _checked(control):
    try:
        return int(control.get_check_state()) == 1
    except Exception:
        return False


def confirm_import(process_id, progress=None, manual_timeout=7_200):
    from pywinauto import Desktop
    dialog = Desktop(backend='win32').window(
        process=process_id, title='导入图像设置', class_name='#32770')
    dialog.wait('visible', timeout=5)
    controls, labels = _original_size_controls(dialog)
    if len(controls) == 1:
        original = controls[0]
        if not _checked(original):
            original.click()
            time.sleep(0.2)
        if _checked(original):
            selected = original.window_text().strip()
            if progress:
                progress(f'RIIN导入图像设置已确认“{selected}”；正在提交导入…')
            dialog.child_window(title='确定', class_name='Button').click()
            dialog.wait_not('visible', timeout=30)
            return {
                'state': 'original_size_confirmed',
                'parameters': selected,
                'confirmation': 'automatic',
            }

    reason = (
        '找到多个可能的原尺寸选项，无法安全自动选择'
        if len(controls) > 1
        else '未识别到可验证的原尺寸选项'
    )
    if progress:
        progress(
            f'{reason}；请在RIIN“导入图像设置”窗口手动选择原尺寸并点击确定。'
        )
    dialog.wait_not('visible', timeout=manual_timeout)
    return {
        'state': 'original_size_confirmed',
        'parameters': '原尺寸（用户在RIIN窗口确认）',
        'confirmation': 'manual',
        'reason': reason,
        'visible_labels': labels,
    }


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
