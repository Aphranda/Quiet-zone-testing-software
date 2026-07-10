from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout

from quiet_zone_tester.models import SParameterTrace
from quiet_zone_tester.presentation.modules.scan_runtime import ScanFlagModel


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
        header.addWidget(QLabel("标签"))
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
        flag_state = ScanFlagModel.from_scan_settings(settings)
        if flag_state is None:
            return

        if flag_state.main_line is not None:
            self._main_line.setCurrentText(flag_state.main_line)
        self._position_mark.setCurrentText(flag_state.position_mark)

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
