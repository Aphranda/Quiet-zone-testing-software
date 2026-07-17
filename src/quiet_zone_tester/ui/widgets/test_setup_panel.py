from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QWidget,
)

from quiet_zone_tester.presentation.modules.scan_setup import (
    DEFAULT_DISTANCE_PER_TURN_MM,
    DEFAULT_FREQUENCY_STEP_MHZ,
    DEFAULT_IF_BANDWIDTH_HZ,
    DEFAULT_MOTION_TIMEOUT_MARGIN_S,
    DEFAULT_PROBE_OFFSET_MM,
    DEFAULT_SETTLE_DELAY_S,
    DEFAULT_START_GHZ,
    DEFAULT_STEP_MM,
    DEFAULT_STEP_SPEED_MM_S,
    DEFAULT_STOP_GHZ,
    ScanSetupFormState,
    ScanSetupViewModel,
)
from quiet_zone_tester.shared.instrument_defaults import MAX_POSITIONER_SPEED_MM_S

MAX_PROBE_OFFSET_MM = 10000.0


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class TestSetupPanel(QGroupBox):
    vna_sample_requested = Signal(dict)
    scan_requested = Signal(dict)
    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()
    config_changed = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__("测试参数", parent)
        self._view_model = ScanSetupViewModel()
        self._busy = False
        self._sampling_active = False
        self._sampling_paused = False

        self._start_ghz = self._frequency_spinbox(DEFAULT_START_GHZ)
        self._stop_ghz = self._frequency_spinbox(DEFAULT_STOP_GHZ)
        self._frequency_step_mhz = self._frequency_step_spinbox(DEFAULT_FREQUENCY_STEP_MHZ)
        self._sweep_points_label = QLabel()
        self._vna_power_dbm = self._power_spinbox(-10.0)
        self._if_bandwidth_hz = self._if_bandwidth_spinbox(DEFAULT_IF_BANDWIDTH_HZ)

        self._parameter = NoWheelComboBox()
        self._parameter.addItems(["S21", "S11", "S12", "S22"])

        self._scan_mode = NoWheelComboBox()
        self._scan_mode.addItem("步进测试", "step")
        self._scan_mode.addItem("匀速测试", "continuous")

        self._x_start_mm = self._coordinate_spinbox(0.0)
        self._x_stop_mm = self._coordinate_spinbox(400.0)
        self._y_start_mm = self._coordinate_spinbox(0.0)
        self._y_stop_mm = self._coordinate_spinbox(400.0)
        self._step_x_mm = self._step_spinbox(DEFAULT_STEP_MM)
        self._step_y_mm = self._step_spinbox(DEFAULT_STEP_MM)
        self._step_x_turns = self._turns_spinbox(DEFAULT_STEP_MM / DEFAULT_DISTANCE_PER_TURN_MM)
        self._step_y_turns = self._turns_spinbox(DEFAULT_STEP_MM / DEFAULT_DISTANCE_PER_TURN_MM)
        self._x_mm_per_turn = self._distance_per_turn_spinbox(DEFAULT_DISTANCE_PER_TURN_MM)
        self._y_mm_per_turn = self._distance_per_turn_spinbox(DEFAULT_DISTANCE_PER_TURN_MM)
        self._step_speed_mm_s = self._speed_spinbox(DEFAULT_STEP_SPEED_MM_S)
        self._settle_delay_s = self._seconds_spinbox(DEFAULT_SETTLE_DELAY_S, 0.0, 120.0)
        self._motion_timeout_margin_s = self._seconds_spinbox(DEFAULT_MOTION_TIMEOUT_MARGIN_S, 0.0, 600.0)
        self._probe_offset_preset = NoWheelComboBox()
        self._populate_probe_offset_presets()
        self._probe_x_offset_mm = self._offset_spinbox(DEFAULT_PROBE_OFFSET_MM)
        self._probe_y_offset_mm = self._offset_spinbox(DEFAULT_PROBE_OFFSET_MM)

        self._continuous_speed_mm_s = self._speed_spinbox(20.0)

        self._input_widgets: list[QWidget] = [
            self._start_ghz,
            self._stop_ghz,
            self._frequency_step_mhz,
            self._vna_power_dbm,
            self._if_bandwidth_hz,
            self._parameter,
            self._scan_mode,
            self._x_start_mm,
            self._x_stop_mm,
            self._y_start_mm,
            self._y_stop_mm,
            self._step_x_mm,
            self._step_y_mm,
            self._step_x_turns,
            self._step_y_turns,
            self._x_mm_per_turn,
            self._y_mm_per_turn,
            self._step_speed_mm_s,
            self._settle_delay_s,
            self._probe_offset_preset,
            self._probe_x_offset_mm,
            self._probe_y_offset_mm,
            self._continuous_speed_mm_s,
        ]

        self._vna_sample_button = QPushButton("曲线采样")
        self._vna_sample_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self._vna_sample_button.clicked.connect(
            lambda: self.vna_sample_requested.emit(self.current_settings())
        )

        self._scan_button = QPushButton("开始测试")
        self._scan_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self._scan_button.clicked.connect(lambda: self.scan_requested.emit(self.current_settings()))

        self._pause_button = QPushButton("暂停")
        self._pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self._pause_button.clicked.connect(self._toggle_pause)

        self._stop_button = QPushButton("停止")
        self._stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self._stop_button.clicked.connect(self.stop_requested)

        layout = QGridLayout(self)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        layout.addWidget(self._build_sweep_group(), 0, 0)
        layout.addWidget(self._build_mode_group(), 0, 1)
        self._volume_group = self._build_volume_group()
        layout.addWidget(self._volume_group, 1, 0, 1, 2)
        layout.addLayout(self._build_action_buttons(), 2, 0, 1, 2)

        self._scan_mode.currentIndexChanged.connect(lambda _index: self._refresh_mode_visibility())
        for widget in (self._step_x_turns, self._step_y_turns, self._x_mm_per_turn, self._y_mm_per_turn):
            widget.valueChanged.connect(lambda _value: self._sync_step_distance_from_turns())
        self._step_x_mm.valueChanged.connect(lambda _value: self._sync_turns_from_step_distance("X"))
        self._step_y_mm.valueChanged.connect(lambda _value: self._sync_turns_from_step_distance("Y"))
        self._probe_offset_preset.currentIndexChanged.connect(lambda _index: self._apply_probe_offset_preset())
        self._connect_config_change_signals()
        self._apply_probe_offset_preset()
        self._refresh_sweep_points_display()
        self._refresh_mode_visibility()
        self._refresh_step_input_mode()
        self._refresh_action_buttons()

    def current_settings(self) -> dict:
        return self._view_model.build_settings(self._form_state())

    def set_positioner_default_speed(self, speed_mm_s: float) -> None:
        self._set_speed_without_noise(self._step_speed_mm_s, speed_mm_s)
        self._set_speed_without_noise(self._continuous_speed_mm_s, speed_mm_s)
        self._emit_config_changed()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh_action_buttons()

    def set_sampling_active(self, active: bool) -> None:
        self._sampling_active = active
        if not active:
            self._sampling_paused = False
        for widget in self._input_widgets:
            widget.setEnabled(not active)
        if not active:
            self._refresh_probe_offset_editability()
        self._refresh_action_buttons()

    def set_sampling_paused(self, paused: bool) -> None:
        self._sampling_paused = paused
        self._refresh_action_buttons()

    def _build_sweep_group(self) -> QGroupBox:
        group = QGroupBox("网分设置")
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.addRow("起止频率", self._build_frequency_range_field())
        form.addRow("频率步进/点数", self._build_sweep_resolution_field())
        form.addRow("网分功率", self._vna_power_dbm)
        form.addRow("中频带宽", self._if_bandwidth_hz)
        form.addRow("S 参数", self._parameter)
        return group

    def _build_mode_group(self) -> QGroupBox:
        group = QGroupBox("扫描模式")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        self._mode_field_labels: dict[QWidget, QLabel] = {}
        self._add_mode_field(grid, 0, 0, "测试模式", self._scan_mode, column_span=3)
        self._add_mode_field(grid, 1, 0, "步进速度", self._step_speed_mm_s)
        self._add_mode_field(grid, 1, 2, "到点延时", self._settle_delay_s)
        self._add_mode_field(grid, 2, 0, "探头位置", self._probe_offset_preset, column_span=3)
        self._add_mode_field(grid, 3, 0, "X偏移", self._probe_x_offset_mm)
        self._add_mode_field(grid, 3, 2, "Y偏移", self._probe_y_offset_mm)
        self._add_mode_field(grid, 4, 0, "匀速速度", self._continuous_speed_mm_s)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        return group

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
        self._sweep_points_label.setMinimumWidth(64)
        layout.addWidget(self._sweep_points_label, 0)
        return field

    def _add_mode_field(
        self,
        grid: QGridLayout,
        row: int,
        column: int,
        label_text: str,
        widget: QWidget,
        column_span: int = 1,
    ) -> None:
        label = QLabel(label_text)
        grid.addWidget(label, row, column)
        grid.addWidget(widget, row, column + 1, 1, column_span)
        self._mode_field_labels[widget] = label

    def _build_volume_group(self) -> QGroupBox:
        group = QGroupBox("静区扫描区间")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self._volume_grid = grid

        headers = ("", "起点", "终点", "换算步进", "步进圈数", "每圈距离")
        self._range_header_labels: list[QLabel] = []
        self._step_header_label: QLabel | None = None
        for column, text in enumerate(headers):
            label = QLabel(text)
            label.setStyleSheet("font-weight: 600; color: #344054;")
            grid.addWidget(label, 0, column)
            self._range_header_labels.append(label)
            if column == 3:
                self._step_header_label = label

        self._continuous_header_labels: list[QLabel] = []
        for column, text in enumerate(("横向起点", "横向终点", "纵向起点", "纵向终点", "横向每圈", "纵向每圈")):
            label = QLabel(text)
            label.setStyleSheet("font-weight: 600; color: #344054;")
            label.setVisible(False)
            grid.addWidget(label, 0, column)
            self._continuous_header_labels.append(label)

        rows = (
            ("X", self._x_start_mm, self._x_stop_mm, self._step_x_mm, self._step_x_turns, self._x_mm_per_turn),
            ("Y", self._y_start_mm, self._y_stop_mm, self._step_y_mm, self._step_y_turns, self._y_mm_per_turn),
        )
        self._axis_labels: list[QLabel] = []
        self._turn_widgets: list[QWidget] = []
        self._distance_per_turn_widgets: list[QWidget] = []
        for row, (axis, start_widget, stop_widget, step_widget, turns_widget, distance_widget) in enumerate(
            rows, start=1
        ):
            axis_label = QLabel(axis)
            axis_label.setStyleSheet("font-weight: 700;")
            grid.addWidget(axis_label, row, 0)
            self._axis_labels.append(axis_label)
            grid.addWidget(start_widget, row, 1)
            grid.addWidget(stop_widget, row, 2)
            grid.addWidget(step_widget, row, 3)
            grid.addWidget(turns_widget, row, 4)
            grid.addWidget(distance_widget, row, 5)
            self._turn_widgets.append(turns_widget)
            self._distance_per_turn_widgets.append(distance_widget)

        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(4, 1)
        grid.setColumnStretch(5, 1)

        self._turns_header_labels: list[QLabel] = []
        self._turn_axis_labels: list[QLabel] = []

        return group

    def _build_action_buttons(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._vna_sample_button, 1)
        layout.addWidget(self._scan_button, 1)
        layout.addWidget(self._pause_button, 1)
        layout.addWidget(self._stop_button, 1)
        return layout

    def _toggle_pause(self) -> None:
        if self._sampling_paused:
            self.resume_requested.emit()
            return
        self.pause_requested.emit()

    def _connect_config_change_signals(self) -> None:
        for widget in self._input_widgets:
            if isinstance(widget, QDoubleSpinBox):
                widget.valueChanged.connect(lambda _value: self._emit_config_changed())
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(lambda _text: self._emit_config_changed())

    def _emit_config_changed(self) -> None:
        self._refresh_sweep_points_display()
        if not self._sampling_active:
            self.config_changed.emit(self.current_settings())

    def _refresh_sweep_points_display(self) -> None:
        self._sweep_points_label.setText(f"{self._view_model.sweep_points(self._form_state())} 点")

    def _populate_probe_offset_presets(self) -> None:
        for preset in self._view_model.probe_offset_presets():
            self._probe_offset_preset.addItem(preset.label, preset.offset_mm)

    def _apply_probe_offset_preset(self) -> None:
        preset = self._probe_offset_preset.currentData()
        is_custom = preset is None
        self._refresh_probe_offset_editability()
        if is_custom:
            self._emit_config_changed()
            return

        x_offset_mm, y_offset_mm = preset
        self._set_offset_without_noise(self._probe_x_offset_mm, x_offset_mm)
        self._set_offset_without_noise(self._probe_y_offset_mm, y_offset_mm)
        self._emit_config_changed()

    def _refresh_probe_offset_editability(self) -> None:
        is_custom = self._probe_offset_preset.currentData() is None
        enabled = is_custom and not self._sampling_active
        self._probe_x_offset_mm.setEnabled(enabled)
        self._probe_y_offset_mm.setEnabled(enabled)

    def _sync_step_distance_from_turns(self) -> None:
        self._set_step_without_noise(self._step_x_mm, self._computed_step_distance_mm("X"))
        self._set_step_without_noise(self._step_y_mm, self._computed_step_distance_mm("Y"))

    def _sync_turns_from_step_distance(self, axis: str) -> None:
        if self._scan_mode.currentData() != "step":
            return

        if axis.upper() == "Y":
            self._set_turns_without_noise(
                self._step_y_turns,
                self._view_model.turns_from_step_distance(self._step_y_mm.value(), self._y_mm_per_turn.value()),
            )
            return

        self._set_turns_without_noise(
            self._step_x_turns,
            self._view_model.turns_from_step_distance(self._step_x_mm.value(), self._x_mm_per_turn.value()),
        )

    def _computed_step_distance_mm(self, axis: str) -> float:
        return self._view_model.computed_step_distance_mm(self._form_state(), axis)

    def _form_state(self) -> ScanSetupFormState:
        return ScanSetupFormState(
            start_ghz=self._start_ghz.value(),
            stop_ghz=self._stop_ghz.value(),
            frequency_step_mhz=self._frequency_step_mhz.value(),
            vna_power_dbm=self._vna_power_dbm.value(),
            if_bandwidth_hz=self._if_bandwidth_hz.value(),
            parameter=self._parameter.currentText(),
            scan_mode=str(self._scan_mode.currentData()),
            x_start_mm=self._x_start_mm.value(),
            x_stop_mm=self._x_stop_mm.value(),
            y_start_mm=self._y_start_mm.value(),
            y_stop_mm=self._y_stop_mm.value(),
            step_x_mm=self._step_x_mm.value(),
            step_y_mm=self._step_y_mm.value(),
            step_x_turns=self._step_x_turns.value(),
            step_y_turns=self._step_y_turns.value(),
            x_mm_per_turn=self._x_mm_per_turn.value(),
            y_mm_per_turn=self._y_mm_per_turn.value(),
            step_speed_mm_s=self._step_speed_mm_s.value(),
            settle_delay_s=self._settle_delay_s.value(),
            motion_timeout_margin_s=DEFAULT_MOTION_TIMEOUT_MARGIN_S,
            probe_offset_preset=self._probe_offset_preset.currentText(),
            probe_x_offset_mm=self._probe_x_offset_mm.value(),
            probe_y_offset_mm=self._probe_y_offset_mm.value(),
            continuous_speed_mm_s=self._continuous_speed_mm_s.value(),
        )

    @staticmethod
    def _set_speed_without_noise(spinbox: QDoubleSpinBox, speed_mm_s: float) -> None:
        clamped_speed = max(spinbox.minimum(), min(spinbox.maximum(), float(speed_mm_s)))
        if abs(spinbox.value() - clamped_speed) <= 1e-9:
            return

        blocked = spinbox.blockSignals(True)
        try:
            spinbox.setValue(clamped_speed)
        finally:
            spinbox.blockSignals(blocked)

    @staticmethod
    def _set_step_without_noise(spinbox: QDoubleSpinBox, step_mm: float) -> None:
        clamped_step = max(spinbox.minimum(), min(spinbox.maximum(), float(step_mm)))
        if abs(spinbox.value() - clamped_step) <= 1e-9:
            return

        blocked = spinbox.blockSignals(True)
        try:
            spinbox.setValue(clamped_step)
        finally:
            spinbox.blockSignals(blocked)

    @staticmethod
    def _set_turns_without_noise(spinbox: QDoubleSpinBox, turns: float) -> None:
        clamped_turns = max(spinbox.minimum(), min(spinbox.maximum(), float(turns)))
        if abs(spinbox.value() - clamped_turns) <= 1e-9:
            return

        blocked = spinbox.blockSignals(True)
        try:
            spinbox.setValue(clamped_turns)
        finally:
            spinbox.blockSignals(blocked)

    @staticmethod
    def _set_offset_without_noise(spinbox: QDoubleSpinBox, offset_mm: float) -> None:
        clamped_offset = max(spinbox.minimum(), min(spinbox.maximum(), float(offset_mm)))
        if abs(spinbox.value() - clamped_offset) <= 1e-9:
            return

        blocked = spinbox.blockSignals(True)
        try:
            spinbox.setValue(clamped_offset)
        finally:
            spinbox.blockSignals(blocked)

    def _refresh_action_buttons(self) -> None:
        if self._sampling_active:
            self._vna_sample_button.setEnabled(False)
            self._scan_button.setEnabled(False)
            self._pause_button.setEnabled(True)
            if self._sampling_paused:
                self._pause_button.setText("继续")
                self._pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            else:
                self._pause_button.setText("暂停")
                self._pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self._stop_button.setEnabled(True)
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
            return

        enabled = not self._busy
        self._vna_sample_button.setEnabled(enabled)
        self._scan_button.setEnabled(enabled)
        self._pause_button.setEnabled(False)
        self._pause_button.setText("暂停")
        self._pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self._stop_button.setEnabled(False)
        self._stop_button.setStyleSheet("")

    def _refresh_mode_visibility(self) -> None:
        is_step_mode = self._scan_mode.currentData() == "step"
        self._volume_group.setVisible(True)
        step_widgets = (self._step_speed_mm_s, self._settle_delay_s)
        continuous_widgets = (self._continuous_speed_mm_s,)
        for widget in step_widgets:
            widget.setVisible(is_step_mode)
            label = self._mode_field_labels.get(widget) if hasattr(self, "_mode_field_labels") else None
            if label is not None:
                label.setVisible(is_step_mode)
        for widget in continuous_widgets:
            widget.setVisible(not is_step_mode)
            label = self._mode_field_labels.get(widget) if hasattr(self, "_mode_field_labels") else None
            if label is not None:
                label.setVisible(not is_step_mode)
        self._refresh_step_input_mode()
        self._emit_config_changed()

    def _refresh_step_input_mode(self) -> None:
        is_step_mode = self._scan_mode.currentData() == "step"
        self._refresh_volume_layout(is_step_mode)

    def _refresh_volume_layout(self, is_step_mode: bool) -> None:
        grid = self._volume_grid

        for label in self._range_header_labels:
            label.setVisible(is_step_mode)
        for label in self._continuous_header_labels:
            label.setVisible(not is_step_mode)
        for label in self._axis_labels:
            label.setVisible(is_step_mode)
        for label in self._turns_header_labels:
            label.setVisible(is_step_mode)
        for label in self._turn_axis_labels:
            label.setVisible(is_step_mode)
        if self._step_header_label is not None:
            self._step_header_label.setText("换算步进")
            self._step_header_label.setVisible(is_step_mode)
        for widget in self._turn_widgets:
            widget.setVisible(is_step_mode)
        for widget in self._distance_per_turn_widgets:
            widget.setVisible(True)

        self._step_x_mm.setVisible(is_step_mode)
        self._step_y_mm.setVisible(is_step_mode)
        self._step_x_mm.setReadOnly(False)
        self._step_y_mm.setReadOnly(False)

        if is_step_mode:
            grid.addWidget(self._x_start_mm, 1, 1)
            grid.addWidget(self._x_stop_mm, 1, 2)
            grid.addWidget(self._step_x_mm, 1, 3)
            grid.addWidget(self._step_x_turns, 1, 4)
            grid.addWidget(self._x_mm_per_turn, 1, 5)
            grid.addWidget(self._y_start_mm, 2, 1)
            grid.addWidget(self._y_stop_mm, 2, 2)
            grid.addWidget(self._step_y_mm, 2, 3)
            grid.addWidget(self._step_y_turns, 2, 4)
            grid.addWidget(self._y_mm_per_turn, 2, 5)
        else:
            grid.addWidget(self._x_start_mm, 1, 0)
            grid.addWidget(self._x_stop_mm, 1, 1)
            grid.addWidget(self._y_start_mm, 1, 2)
            grid.addWidget(self._y_stop_mm, 1, 3)
            grid.addWidget(self._x_mm_per_turn, 1, 4)
            grid.addWidget(self._y_mm_per_turn, 1, 5)

        self._sync_step_distance_from_turns()

    @staticmethod
    def _frequency_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(0.001, 110.0)
        spinbox.setDecimals(3)
        spinbox.setValue(value)
        spinbox.setSuffix(" GHz")
        return spinbox

    @staticmethod
    def _power_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(-80.0, 20.0)
        spinbox.setDecimals(1)
        spinbox.setSingleStep(1.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" dBm")
        return spinbox

    @staticmethod
    def _if_bandwidth_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(1.0, 10000000.0)
        spinbox.setDecimals(0)
        spinbox.setSingleStep(100.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" Hz")
        return spinbox

    @staticmethod
    def _frequency_step_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(0.001, 1000000.0)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(1.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" MHz")
        return spinbox

    @staticmethod
    def _coordinate_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(0.0, 10000.0)
        spinbox.setDecimals(1)
        spinbox.setSingleStep(10.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" mm")
        spinbox.setMinimumWidth(84)
        return spinbox

    @staticmethod
    def _offset_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(-MAX_PROBE_OFFSET_MM, MAX_PROBE_OFFSET_MM)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(1.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" mm")
        spinbox.setMinimumWidth(84)
        return spinbox

    @staticmethod
    def _step_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(0.1, 1000000.0)
        spinbox.setDecimals(1)
        spinbox.setSingleStep(5.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" mm")
        spinbox.setMinimumWidth(84)
        return spinbox

    @staticmethod
    def _turns_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(0.0001, 1000000.0)
        spinbox.setDecimals(4)
        spinbox.setSingleStep(0.1)
        spinbox.setValue(value)
        spinbox.setSuffix(" 圈")
        spinbox.setMinimumWidth(84)
        return spinbox

    @staticmethod
    def _distance_per_turn_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(0.0001, 1000000.0)
        spinbox.setDecimals(4)
        spinbox.setSingleStep(1.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" mm/圈")
        spinbox.setMinimumWidth(84)
        return spinbox

    @staticmethod
    def _speed_spinbox(value: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(-1000000.0, 1000000.0)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(10.0)
        spinbox.setValue(value)
        spinbox.setSuffix(" mm/s")
        spinbox.setMinimumWidth(84)
        return spinbox

    @staticmethod
    def _seconds_spinbox(value: float, minimum: float, maximum: float) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(0.1)
        spinbox.setValue(value)
        spinbox.setSuffix(" s")
        spinbox.setMinimumWidth(84)
        return spinbox
