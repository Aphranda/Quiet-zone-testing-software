import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quiet_zone_tester.ui.widgets.live_plot_panel import LivePlotPanel


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class LivePlotPanelTest(unittest.TestCase):
    def test_polarization_and_dut_controls_emit_independent_link_requests(self) -> None:
        _app()
        panel = LivePlotPanel()
        polarizations: list[str] = []
        dut_targets: list[str] = []
        panel.polarization_changed.connect(polarizations.append)
        panel.dut_path_requested.connect(dut_targets.append)

        panel._polarization.setCurrentText("V")
        panel._dut_sa_button.click()
        panel._dut_vna_button.click()

        self.assertEqual(polarizations, ["V"])
        self.assertEqual(dut_targets, ["SA", "VNA2"])
        self.assertEqual(panel.polarization(), "V")

    def test_file_flag_uses_current_polarization_line_and_position(self) -> None:
        _app()
        panel = LivePlotPanel()

        panel._polarization.setCurrentText("V")
        panel._main_line.setCurrentText("Y")
        panel._position_mark.setCurrentText("R")

        self.assertEqual(panel.file_flag(), "V-Y-R")

    def test_main_line_tracks_fixed_x_scan_range(self) -> None:
        _app()
        panel = LivePlotPanel()

        panel._main_line.setCurrentText("X")
        panel.set_main_line_from_scan_settings(
            {
                "x_start_mm": 100.0,
                "x_stop_mm": 100.0,
                "y_start_mm": 0.0,
                "y_stop_mm": 400.0,
            }
        )

        self.assertEqual(panel._main_line.currentText(), "Y")
        self.assertEqual(panel._position_mark.currentText(), "U")

    def test_main_line_tracks_fixed_y_scan_range(self) -> None:
        _app()
        panel = LivePlotPanel()

        panel._main_line.setCurrentText("Y")
        panel.set_main_line_from_scan_settings(
            {
                "x_start_mm": 0.0,
                "x_stop_mm": 400.0,
                "y_start_mm": 100.0,
                "y_stop_mm": 100.0,
            }
        )

        self.assertEqual(panel._main_line.currentText(), "X")
        self.assertEqual(panel._position_mark.currentText(), "R")

    def test_position_mark_uses_quarter_boundaries(self) -> None:
        _app()
        panel = LivePlotPanel()

        panel.set_main_line_from_scan_settings(
            {
                "x_start_mm": 0.0,
                "x_stop_mm": 400.0,
                "y_start_mm": 101.0,
                "y_stop_mm": 101.0,
            }
        )
        self.assertEqual(panel._main_line.currentText(), "X")
        self.assertEqual(panel._position_mark.currentText(), "M")

        panel.set_main_line_from_scan_settings(
            {
                "x_start_mm": 0.0,
                "x_stop_mm": 400.0,
                "y_start_mm": 300.0,
                "y_stop_mm": 300.0,
            }
        )
        self.assertEqual(panel._position_mark.currentText(), "L")

    def test_main_line_tracks_first_scan_direction_when_both_axes_move(self) -> None:
        _app()
        panel = LivePlotPanel()

        panel._main_line.setCurrentText("Y")
        panel.set_main_line_from_scan_settings(
            {
                "x_start_mm": 0.0,
                "x_stop_mm": 400.0,
                "y_start_mm": 0.0,
                "y_stop_mm": 400.0,
            }
        )

        self.assertEqual(panel._main_line.currentText(), "X")
        self.assertEqual(panel._position_mark.currentText(), "M")

    def test_position_mark_tracks_middle_line(self) -> None:
        _app()
        panel = LivePlotPanel()

        panel._position_mark.setCurrentText("L")
        panel.set_main_line_from_scan_settings(
            {
                "x_start_mm": 0.0,
                "x_stop_mm": 400.0,
                "y_start_mm": 200.0,
                "y_stop_mm": 200.0,
            }
        )

        self.assertEqual(panel._main_line.currentText(), "X")
        self.assertEqual(panel._position_mark.currentText(), "M")

    def test_position_mark_tracks_left_and_down_lines(self) -> None:
        _app()
        panel = LivePlotPanel()

        panel.set_main_line_from_scan_settings(
            {
                "x_start_mm": 0.0,
                "x_stop_mm": 400.0,
                "y_start_mm": 400.0,
                "y_stop_mm": 400.0,
            }
        )
        self.assertEqual(panel._main_line.currentText(), "X")
        self.assertEqual(panel._position_mark.currentText(), "L")

        panel.set_main_line_from_scan_settings(
            {
                "x_start_mm": 400.0,
                "x_stop_mm": 400.0,
                "y_start_mm": 0.0,
                "y_stop_mm": 400.0,
            }
        )
        self.assertEqual(panel._main_line.currentText(), "Y")
        self.assertEqual(panel._position_mark.currentText(), "D")


if __name__ == "__main__":
    unittest.main()
