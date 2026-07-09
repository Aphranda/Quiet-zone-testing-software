from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)


DEFAULT_START_GHZ = 10.0
DEFAULT_STOP_GHZ = 17.0
DEFAULT_IF_BANDWIDTH_HZ = 1000.0


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class NoWheelSpinBox(QSpinBox):
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
        self._points = self._points_spinbox(801)
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

        self._input_widgets: list[QWidget] = [
            self._start_ghz,
            self._stop_ghz,
            self._points,
            self._power_dbm,
            self._if_bandwidth_hz,
            self._parameter,
            self._configure_button,
            self._sample_button,
        ]

        form_group = QGroupBox("扫频设置")
        form = QFormLayout(form_group)
        form.addRow("起始频率", self._start_ghz)
        form.addRow("终止频率", self._stop_ghz)
        form.addRow("扫描点数", self._points)
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
        self._refresh_enabled_state()

    def current_settings(self) -> dict:
        return {
            "start_ghz": self._start_ghz.value(),
            "stop_ghz": self._stop_ghz.value(),
            "points": self._points.value(),
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
    def _points_spinbox(value: int) -> QSpinBox:
        spinbox = NoWheelSpinBox()
        spinbox.setRange(2, 1000000)
        spinbox.setSingleStep(10)
        spinbox.setValue(value)
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
