"""Explicit user exit bypasses uninterruptible image and Qt thread teardown."""
import os


def terminate_process(code=0):
    os._exit(code)


def exit_now(window):
    # All production writes are staged/marked before work starts. Do not wait
    # for QThread, executor shutdown or native PNG encoders here.
    try:
        window.startup_update_timer.stop()
        window.clock.stop()
        window.preference_autosave.flush()
        window.hide()
        window.settings_dialog.hide()
    finally:
        terminate_process(0)
