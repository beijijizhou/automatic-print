from PySide6.QtWidgets import QLabel

from test_developer_mode import window, APP


def test_settings_categories_reuse_controls_and_persist_parallelism(tmp_path, monkeypatch):
    path = tmp_path/'prefs.ini'
    owner = window(path)
    tabs = owner.print_settings_tabs
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        '切膜机', '自动排版', '标签与文字', '输出与并行']
    assert tabs.widget(0).isAncestorOf(owner.cutter_settings.film)
    assert tabs.widget(0).isAncestorOf(owner.cutter_settings.printable)
    assert tabs.widget(0).isAncestorOf(owner.cutter_settings.knife)
    assert tabs.widget(1).isAncestorOf(owner.cutter_settings.force_small_pair)
    assert tabs.widget(1).isAncestorOf(owner.cutter_settings.force_small_pair_sizes)
    assert tabs.widget(1).isAncestorOf(owner.cutter_settings.force_small_pair_limit)
    assert tabs.widget(0).isAncestorOf(owner.membrane_gap_enabled)
    assert tabs.widget(0).isAncestorOf(owner.membrane_gap)
    assert any(
        '剪膜机色块' in label.text()
        for label in tabs.widget(0).findChildren(QLabel)
    )
    assert tabs.widget(1).isAncestorOf(owner.spacing)
    assert tabs.widget(3).isAncestorOf(owner.bulk_parallelism)
    assert owner.automation_home.isAncestorOf(owner.combine_bulk_batches)
    assert not owner.settings_dialog.isAncestorOf(owner.combine_bulk_batches)
    assert owner.worker_threads.value() == 4
    assert owner.segmented_output.workers.value() == 4
    assert owner.bulk_parallelism.value() == 4
    assert not owner.combine_bulk_batches.isChecked()
    monkeypatch.setattr('automatic_print.ui.layout_values.os.cpu_count', lambda: 12)
    owner.worker_threads.setValue(1)
    assert owner.worker_threads.text() == '自动（最多4线程）'
    assert owner._layout_settings().worker_threads == 4
    owner.worker_threads.setValue(3)
    assert owner._layout_settings().worker_threads == 3
    # The spacing callback still owns the same label after layout transfer.
    owner.cutter_settings.mode.setCurrentIndex(owner.cutter_settings.mode.findData('free'))
    assert not owner.cutter_rules_form.isRowVisible(owner.membrane_gap_enabled)
    assert not owner.cutter_rules_form.isRowVisible(owner.membrane_gap)
    shrink_label = owner.layout_rules_form.labelForField(
        owner.cutter_settings.force_small_pair)
    assert shrink_label.text() == '并排缩小'
    gap_label = owner.cutter_rules_form.labelForField(owner.membrane_gap)
    assert gap_label.text().startswith('● 切膜 · ')
    assert owner.auto_fit_width.property('cutterProductionSetting') is not True
    label = tabs.widget(1).layout().labelForField(owner.spacing)
    assert '自由排版' in label.text()
    owner.cutter_settings.mode.setCurrentIndex(
        owner.cutter_settings.mode.findData('dual'))
    owner.settings_dialog.show()
    APP.processEvents()
    assert not owner.generate_button.isVisible()
    save_y = owner.save_settings_button.mapTo(owner.settings_dialog, owner.save_settings_button.rect().topLeft()).y()
    assert save_y + owner.save_settings_button.height() <= owner.settings_dialog.height()
    for index in range(tabs.count()):
        tabs.setCurrentIndex(index)
        APP.processEvents()
        assert owner.settings_dialog.grab().save(str(tmp_path/f'settings-{index}.png'))
    owner.bulk_parallelism.setValue(2)
    owner.combine_bulk_batches.setChecked(True)
    owner.worker_threads.setValue(3)
    owner.preference_autosave.flush()
    assert owner.bulk_parallelism.value() == 2
    owner.settings_dialog.close()
    owner.close()
    reopened = window(path)
    assert reopened.bulk_parallelism.value() == 2
    assert reopened.combine_bulk_batches.isChecked()
    assert reopened.worker_threads.value() == 3
    reopened.close()


def test_cutter_mode_is_pinned_above_every_main_and_settings_tab(tmp_path):
    owner = window(tmp_path/'pinned-mode.ini')
    owner.show()
    APP.processEvents()

    main_banner = owner.global_cutter_mode
    assert main_banner.isVisibleTo(owner)
    assert main_banner.mapTo(owner, main_banner.rect().topLeft()).y() < (
        owner.workspace_tabs.mapTo(owner, owner.workspace_tabs.rect().topLeft()).y())
    for index in range(owner.workspace_tabs.count()):
        if owner.workspace_tabs.isTabVisible(index):
            owner.workspace_tabs.setCurrentIndex(index)
            APP.processEvents()
            assert main_banner.isVisibleTo(owner)

    owner.settings_dialog.show()
    APP.processEvents()
    settings_banner = owner.settings_cutter_mode
    assert owner.settings_dialog.layout().indexOf(settings_banner) == 0
    for index in range(owner.print_settings_tabs.count()):
        owner.print_settings_tabs.setCurrentIndex(index)
        APP.processEvents()
        assert settings_banner.isVisibleTo(owner.settings_dialog)

    free = main_banner.mode.findData('free')
    main_banner.mode.setCurrentIndex(free)
    APP.processEvents()
    assert owner.cutter_settings.mode.currentData() == 'free'
    assert settings_banner.mode.currentData() == 'free'
    assert '无刀码' in main_banner.status.text()
    assert main_banner.property('cuttingMode') is False
    owner.close()
