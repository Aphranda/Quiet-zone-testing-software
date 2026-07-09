import os
import unittest
from dataclasses import dataclass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from quiet_zone_tester.presentation.modules.motion_control import MotionControlViewModel
from quiet_zone_tester.ui.widgets.positioner_control_panel import PositionerControlPanel


@dataclass(frozen=True)
class _Position:
    x_mm: float
    y_mm: float


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class MotionControlViewModelTest(unittest.TestCase):
    def test_absolute_and_relative_commands_keep_legacy_dict_shape(self) -> None:
        view_model = MotionControlViewModel()

        self.assertEqual(
            view_model.absolute_move_command(x_mm=1.0, y_mm=2.5, speed_mm_s=10.0),
            {"x_mm": 1.0, "y_mm": 2.5, "speed_mm_s": 10.0},
        )
        self.assertEqual(
            view_model.relative_move_command(delta_x_mm=-1.0, delta_y_mm=3.0, speed_mm_s=5.0),
            {"delta_x_mm": -1.0, "delta_y_mm": 3.0, "speed_mm_s": 5.0},
        )

    def test_commands_reject_non_positive_speed(self) -> None:
        view_model = MotionControlViewModel()

        with self.assertRaises(ValueError):
            view_model.absolute_move_command(x_mm=0.0, y_mm=0.0, speed_mm_s=0.0)
        with self.assertRaises(ValueError):
            view_model.relative_move_command(delta_x_mm=0.0, delta_y_mm=0.0, speed_mm_s=-1.0)

    def test_position_display_and_ui_state(self) -> None:
        view_model = MotionControlViewModel()

        self.assertEqual(view_model.position_display(None).x_text, "-")
        self.assertEqual(view_model.position_display(_Position(1.23456, -2.0)).x_text, "1.235 mm")
        self.assertEqual(view_model.position_display(_Position(1.23456, -2.0)).y_text, "-2.000 mm")
        self.assertTrue(view_model.ui_state(connected=True, busy=False).actions_enabled)
        self.assertFalse(view_model.ui_state(connected=True, busy=True).actions_enabled)
        self.assertFalse(view_model.ui_state(connected=False, busy=False).stop_enabled)

    def test_positioner_control_panel_uses_legacy_signal_payloads(self) -> None:
        _app()
        panel = PositionerControlPanel()
        absolute_payloads: list[dict] = []
        relative_payloads: list[dict] = []
        panel.absolute_move_requested.connect(absolute_payloads.append)
        panel.relative_move_requested.connect(relative_payloads.append)

        panel._absolute_x_mm.setValue(12.0)
        panel._absolute_y_mm.setValue(34.0)
        panel._absolute_speed_mm_s.setValue(56.0)
        panel._relative_x_mm.setValue(-1.5)
        panel._relative_y_mm.setValue(2.5)
        panel._relative_speed_mm_s.setValue(7.5)

        panel._emit_absolute_move()
        panel._emit_relative_move()

        self.assertEqual(absolute_payloads[0], {"x_mm": 12.0, "y_mm": 34.0, "speed_mm_s": 56.0})
        self.assertEqual(relative_payloads[0], {"delta_x_mm": -1.5, "delta_y_mm": 2.5, "speed_mm_s": 7.5})

    def test_positioner_control_panel_updates_position_labels(self) -> None:
        _app()
        panel = PositionerControlPanel()

        panel.set_current_position(_Position(1.0, 2.0))

        texts = [label.text() for label in panel.findChildren(QLabel)]
        self.assertIn("1.000 mm", texts)
        self.assertIn("2.000 mm", texts)


if __name__ == "__main__":
    unittest.main()
