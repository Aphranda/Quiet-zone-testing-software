from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from quiet_zone_tester.hardware import Position
from quiet_zone_tester.presentation.modules.motion_control import MotionControlViewModel


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class PositionerControlPanel(QGroupBox):
    query_position_requested = Signal()
    absolute_move_requested = Signal(dict)
    relative_move_requested = Signal(dict)
    stop_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("扫描架控制", parent)
        self._view_model = MotionControlViewModel()
        self._busy = False
        self._connected = False

        self._x_position_value = QLabel("-")
        self._y_position_value = QLabel("-")

        self._absolute_x_mm = self._position_spinbox(0.0)
        self._absolute_y_mm = self._position_spinbox(0.0)
        self._absolute_speed_mm_s = self._speed_spinbox(100.0)

        self._relative_x_mm = self._relative_spinbox(0.0)
        self._relative_y_mm = self._relative_spinbox(0.0)
        self._relative_speed_mm_s = self._speed_spinbox(100.0)

        self._query_button = QPushButton("查询当前位置")
        self._query_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self._query_button.clicked.connect(self.query_position_requested)

        self._absolute_move_button = QPushButton("绝对定位")
        self._absolute_move_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self._absolute_move_button.clicked.connect(self._emit_absolute_move)

        self._relative_move_button = QPushButton("相对定位")
        self._relative_move_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self._relative_move_button.clicked.connect(self._emit_relative_move)

        self._stop_button = QPushButton("停止")
        self._stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self._stop_button.setStyleSheet(
            """
            QPushButton {
                background: #d92d20;
                color: white;
                border: 1px solid #b42318;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #b42318;
            }
            QPushButton:disabled {
                background: #e4e7ec;
                color: #98a2b3;
                border: 1px solid #d0d5dd;
            }
            """
        )
        self._stop_button.clicked.connect(self.stop_requested)

        self._action_widgets: list[QWidget] = [
            self._query_button,
            self._absolute_x_mm,
            self._absolute_y_mm,
            self._absolute_speed_mm_s,
            self._absolute_move_button,
            self._relative_x_mm,
            self._relative_y_mm,
            self._relative_speed_mm_s,
            self._relative_move_button,
        ]

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_position_group())
        layout.addWidget(self._build_absolute_group())
        layout.addWidget(self._build_relative_group())
        layout.addWidget(self._stop_button)
        layout.addStretch(1)

        self._refresh_enabled_state()

    def set_positioner_connected(self, connected: bool) -> None:
        self._connected = connected
        if not connected:
            self._set_position_display(None)
        self._refresh_enabled_state()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh_enabled_state()

    def set_position(self, position: Position) -> None:
        self.set_current_position(position)
        self._absolute_x_mm.setValue(position.x_mm)
        self._absolute_y_mm.setValue(position.y_mm)

    def set_current_position(self, position: Position) -> None:
        self._set_position_display(position)

    def _set_position_display(self, position: Position | None) -> None:
        display = self._view_model.position_display(position)
        self._x_position_value.setText(display.x_text)
        self._y_position_value.setText(display.y_text)

    def _build_position_group(self) -> QGroupBox:
        group = QGroupBox("当前位置")
        form = QFormLayout(group)
        form.addRow("X", self._x_position_value)
        form.addRow("Y", self._y_position_value)
        form.addRow("", self._query_button)
        return group

    def _build_absolute_group(self) -> QGroupBox:
        group = QGroupBox("绝对定位")
        grid = QGridLayout(group)
        grid.addWidget(QLabel("X"), 0, 0)
        grid.addWidget(self._absolute_x_mm, 0, 1)
        grid.addWidget(QLabel("Y"), 1, 0)
        grid.addWidget(self._absolute_y_mm, 1, 1)
        grid.addWidget(QLabel("速度"), 2, 0)
        grid.addWidget(self._absolute_speed_mm_s, 2, 1)
        grid.addWidget(self._absolute_move_button, 3, 0, 1, 2)
        grid.setColumnStretch(1, 1)
        return group

    def _build_relative_group(self) -> QGroupBox:
        group = QGroupBox("相对定位")
        grid = QGridLayout(group)
        grid.addWidget(QLabel("ΔX"), 0, 0)
        grid.addWidget(self._relative_x_mm, 0, 1)
        grid.addWidget(QLabel("ΔY"), 1, 0)
        grid.addWidget(self._relative_y_mm, 1, 1)
        grid.addWidget(QLabel("速度"), 2, 0)
        grid.addWidget(self._relative_speed_mm_s, 2, 1)
        grid.addWidget(self._relative_move_button, 3, 0, 1, 2)
        grid.setColumnStretch(1, 1)
        return group

    def _emit_absolute_move(self) -> None:
        self.absolute_move_requested.emit(
            self._view_model.absolute_move_command(
                x_mm=self._absolute_x_mm.value(),
                y_mm=self._absolute_y_mm.value(),
                speed_mm_s=self._absolute_speed_mm_s.value(),
            )
        )

    def _emit_relative_move(self) -> None:
        self.relative_move_requested.emit(
            self._view_model.relative_move_command(
                delta_x_mm=self._relative_x_mm.value(),
                delta_y_mm=self._relative_y_mm.value(),
                speed_mm_s=self._relative_speed_mm_s.value(),
            )
        )

    def _refresh_enabled_state(self) -> None:
        state = self._view_model.ui_state(connected=self._connected, busy=self._busy)
        for widget in self._action_widgets:
            widget.setEnabled(state.actions_enabled)
        self._stop_button.setEnabled(state.stop_enabled)

    @staticmethod
    def _position_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(-1000000.0, 1000000.0)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(1.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" mm")
        spinbox.setMinimumWidth(120)
        return spinbox

    @staticmethod
    def _relative_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = PositionerControlPanel._position_spinbox(value)
        spinbox.setSingleStep(0.5)
        return spinbox

    @staticmethod
    def _speed_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(0.001, 1000000.0)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(10.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" mm/s")
        spinbox.setMinimumWidth(120)
        return spinbox
