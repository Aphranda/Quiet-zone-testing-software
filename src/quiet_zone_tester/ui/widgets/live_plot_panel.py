from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QTabWidget, QVBoxLayout

from quiet_zone_tester.models import SParameterTrace


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class LivePlotPanel(QGroupBox):
    def __init__(self, parent=None) -> None:
        super().__init__("实时曲线", parent)
        self._trace: SParameterTrace | None = None

        self._polarization = NoWheelComboBox()
        self._polarization.addItems(["H", "V"])
        self._position_mark = NoWheelComboBox()
        self._position_mark.addItems(["L", "M", "R", "U", "D"])
        self._position_mark.setCurrentText("M")
        self._main_line = NoWheelComboBox()
        self._main_line.addItems(["X", "Y"])

        self._tabs = QTabWidget()
        self._magnitude_plot = pg.PlotWidget()
        self._phase_plot = pg.PlotWidget()
        self._magnitude_curve = self._magnitude_plot.plot(pen=pg.mkPen("#1769aa", width=2))
        self._phase_curve = self._phase_plot.plot(pen=pg.mkPen("#2e7d32", width=2))

        self._configure_plot(self._magnitude_plot, "频率 (GHz)", "幅度 (dB)")
        self._configure_plot(self._phase_plot, "频率 (GHz)", "相位 (deg)")

        self._tabs.addTab(self._magnitude_plot, "幅度")
        self._tabs.addTab(self._phase_plot, "相位")

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addStretch(1)
        header.addWidget(QLabel("FLAG"))
        header.addWidget(QLabel("极化"))
        header.addWidget(self._polarization)
        header.addWidget(QLabel("主线条"))
        header.addWidget(self._main_line)
        header.addWidget(QLabel("位置"))
        header.addWidget(self._position_mark)
        layout.addLayout(header)
        layout.addWidget(self._tabs)

    def file_flag(self) -> str:
        return "-".join(
            (
                self._polarization.currentText().strip(),
                self._main_line.currentText().strip(),
                self._position_mark.currentText().strip(),
            )
        )

    def set_polarization_from_link(self, command: str, parameter: str = "") -> None:
        polarization = self._polarization_from_link_command(command)
        if polarization is None:
            polarization = self._polarization_from_link_command(parameter)
        if polarization is None:
            polarization = self._polarization_from_parameter(parameter)
        if polarization is not None:
            self._polarization.setCurrentText(polarization)

    def set_polarization_from_parameter(self, parameter: str) -> None:
        polarization = self._polarization_from_parameter(parameter)
        if polarization is not None:
            self._polarization.setCurrentText(polarization)

    def set_main_line_from_scan_settings(self, settings: dict) -> None:
        try:
            x_start = float(settings["x_start_mm"])
            x_stop = float(settings["x_stop_mm"])
            y_start = float(settings["y_start_mm"])
            y_stop = float(settings["y_stop_mm"])
        except (KeyError, TypeError, ValueError):
            return

        x_fixed = abs(x_start - x_stop) <= 1e-9
        y_fixed = abs(y_start - y_stop) <= 1e-9
        if x_fixed and not y_fixed:
            self._main_line.setCurrentText("Y")
        elif y_fixed and not x_fixed:
            self._main_line.setCurrentText("X")

    def set_trace(self, trace: SParameterTrace) -> None:
        self._trace = trace
        self._magnitude_plot.setTitle(f"{trace.parameter} Magnitude")
        self._phase_plot.setTitle(f"{trace.parameter} Phase")
        self._magnitude_curve.setData(
            trace.frequency_ghz,
            trace.magnitude_db,
        )
        self._phase_curve.setData(
            trace.frequency_ghz,
            trace.phase_deg,
        )

    def clear(self) -> None:
        self._trace = None
        self._magnitude_curve.clear()
        self._phase_curve.clear()

    @staticmethod
    def _configure_plot(plot: pg.PlotWidget, bottom_label: str, left_label: str) -> None:
        plot.setBackground("w")
        plot.showGrid(x=True, y=True, alpha=0.25)
        plot.setLabel("bottom", bottom_label)
        plot.setLabel("left", left_label)

    @staticmethod
    def _polarization_from_link_command(command: str) -> str | None:
        normalized = str(command or "").upper().replace(",", " ")
        tokens = [token.strip() for token in normalized.split()]
        if "H" in tokens:
            return "H"
        if "V" in tokens:
            return "V"
        return None

    @staticmethod
    def _polarization_from_parameter(parameter: str) -> str | None:
        parameter = str(parameter or "").strip().upper()
        if parameter in {"S11", "S21"}:
            return "H"
        if parameter in {"S12", "S22"}:
            return "V"
        return None
