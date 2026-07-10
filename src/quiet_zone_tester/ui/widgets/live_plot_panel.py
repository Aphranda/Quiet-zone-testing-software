from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout

from quiet_zone_tester.models import SParameterTrace


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class LivePlotPanel(QGroupBox):
    polarization_changed = Signal(str)
    dut_path_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("实时曲线", parent)
        self._trace: SParameterTrace | None = None

        self._polarization = NoWheelComboBox()
        self._polarization.addItems(["H", "V"])
        self._polarization.currentTextChanged.connect(self.polarization_changed.emit)
        self._position_mark = NoWheelComboBox()
        self._position_mark.addItems(["L", "M", "R", "U", "D"])
        self._position_mark.setCurrentText("M")
        self._main_line = NoWheelComboBox()
        self._main_line.addItems(["X", "Y"])
        self._dut_vna_button = QPushButton("网分")
        self._dut_vna_button.setObjectName("dutPathButton")
        self._dut_vna_button.setCheckable(True)
        self._dut_vna_button.setChecked(True)
        self._dut_sa_button = QPushButton("信号源+频谱")
        self._dut_sa_button.setObjectName("dutPathButton")
        self._dut_sa_button.setCheckable(True)
        self._dut_path_buttons = QButtonGroup(self)
        self._dut_path_buttons.setExclusive(True)
        self._dut_path_buttons.addButton(self._dut_vna_button)
        self._dut_path_buttons.addButton(self._dut_sa_button)
        self._dut_vna_button.clicked.connect(lambda _checked=False: self.dut_path_requested.emit("VNA2"))
        self._dut_sa_button.clicked.connect(lambda _checked=False: self.dut_path_requested.emit("SA"))

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
        header.addWidget(QLabel("DUT"))
        header.addWidget(self._dut_vna_button)
        header.addWidget(self._dut_sa_button)
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

    def polarization(self) -> str:
        return self._polarization.currentText().strip().upper()

    def set_main_line_from_scan_settings(self, settings: dict) -> None:
        try:
            x_start = float(settings["x_start_mm"])
            x_stop = float(settings["x_stop_mm"])
            y_start = float(settings["y_start_mm"])
            y_stop = float(settings["y_stop_mm"])
        except (KeyError, TypeError, ValueError):
            return

        x_moving = abs(x_start - x_stop) > 1e-9
        y_moving = abs(y_start - y_stop) > 1e-9
        if x_moving:
            self._main_line.setCurrentText("X")
            if y_moving:
                self._position_mark.setCurrentText("M")
            else:
                self._position_mark.setCurrentText(self._x_line_position_mark(y_start, x_start, x_stop, y_start, y_stop))
        elif y_moving:
            self._main_line.setCurrentText("Y")
            self._position_mark.setCurrentText(self._y_line_position_mark(x_start, x_start, x_stop, y_start, y_stop))
        else:
            self._position_mark.setCurrentText("M")

    @classmethod
    def _x_line_position_mark(
        cls,
        y_mm: float,
        x_start_mm: float,
        x_stop_mm: float,
        y_start_mm: float,
        y_stop_mm: float,
    ) -> str:
        return cls._position_mark_by_quarter(
            value_mm=y_mm,
            x_start_mm=x_start_mm,
            x_stop_mm=x_stop_mm,
            y_start_mm=y_start_mm,
            y_stop_mm=y_stop_mm,
            low_mark="R",
            high_mark="L",
        )

    @classmethod
    def _y_line_position_mark(
        cls,
        x_mm: float,
        x_start_mm: float,
        x_stop_mm: float,
        y_start_mm: float,
        y_stop_mm: float,
    ) -> str:
        return cls._position_mark_by_quarter(
            value_mm=x_mm,
            x_start_mm=x_start_mm,
            x_stop_mm=x_stop_mm,
            y_start_mm=y_start_mm,
            y_stop_mm=y_stop_mm,
            low_mark="U",
            high_mark="D",
        )

    @classmethod
    def _position_mark_by_quarter(
        cls,
        value_mm: float,
        x_start_mm: float,
        x_stop_mm: float,
        y_start_mm: float,
        y_stop_mm: float,
        low_mark: str,
        high_mark: str,
    ) -> str:
        view_limit = cls._view_limit_mm(x_start_mm, x_stop_mm, y_start_mm, y_stop_mm)
        if value_mm <= view_limit * 0.25:
            return low_mark
        if value_mm >= view_limit * 0.75:
            return high_mark
        return "M"

    @staticmethod
    def _view_limit_mm(x_start_mm: float, x_stop_mm: float, y_start_mm: float, y_stop_mm: float) -> float:
        return max(x_start_mm, x_stop_mm, y_start_mm, y_stop_mm, 1.0)

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
