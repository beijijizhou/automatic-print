from pathlib import Path

from automatic_print.ui.full_test_runner import full_test_phases
from automatic_print.ui.full_test_results import phase_summary, real_batch_file_summary
from test_developer_mode import APP, window


def test_full_test_phases_cover_suite_and_real_batches_without_prn(tmp_path):
    phases = full_test_phases(
        tmp_path, "python-test", tmp_path / "results",
    )

    assert [phase["name"] for phase in phases] == [
        "完整自动测试", "真实批次跨平台回归",
    ]
    assert phases[0]["program"] == "python-test"
    assert phases[0]["arguments"][:3] == ("-m", "pytest", "-q")
    real = " ".join(phases[1]["arguments"])
    assert "run-real-batch-suite.ps1" in real
    assert "PRN" not in real.upper()


def test_full_test_button_and_result_live_in_developer_menu(tmp_path):
    owner = window(tmp_path / "prefs.ini")
    assert owner.full_test_button.text() == "完整测试"
    assert owner.full_test_result.text() == "完整测试：尚未运行"
    assert not owner.full_test_button.isVisible()

    owner.developer_mode_checkbox.setChecked(True)
    APP.processEvents()

    assert owner.full_test_button.isVisible()
    assert owner.full_test_result.isVisible()
    assert owner.developer_tools_panel.isAncestorOf(owner.full_test_button)
    assert owner.grab().save(str(tmp_path / "full-test-developer-menu.png"))
    owner.close()


def test_full_test_summary_shows_automated_and_real_counts():
    assert phase_summary("automated", "1216 passed, 2 skipped") == "自动 1216项"
    assert phase_summary("automated", "7 failed, 1216 passed, 1 error") == (
        "自动 1216项 失败7 错误1"
    )
    assert phase_summary("real_batches", '{"total": 11, "passed": 11}') == (
        "真实批次 11/11"
    )


def test_real_batch_summary_reads_the_written_suite_result(tmp_path):
    summary = tmp_path / "suite-summary.json"
    summary.write_text('{"total": 11, "passed": 11, "failed": 0}', encoding="utf-8")
    assert real_batch_file_summary(summary) == "真实批次 11/11"
