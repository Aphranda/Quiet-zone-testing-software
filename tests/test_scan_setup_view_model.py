import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quiet_zone_tester.presentation.modules.scan_setup import (
    DEFAULT_DISTANCE_PER_TURN_MM,
    DEFAULT_FREQUENCY_STEP_MHZ,
    DEFAULT_SETTLE_DELAY_S,
    DEFAULT_STEP_MM,
    ProbeOffsetPreset,
    ScanSetupFormState,
    ScanSetupViewModel,
)
from quiet_zone_tester.ui.widgets.test_setup_panel import TestSetupPanel


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _state(scan_mode: str = "step") -> ScanSetupFormState:
    return ScanSetupFormState(
        start_ghz=10.0,
        stop_ghz=17.0,
        frequency_step_mhz=DEFAULT_FREQUENCY_STEP_MHZ,
        vna_power_dbm=-10.0,
        if_bandwidth_hz=1000.0,
        parameter="S21",
        scan_mode=scan_mode,
        x_start_mm=0.0,
        x_stop_mm=400.0,
        y_start_mm=0.0,
        y_stop_mm=400.0,
        step_x_mm=2.5,
        step_y_mm=2.5,
        step_x_turns=0.25,
        step_y_turns=0.5,
        x_mm_per_turn=24.0,
        y_mm_per_turn=30.0,
        step_speed_mm_s=20.0,
        settle_delay_s=DEFAULT_SETTLE_DELAY_S,
        probe_offset_preset="右上",
        probe_x_offset_mm=-61.5,
        probe_y_offset_mm=-61.5,
        continuous_speed_mm_s=20.0,
    )


class ScanSetupViewModelTest(unittest.TestCase):
    def test_build_step_settings_preserves_legacy_dict_shape(self) -> None:
        settings = ScanSetupViewModel().build_settings(_state("step"))

        self.assertEqual(settings["frequency_step_mhz"], DEFAULT_FREQUENCY_STEP_MHZ)
        self.assertEqual(settings["points"], 71)
        self.assertEqual(settings["parameter"], "S21")
        self.assertEqual(settings["scan_mode"], "step")
        self.assertEqual(settings["step_x_mm"], 2.5)
        self.assertEqual(settings["step_y_mm"], 2.5)
        self.assertEqual(settings["probe_offset_preset"], "右上")

    def test_continuous_mode_uses_mm_per_turn_as_step_distance(self) -> None:
        state = _state("continuous")
        settings = ScanSetupViewModel().build_settings(state)

        self.assertEqual(settings["scan_mode"], "continuous")
        self.assertEqual(settings["step_x_mm"], 24.0)
        self.assertEqual(settings["step_y_mm"], 30.0)

    def test_probe_presets_match_expected_offsets(self) -> None:
        presets = ScanSetupViewModel.probe_offset_presets()

        self.assertIn(ProbeOffsetPreset("自定义", None), presets)
        self.assertIn(ProbeOffsetPreset("右上", (-61.5, -61.5)), presets)
        self.assertIn(ProbeOffsetPreset("左下", (61.5, 61.5)), presets)

    def test_turns_from_step_distance(self) -> None:
        self.assertAlmostEqual(
            ScanSetupViewModel.turns_from_step_distance(DEFAULT_STEP_MM, DEFAULT_DISTANCE_PER_TURN_MM),
            DEFAULT_STEP_MM / DEFAULT_DISTANCE_PER_TURN_MM,
        )

    def test_test_setup_panel_current_settings_still_returns_dict(self) -> None:
        _app()
        panel = TestSetupPanel()

        settings = panel.current_settings()

        self.assertEqual(settings["frequency_step_mhz"], DEFAULT_FREQUENCY_STEP_MHZ)
        self.assertEqual(settings["points"], 71)
        self.assertEqual(settings["scan_mode"], "step")
        self.assertEqual(settings["parameter"], "S21")
        self.assertEqual(settings["step_x_mm"], DEFAULT_STEP_MM)
        self.assertEqual(settings["step_y_mm"], DEFAULT_STEP_MM)
        self.assertEqual(settings["settle_delay_s"], DEFAULT_SETTLE_DELAY_S)
        self.assertEqual(settings["probe_offset_preset"], "右上")
        self.assertEqual(settings["probe_x_offset_mm"], -61.5)
        self.assertEqual(settings["probe_y_offset_mm"], -61.5)


if __name__ == "__main__":
    unittest.main()
