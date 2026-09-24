"""Canonical PrintExp states, projections, and control transitions."""

IDLE = "idle"
READY = "ready"
PRINTING = "printing"
PAUSED = "paused"
CLEANING = "cleaning"
UNKNOWN = "unknown"

START_PRINT = "start_print"
PAUSE_PRINT = "pause_print"
CLEAN_RESUME = "clean_resume"

PRINTER_STATES = frozenset({IDLE, READY, PRINTING, PAUSED, CLEANING, UNKNOWN})
CONTROL_ACTIONS = frozenset({START_PRINT, PAUSE_PRINT, CLEAN_RESUME})

_PROJECTIONS = {
    IDLE: ("idle", "PrintExp在线待机"),
    READY: ("idle", "PrintExp待打印"),
    PRINTING: ("running", "PrintExp打印中"),
    PAUSED: ("running", "PrintExp已暂停"),
    CLEANING: ("running", "PrintExp清洗中"),
    UNKNOWN: ("failed", "PrintExp状态未确认"),
}

_LABELS = {
    IDLE: "空闲",
    READY: "待打印",
    PRINTING: "打印中",
    PAUSED: "已暂停",
    CLEANING: "清洗中",
    UNKNOWN: "状态未确认",
}

_TRANSITIONS = {
    (START_PRINT, READY): (PRINTING,),
    (START_PRINT, PAUSED): (PRINTING,),
    (PAUSE_PRINT, PRINTING): (PAUSED,),
    (CLEAN_RESUME, PRINTING): (PAUSED, CLEANING, PRINTING),
    (CLEAN_RESUME, PAUSED): (CLEANING, PRINTING),
}


def normalize_printer_state(value):
    state = str(value or "").strip().casefold()
    return state if state in PRINTER_STATES else UNKNOWN


def inspect_printer_state(
    *, status_text, pause_enabled, pause_caption, print_enabled, task_loaded=False,
):
    """Translate native control facts without advancing state speculatively."""
    if "清洗" in str(status_text):
        return CLEANING
    if pause_enabled:
        if pause_caption == "继续":
            return PAUSED
        if pause_caption == "暂停" and "打印" in str(status_text):
            return PRINTING
    if print_enabled and not pause_enabled:
        return READY if task_loaded else IDLE
    return UNKNOWN


def project_printer_state(value):
    return _PROJECTIONS[normalize_printer_state(value)]


def printer_state_label(value):
    return _LABELS[normalize_printer_state(value)]


def transition_path(action, state):
    return _TRANSITIONS.get((str(action), normalize_printer_state(state)))


def control_allowed(
    action, state, *, progress=None, task_name_verified=False, batch_name="",
):
    state = normalize_printer_state(state)
    if transition_path(action, state) is None:
        return False
    if action != START_PRINT:
        return True
    if not task_name_verified or not str(batch_name or "").strip():
        return False
    value = _number(progress)
    if state == READY:
        return value == 0
    return state == PAUSED and value is not None and 0 <= value < 100


def require_control(
    action, state, *, progress=None, task_name_verified=False, batch_name="",
):
    if control_allowed(
        action, state, progress=progress, task_name_verified=task_name_verified,
        batch_name=batch_name,
    ):
        return transition_path(action, state)
    state = normalize_printer_state(state)
    if action == START_PRINT and not task_name_verified:
        raise RuntimeError("PrintExp 当前任务名尚未核实，未发送打印指令。")
    if action == START_PRINT and not str(batch_name or "").strip():
        raise RuntimeError("PrintExp 当前没有已确认的 PRN，未发送打印指令。")
    if action == START_PRINT and state == READY:
        raise RuntimeError("PrintExp 待打印任务不是 0%，未发送开始指令。")
    if action == START_PRINT and state == PAUSED:
        raise RuntimeError("PrintExp 暂停任务进度无效或已完成，未发送继续指令。")
    if action == PAUSE_PRINT:
        raise RuntimeError("PrintExp 当前不是正在打印或已暂停状态，未发送暂停指令。")
    if action == CLEAN_RESUME:
        raise RuntimeError("PrintExp 当前不是正在打印或已暂停状态，未执行清洗。")
    raise RuntimeError("PrintExp 当前状态不允许执行该控制指令。")


def start_button_text(state):
    return "继续打印" if normalize_printer_state(state) == PAUSED else "开始打印"


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
