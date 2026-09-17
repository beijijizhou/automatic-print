from test_developer_mode import window, APP


def test_settings_categories_reuse_controls_and_persist_parallelism(tmp_path, monkeypatch):
    path = tmp_path/'prefs.ini'
    owner = window(path)
    tabs = owner.print_settings_tabs
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        '膜的设置', '排版规则', '标签与文字', '输出与并行']
    assert tabs.widget(0).isAncestorOf(owner.cutter_settings.film)
    assert tabs.widget(0).isAncestorOf(owner.cutter_settings.printable)
    assert tabs.widget(0).isAncestorOf(owner.cutter_settings.knife)
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
    label = tabs.widget(1).layout().labelForField(owner.spacing)
    assert '自由排版' in label.text()
    owner.settings_dialog.show()
    APP.processEvents()
    assert not owner.generate_button.isVisible()
    save_y = owner.save_settings_button.mapTo(owner.settings_dialog, owner.save_settings_button.rect().topLeft()).y()
    assert save_y < owner.settings_dialog.height() - 40
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
