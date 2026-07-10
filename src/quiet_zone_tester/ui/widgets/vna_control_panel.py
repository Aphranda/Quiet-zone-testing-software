from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from quiet_zone_tester.models import DEFAULT_FREQUENCY_STEP_MHZ, calculate_sweep_points


DEFAULT_START_GHZ = 10.0
DEFAULT_STOP_GHZ = 17.0
DEFAULT_IF_BANDWIDTH_HZ = 1000.0


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class VnaControlPanel(QGroupBox):
    configure_requested = Signal(dict)
    sample_requested = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__("网分仪配置与采样", parent)
        self._busy = False
        self._connected = False

        self._start_ghz = self._frequency_spinbox(DEFAULT_START_GHZ)
        self._stop_ghz = self._frequency_spinbox(DEFAULT_STOP_GHZ)
        self._frequency_step_mhz = self._frequency_step_spinbox(DEFAULT_FREQUENCY_STEP_MHZ)
        self._sweep_points_label = QLabel()
        self._power_dbm = self._power_spinbox(-10.0)
        self._if_bandwidth_hz = self._if_bandwidth_spinbox(DEFAULT_IF_BANDWIDTH_HZ)
        self._parameter = NoWheelComboBox()
        self._parameter.addItems(["S21", "S11", "S12", "S22"])

        self._configure_button = QPushButton("配置")
        self._configure_button.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self._configure_button.clicked.connect(lambda: self.configure_requested.emit(self.current_settings()))

        self._sample_button = QPushButton("采样")
        self._sample_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self._sample_button.clicked.connect(lambda: self.sample_requested.emit(self.current_settings()))
        self._start_ghz.valueChanged.connect(lambda _value: self._refresh_sweep_points_display())
        self._stop_ghz.valueChanged.connect(lambda _value: self._refresh_sweep_points_display())
        self._frequency_step_mhz.valueChanged.connect(lambda _value: self._refresh_sweep_points_display())

        self._input_widgets: list[QWidget] = [
            self._start_ghz,
            self._stop_ghz,
            self._frequency_step_mhz,
            self._power_dbm,
            self._if_bandwidth_hz,
            self._parameter,
            self._configure_button,
            self._sample_button,
        ]

        form_group = QGroupBox("扫频设置")
        form = QFormLayout(form_group)
        form.addRow("起止频率", self._build_frequency_range_field())
        form.addRow("频率步进/点数", self._build_sweep_resolution_field())
        form.addRow("输出功率", self._power_dbm)
        form.addRow("中频带宽", self._if_bandwidth_hz)
        form.addRow("S 参数", self._parameter)

        layout = QVBoxLayout(self)
        layout.addWidget(form_group)
        button_row = QHBoxLayout()
        button_row.addWidget(self._configure_button)
        button_row.addWidget(self._sample_button)
        layout.addLayout(button_row)
        layout.addStretch(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._refresh_sweep_points_display()
        self._refresh_enabled_state()

    def current_settings(self) -> dict:
        return {
            "start_ghz": self._start_ghz.value(),
            "stop_ghz": self._stop_ghz.value(),
            "frequency_step_mhz": self._frequency_step_mhz.value(),
            "points": self._sweep_points(),
            "vna_power_dbm": self._power_dbm.value(),
            "if_bandwidth_hz": self._if_bandwidth_hz.value(),
            "parameter": self._parameter.currentText(),
        }

    def set_vna_connected(self, connected: bool) -> None:
        self._connected = connected
        self._refresh_enabled_state()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh_enabled_state()

    def _refresh_enabled_state(self) -> None:
        enabled = self._connected and not self._busy
        for widget in self._input_widgets:
            widget.setEnabled(enabled)

    def _sweep_points(self) -> int:
        return calculate_sweep_points(
            self._start_ghz.value(),
            self._stop_ghz.value(),
            self._frequency_step_mhz.value(),
        )

    def _refresh_sweep_points_display(self) -> None:
        self._sweep_points_label.setText(f"{self._sweep_points()} 点")

    def _build_frequency_range_field(self) -> QWidget:
        field = QWidget()
        layout = QHBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._start_ghz, 1)
        separator = QLabel("到")
        separator.setStyleSheet("color: #475467;")
        layout.addWidget(separator, 0)
        layout.addWidget(self._stop_ghz, 1)
        return field

    def _build_sweep_resolution_field(self) -> QWidget:
        field = QWidget()
        layout = QHBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._frequency_step_mhz, 1)
        self._sweep_points_label.setMinimumWidth(72)
        layout.addWidget(self._sweep_points_label, 0)
        return field

    @staticmethod
    def _frequency_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(0.001, 110.0)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(0.1)
        spinbox.setValue(value)
        spinbox.setSuffix(" GHz")
        spinbox.setMinimumWidth(140)
        return spinbox

    @staticmethod
    def _frequency_step_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(0.001, 1000000.0)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(1.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" MHz")
        spinbox.setMinimumWidth(140)
        return spinbox

    @staticmethod
    def _power_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(-90.0, 30.0)
        spinbox.setDecimals(1)
        spinbox.setSingleStep(1.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" dBm")
        spinbox.setMinimumWidth(140)
        return spinbox

    @staticmethod
    def _if_bandwidth_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(1.0, 10000000.0)
        spinbox.setDecimals(0)
        spinbox.setSingleStep(100.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" Hz")
        spinbox.setMinimumWidth(140)
        return spinbox
