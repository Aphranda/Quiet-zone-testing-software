import unittest

from quiet_zone_tester.presentation.modules.scan_runtime import ScanFlagModel, ScanFlagState


class ScanFlagModelTest(unittest.TestCase):
    def test_x_line_uses_actual_non_zero_bounds_for_position_mark(self) -> None:
        state = ScanFlagModel.from_scan_settings(
            {
                "x_start_mm": 100.0,
                "x_stop_mm": 500.0,
                "y_start_mm": 300.0,
                "y_stop_mm": 300.0,
            }
        )

        self.assertEqual(state, ScanFlagState(main_line="X", position_mark="M"))

    def test_x_line_marks_high_quarter_as_left_with_non_zero_bounds(self) -> None:
        state = ScanFlagModel.from_scan_settings(
            {
                "x_start_mm": 100.0,
                "x_stop_mm": 500.0,
                "y_start_mm": 400.0,
                "y_stop_mm": 400.0,
            }
        )

        self.assertEqual(state, ScanFlagState(main_line="X", position_mark="L"))

    def test_y_line_uses_actual_non_zero_bounds_for_position_mark(self) -> None:
        state = ScanFlagModel.from_scan_settings(
            {
                "x_start_mm": 200.0,
                "x_stop_mm": 200.0,
                "y_start_mm": 100.0,
                "y_stop_mm": 500.0,
            }
        )

        self.assertEqual(state, ScanFlagState(main_line="Y", position_mark="U"))

    def test_both_axes_move_uses_x_main_line_and_middle_mark(self) -> None:
        state = ScanFlagModel.from_scan_settings(
            {
                "x_start_mm": 100.0,
                "x_stop_mm": 500.0,
                "y_start_mm": 100.0,
                "y_stop_mm": 500.0,
            }
        )

        self.assertEqual(state, ScanFlagState(main_line="X", position_mark="M"))

    def test_invalid_settings_return_none(self) -> None:
        self.assertIsNone(ScanFlagModel.from_scan_settings({"x_start_mm": "bad"}))


if __name__ == "__main__":
    unittest.main()
