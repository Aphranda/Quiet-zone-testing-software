import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quiet_zone_tester.models import DEFAULT_FREQUENCY_STEP_MHZ
from quiet_zone_tester.ui.widgets.vna_control_panel import VnaControlPanel


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class VnaControlPanelTest(unittest.TestCase):
    def test_current_settings_include_sweep_mode(self) -> None:
        _app()
        panel = VnaControlPanel()

        self.assertEqual(panel.current_settings()["frequency_step_mhz"], DEFAULT_FREQUENCY_STEP_MHZ)
        self.assertFalse(panel.current_settings()["continuous_sweep"])
        self.assertEqual(panel.current_settings()["sweep_mode"], "hold")

        panel._trigger_mode.setCurrentText("Single")

        self.assertFalse(panel.current_settings()["continuous_sweep"])
        self.assertEqual(panel.current_settings()["sweep_mode"], "single")
        self.assertEqual(panel.current_settings()["trigger_mode"], "single")

        panel._trigger_mode.setCurrentText("Continuous")

        self.assertTrue(panel.current_settings()["continuous_sweep"])
        self.assertEqual(panel.current_settings()["sweep_mode"], "continuous")

    def test_sweep_time_can_be_updated_from_configured_instrument_value(self) -> None:
        _app()
        panel = VnaControlPanel()

        panel.set_sweep_time_s(0.123)

        self.assertEqual(panel._sweep_time.text(), "123.0 ms")


if __name__ == "__main__":
    unittest.main()
