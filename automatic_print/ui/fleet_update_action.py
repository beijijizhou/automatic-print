"""One-click orchestration for publishing the latest fleet source version."""


def start_latest_update(page):
    page.signal_result.setText("正在准备最新版本更新指令…")
    page.sections.setCurrentWidget(page.update_section)
    panel = page.update_panel
    target = panel.target()
    if panel.loader.lock.locked() or not target or not target.revision:
        page._pending_latest_update = True
        if not panel.loader.lock.locked():
            panel.load_versions()
        page.signal_update_button.setEnabled(False)
        message = "正在读取最新版本；读取完成后会自动继续，无需再次点击。"
        panel.summary.setText(message)
        page.signal_result.setText(message)
        return
    page._pending_latest_update = False
    page.signal_update_button.setEnabled(True)
    panel.versions.setCurrentIndex(0)
    panel._select(True)
    targets = panel._selected_targets()
    if not targets:
        message = "当前已登记电脑的版本与功能都已同步。"
        panel.summary.setText(message)
        page.signal_result.setText(message)
        return
    page.signal_result.setText(
        f"已选择 {len(targets)} 台待同步电脑，正在等待人工确认…"
    )
    if panel.start_all():
        page.signal_update_button.setEnabled(False)
        page.signal_result.setText(
            f"已确认，正在向 {len(targets)} 台电脑发布最新版本更新指令…"
        )
    else:
        page.signal_result.setText(panel.summary.text())


def resume_pending_latest_update(page):
    if not getattr(page, "_pending_latest_update", False):
        return
    target = page.update_panel.target()
    if not target or not target.revision:
        fail_pending_latest_update(page, "origin/main 没有可发布版本")
        return
    start_latest_update(page)


def fail_pending_latest_update(page, error):
    if not getattr(page, "_pending_latest_update", False):
        return
    page._pending_latest_update = False
    page.signal_update_button.setEnabled(True)
    page.signal_result.setText(f"无法读取最新版本：{error}")
