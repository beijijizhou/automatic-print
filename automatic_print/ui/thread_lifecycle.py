def thread_is_running(thread) -> bool:
    if thread is None:
        return False
    try:
        return thread.isRunning()
    except RuntimeError:
        return False


def discard_stopped_thread(owner, thread_name: str, worker_name: str) -> bool:
    thread = getattr(owner, thread_name, None)
    if thread_is_running(thread):
        return False
    setattr(owner, thread_name, None)
    setattr(owner, worker_name, None)
    return True
