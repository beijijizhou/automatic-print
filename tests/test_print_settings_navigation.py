from test_developer_mode import window, APP
from automatic_print.ui.bulk_generation import BulkGenerationDialog


def test_settings_categories_reuse_controls_and_persist_parallelism(tmp_path):
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
    assert owner.worker_threads.value() == 4
    assert owner.segmented_output.workers.value() == 4
    assert owner.bulk_parallelism.value() == 4
    # The spacing callback still owns the same label after layout transfer.
    owner.cutter_settings.mode.setCurrentIndex(owner.cutter_settings.mode.findData('free'))
    label = tabs.widget(1).layout().labelForField(owner.spacing)
    assert '自由排版' in label.text()
    owner.settings_dialog.show()
    for index in range(tabs.count()):
        tabs.setCurrentIndex(index)
        APP.processEvents()
        assert owner.settings_dialog.grab().save(str(tmp_path/f'settings-{index}.png'))
    owner.bulk_parallelism.setValue(2)
    owner.worker_threads.setValue(3)
    owner.preference_autosave.flush()
    dialog = BulkGenerationDialog(owner)
    assert dialog.parallelism.isHidden()
    dialog.begin()  # Empty queue; copies saved production concurrency without starting work.
    assert dialog.parallelism.value() == 2
    assert dialog.thread is None
    dialog.close()
    owner.settings_dialog.close()
    owner.close()
    reopened = window(path)
    assert reopened.bulk_parallelism.value() == 2
    assert reopened.worker_threads.value() == 3
    reopened.close()
