from dataclasses import replace

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.history.layout_settings import (
    load_layout_settings,
    save_layout_settings,
)
from automatic_print.layout_engine import LayoutSettings


APP = QApplication.instance() or QApplication([])


def test_complete_local_settings_snapshot_round_trips(tmp_path):
    preferences = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    expected = LayoutSettings(
        cutter_mode="single",
        media_width_mm=430,
        fixed_output_width_mm=430,
        cutter_auto_knife=False,
        force_small_pair_sizes=("M", "XL"),
        machine_number="M7",
        platform_name="Haloo",
        strict_fixed_knife=True,
        order_side_shared_knife=True,
        sequence_numbers=(("source.png", 9),),
    )

    save_layout_settings(preferences, expected)
    actual = load_layout_settings(preferences)

    assert actual == replace(
        expected,
        strict_fixed_knife=False,
        order_side_shared_knife=False,
        sequence_numbers=(),
        platform_name="Haloo",
    )


def test_legacy_local_cutter_mode_overrides_remote_fallback(tmp_path):
    preferences = QSettings(str(tmp_path / "legacy.ini"), QSettings.IniFormat)
    preferences.setValue("cutter/mode", "free")
    preferences.setValue("cutter/film_mm", 600)
    preferences.setValue("riin/left_mm", 15)
    preferences.setValue("riin/right_mm", 15)
    preferences.setValue("layout/machine_number", "m8")

    actual = load_layout_settings(
        preferences,
        LayoutSettings(cutter_mode="dual", dpi=200, machine_number="M1"),
    )

    assert actual.cutter_mode == "free"
    assert actual.media_width_mm == actual.fixed_output_width_mm == 570
    assert actual.dpi == 200
    assert actual.machine_number == "M8"


def test_corrupt_snapshot_falls_back_to_local_cutter_preferences(tmp_path):
    preferences = QSettings(str(tmp_path / "corrupt.ini"), QSettings.IniFormat)
    preferences.setValue("layout/settings_snapshot_v1", "{broken")
    preferences.setValue("cutter/mode", "single")

    actual = load_layout_settings(
        preferences, LayoutSettings(cutter_mode="dual", dpi=240),
    )

    assert actual.cutter_mode == "single"
    assert actual.dpi == 240


def test_main_window_save_updates_snapshot_used_by_automation(tmp_path):
    from automatic_print.ui.main_window import MainWindow

    preferences = QSettings(str(tmp_path / "window.ini"), QSettings.IniFormat)
    window = MainWindow(preferences)
    window.startup_update_timer.stop()
    window.cutter_settings.mode.setCurrentIndex(
        window.cutter_settings.mode.findData("single")
    )
    window.dpi.setValue(360)

    window.save_layout_preferences(notify=False)
    actual = load_layout_settings(preferences)

    assert actual.cutter_mode == "single"
    assert actual.dpi == 360
    window.close()
