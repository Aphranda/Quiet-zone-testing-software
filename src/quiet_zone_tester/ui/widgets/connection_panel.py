from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from quiet_zone_tester.hardware import InstrumentInfo
from quiet_zone_tester.presentation.modules.connection import (
    ConnectionState,
    ConnectionViewModel,
    PositionerFormState,
    SwitchBoxFormState,
    VnaFormState,
)
from quiet_zone_tester.shared.instrument_defaults import MAX_POSITIONER_SPEED_MM_S


logger = logging.getLogger(__name__)


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()

    def showPopup(self) -> None:  # noqa: N802 - Qt override.
        refresh = getattr(self, "_refresh_before_popup", None)
        if callable(refresh):
            refresh()
        super().showPopup()


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class ConnectionPanel(QGroupBox):
    connect_all_requested = Signal(dict)
    connect_vna_requested = Signal(dict)
    connect_positioner_requested = Signal(dict)
    connect_switch_box_requested = Signal(dict)
    positioner_axis_move_requested = Signal(dict, str)
    positioner_axis_stop_requested = Signal(dict, str)
    positioner_default_speed_changed = Signal(float)
    disconnect_all_requested = Signal()
    disconnect_vna_requested = Signal()
    disconnect_positioner_requested = Signal()
    disconnect_switch_box_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("仪器连接", parent)
        self._view_model = ConnectionViewModel()
        self._vna_defaults = self._view_model.default_vna_form_state()
        self._positioner_defaults = self._view_model.default_positioner_form_state()
        self._switch_box_defaults = self._view_model.default_switch_box_form_state()
        self._busy = False
        self._vna_connected = False
        self._positioner_connected = False
        self._switch_box_connected = False

        self._state_value = QLabel("未连接")
        self._vna_value = QLabel("-")
        self._positioner_value = QLabel("-")
        self._switch_box_value = QLabel("-")

        self._vna_connection_mode = NoWheelComboBox()
        self._vna_connection_mode.addItem("真实连接", False)
        self._vna_connection_mode.addItem("虚拟连接", True)
        self._vna_model = NoWheelComboBox()
        self._vna_model.addItems(self._view_model.supported_vna_models())
        self._vna_model.setCurrentText(self._vna_defaults.model)
        self._vna_ip = QLineEdit(self._vna_defaults.ip_address)
        self._vna_port = self._port_spinbox(self._vna_defaults.port)
        self._vna_resource = QLineEdit()
        self._vna_resource.setReadOnly(True)
        self._vna_timeout_ms = self._timeout_spinbox(self._vna_defaults.timeout_ms)
        self._sync_vna_resource()
        self._vna_ip.textChanged.connect(lambda _text: self._sync_vna_resource())
        self._vna_port.valueChanged.connect(lambda _value: self._sync_vna_resource())

        self._positioner_port_name = self._init_serial_port_combobox()
        self._positioner_port_field = self._serial_port_field(self._positioner_port_name)
        self._positioner_baudrate = self._baudrate_spinbox(self._positioner_defaults.baudrate)
        self._positioner_default_speed = self._positive_double_spinbox(
            self._positioner_defaults.default_speed,
            " mm/s",
        )
        self._positioner_default_speed.valueChanged.connect(self.positioner_default_speed_changed.emit)
        self._positioner_timeout_ms = self._timeout_spinbox(self._positioner_defaults.timeout_ms)

        self._switch_box_connection_mode = NoWheelComboBox()
        self._switch_box_connection_mode.addItem("真实连接", False)
        self._switch_box_connection_mode.addItem("虚拟连接", True)
        self._switch_box_model = NoWheelComboBox()
        self._switch_box_model.addItems(self._view_model.supported_switch_box_models())
        self._switch_box_connection_type = NoWheelComboBox()
        self._switch_box_connection_type.addItems(["TCP/IP", "Serial"])
        self._switch_box_ip = QLineEdit(self._switch_box_defaults.ip_address)
        self._switch_box_tcp_port = self._port_spinbox(self._switch_box_defaults.tcp_port)
        self._switch_box_serial_port = self._init_serial_port_combobox()
        self._switch_box_serial_port_field = self._serial_port_field(self._switch_box_serial_port)
        self._switch_box_baudrate = self._baudrate_spinbox(self._switch_box_defaults.baudrate)
        self._switch_box_timeout_ms = self._timeout_spinbox(self._switch_box_defaults.timeout_ms)
        self._switch_box_model.currentTextChanged.connect(self._on_switch_box_model_changed)
        self._on_switch_box_model_changed(self._switch_box_model.currentText())

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("状态"))
        status_row.addWidget(self._state_value)
        status_row.addStretch(1)

        self._connect_all_button = QPushButton("连接全部")
        self._connect_all_button.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self._connect_all_button.clicked.connect(lambda: self.connect_all_requested.emit(self.current_config()))

        self._disconnect_all_button = QPushButton("断开全部")
        self._disconnect_all_button.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        self._disconnect_all_button.clicked.connect(self.disconnect_all_requested)

        buttons = QHBoxLayout()
        buttons.addWidget(self._connect_all_button)
        buttons.addWidget(self._disconnect_all_button)

        instrument_columns = QHBoxLayout()
        instrument_columns.setSpacing(8)
        instrument_columns.addWidget(self._build_vna_group(), 1)
        instrument_columns.addWidget(self._build_positioner_group(), 1)
        instrument_columns.addWidget(self._build_switch_box_group(), 1)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addLayout(status_row)
        content_layout.addLayout(instrument_columns)
        content_layout.addLayout(buttons)
        content_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setWidget(content)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll_area)
        self._refresh_state()

    def current_config(self) -> dict:
        self._sync_vna_resource()
        return self._view_model.build_config(
            vna=VnaFormState(
                virtual_enabled=bool(self._vna_connection_mode.currentData()),
                model=self._vna_model.currentText(),
                ip_address=self._vna_ip.text(),
                port=self._vna_port.value(),
                timeout_ms=self._vna_timeout_ms.value(),
            ),
            positioner=PositionerFormState(
                port_name=self._combo_text(self._positioner_port_name),
                baudrate=self._positioner_baudrate.value(),
                default_speed=self._positioner_default_speed.value(),
                timeout_ms=self._positioner_timeout_ms.value(),
                x_axis=self._positioner_defaults.x_axis,
                y_axis=self._positioner_defaults.y_axis,
                pulses_per_mm=self._positioner_defaults.pulses_per_mm,
            ),
            switch_box=SwitchBoxFormState(
                virtual_enabled=bool(self._switch_box_connection_mode.currentData()),
                model=self._switch_box_model.currentText(),
                connection_type=self._switch_box_connection_type.currentText(),
                ip_address=self._switch_box_ip.text(),
                tcp_port=self._switch_box_tcp_port.value(),
                serial_port=self._combo_text(self._switch_box_serial_port),
                baudrate=self._switch_box_baudrate.value(),
                timeout_ms=self._switch_box_timeout_ms.value(),
            ),
        )

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh_state()

    def set_vna_connected(self, info: InstrumentInfo) -> None:
        self._vna_connected = True
        self._vna_value.setText(self._instrument_label(info))
        self._refresh_state()

    def set_positioner_connected(self, info: InstrumentInfo) -> None:
        self._positioner_connected = True
        self._positioner_value.setText(self._instrument_label(info))
        self._refresh_state()

    def set_switch_box_connected(self, info: InstrumentInfo) -> None:
        self._switch_box_connected = True
        self._switch_box_value.setText(self._instrument_label(info))
        self._refresh_state()

    def set_all_connected(self, instruments: list[InstrumentInfo]) -> None:
        if instruments:
            self.set_vna_connected(instruments[0])
        if len(instruments) > 1:
            self.set_positioner_connected(instruments[1])
        if len(instruments) > 2:
            self.set_switch_box_connected(instruments[2])
        self._refresh_state()

    def set_vna_disconnected(self) -> None:
        self._vna_connected = False
        self._vna_value.setText("-")
        self._refresh_state()

    def set_positioner_disconnected(self) -> None:
        self._positioner_connected = False
        self._positioner_value.setText("-")
        self._refresh_state()

    def set_switch_box_disconnected(self) -> None:
        self._switch_box_connected = False
        self._switch_box_value.setText("-")
        self._refresh_state()

    def set_all_disconnected(self) -> None:
        self._vna_connected = False
        self._positioner_connected = False
        self._switch_box_connected = False
        self._vna_value.setText("-")
        self._positioner_value.setText("-")
        self._switch_box_value.setText("-")
        self._refresh_state()

    def _build_vna_group(self) -> QGroupBox:
        group = QGroupBox("网分仪配置")
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("连接模式", self._vna_connection_mode)
        form.addRow("型号", self._vna_model)
        form.addRow("IP 地址", self._vna_ip)
        form.addRow("端口", self._vna_port)
        form.addRow("VISA 资源", self._vna_resource)
        form.addRow("超时", self._vna_timeout_ms)

        self._connect_vna_button = QPushButton("连接网分")
        self._connect_vna_button.clicked.connect(
            lambda: self.connect_vna_requested.emit(self.current_config())
        )
        self._disconnect_vna_button = QPushButton("断开网分")
        self._disconnect_vna_button.clicked.connect(self.disconnect_vna_requested)
        self._add_button_row(form, self._connect_vna_button, self._disconnect_vna_button)
        return group

    def _sync_vna_resource(self) -> None:
        self._vna_resource.setText(
            self._view_model.vna_resource_name(self._vna_ip.text(), self._vna_port.value())
        )

    def _build_positioner_group(self) -> QGroupBox:
        group = QGroupBox("扫描架配置")
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("串口", self._positioner_port_field)
        form.addRow("波特率", self._positioner_baudrate)
        form.addRow("默认速度", self._positioner_default_speed)
        form.addRow("超时", self._positioner_timeout_ms)

        self._connect_positioner_button = QPushButton("连接扫描架")
        self._connect_positioner_button.clicked.connect(
            lambda: self.connect_positioner_requested.emit(self.current_config())
        )
        self._disconnect_positioner_button = QPushButton("断开扫描架")
        self._disconnect_positioner_button.clicked.connect(self.disconnect_positioner_requested)

        self._add_button_row(form, self._connect_positioner_button, self._disconnect_positioner_button)
        return group

    def _build_switch_box_group(self) -> QGroupBox:
        group = QGroupBox("开关箱配置")
        layout = QVBoxLayout(group)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("连接模式", self._switch_box_connection_mode)
        form.addRow("型号", self._switch_box_model)
        form.addRow("超时", self._switch_box_timeout_ms)
        layout.addLayout(form)

        self._switch_box_tcp_group = self._build_switch_box_tcp_group()
        self._switch_box_serial_group = self._build_switch_box_serial_group()
        layout.addWidget(self._switch_box_tcp_group)
        layout.addWidget(self._switch_box_serial_group)

        self._connect_switch_box_button = QPushButton("连接开关箱")
        self._connect_switch_box_button.clicked.connect(
            lambda: self.connect_switch_box_requested.emit(self.current_config())
        )
        self._disconnect_switch_box_button = QPushButton("断开开关箱")
        self._disconnect_switch_box_button.clicked.connect(self.disconnect_switch_box_requested)
        button_row = QHBoxLayout()
        button_row.addWidget(self._connect_switch_box_button)
        button_row.addWidget(self._disconnect_switch_box_button)
        layout.addLayout(button_row)
        layout.addStretch(1)

        self._refresh_switch_box_config_fields()
        return group

    def _build_switch_box_tcp_group(self) -> QGroupBox:
        group = QGroupBox("TCP/IP 配置")
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("IP 地址", self._switch_box_ip)
        form.addRow("TCP 端口", self._switch_box_tcp_port)
        return group

    def _build_switch_box_serial_group(self) -> QGroupBox:
        group = QGroupBox("串口配置")
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("串口", self._switch_box_serial_port_field)
        form.addRow("波特率", self._switch_box_baudrate)
        return group

    def _refresh_state(self) -> None:
        state = self._view_model.panel_state(
            connection=ConnectionState(
                vna_connected=self._vna_connected,
                positioner_connected=self._positioner_connected,
                switch_box_connected=self._switch_box_connected,
            ),
            busy=self._busy,
        )
        self._state_value.setText(state.state_text)
        self._connect_all_button.setEnabled(state.connect_all_enabled)
        self._disconnect_all_button.setEnabled(state.disconnect_all_enabled)
        self._connect_vna_button.setEnabled(state.connect_vna_enabled)
        self._disconnect_vna_button.setEnabled(state.disconnect_vna_enabled)
        self._connect_positioner_button.setEnabled(state.connect_positioner_enabled)
        self._disconnect_positioner_button.setEnabled(state.disconnect_positioner_enabled)
        self._connect_switch_box_button.setEnabled(state.connect_switch_box_enabled)
        self._disconnect_switch_box_button.setEnabled(state.disconnect_switch_box_enabled)

    @staticmethod
    def _add_button_row(form: QFormLayout, left: QPushButton, right: QPushButton) -> None:
        row = QHBoxLayout()
        row.addWidget(left)
        row.addWidget(right)
        form.addRow("", row)

    @staticmethod
    def _port_spinbox(value: int) -> QSpinBox:
        spinbox = NoWheelSpinBox()
        spinbox.setRange(1, 65535)
        spinbox.setValue(value)
        return spinbox

    @staticmethod
    def _baudrate_spinbox(value: int) -> QSpinBox:
        spinbox = NoWheelSpinBox()
        spinbox.setRange(1200, 921600)
        spinbox.setSingleStep(9600)
        spinbox.setValue(value)
        return spinbox

    @staticmethod
    def _positive_double_spinbox(value: float, suffix: str) -> QDoubleSpinBox:
        spinbox = NoWheelDoubleSpinBox()
        spinbox.setRange(0.000001, MAX_POSITIONER_SPEED_MM_S)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(1.0)
        spinbox.setValue(value)
        spinbox.setSuffix(suffix)
        return spinbox

    @staticmethod
    def _timeout_spinbox(value: int) -> QSpinBox:
        spinbox = NoWheelSpinBox()
        spinbox.setRange(100, 120000)
        spinbox.setSingleStep(1000)
        spinbox.setValue(value)
        spinbox.setSuffix(" ms")
        return spinbox

    def _serial_port_field(self, combobox: NoWheelComboBox) -> QWidget:
        field = QWidget()
        layout = QHBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(combobox, 1)

        refresh_button = QPushButton("刷新")
        refresh_icon = getattr(QStyle, "SP_BrowserReload", QStyle.SP_FileDialogDetailedView)
        refresh_button.setIcon(self.style().standardIcon(refresh_icon))
        refresh_button.setToolTip("重新搜索串口")
        refresh_button.clicked.connect(lambda: self._refresh_serial_ports(combobox))
        layout.addWidget(refresh_button, 0)
        return field

    @staticmethod
    def _serial_port_combobox() -> NoWheelComboBox:
        combobox = NoWheelComboBox()
        combobox.setEditable(True)
        return combobox

    def _init_serial_port_combobox(self) -> NoWheelComboBox:
        combobox = self._serial_port_combobox()
        combobox._refresh_before_popup = lambda: self._refresh_serial_ports(combobox)
        self._refresh_serial_ports(combobox)
        return combobox

    def _refresh_serial_ports(self, combobox: QComboBox) -> None:
        current_text = combobox.currentText().strip()
        ports = self._view_model.available_serial_ports()

        blocked = combobox.blockSignals(True)
        try:
            combobox.clear()
            combobox.addItems(ports)
            if current_text and current_text in ports:
                combobox.setCurrentText(current_text)
            elif ports:
                combobox.setCurrentIndex(0)
            else:
                combobox.setEditText("")
        finally:
            combobox.blockSignals(blocked)

    @staticmethod
    def _combo_text(combobox: QComboBox) -> str:
        return combobox.currentText().strip()

    def _on_switch_box_model_changed(self, model: str) -> None:
        defaults = self._view_model.switch_box_defaults(model)
        self._switch_box_connection_type.setCurrentText(defaults.connection_type)
        self._switch_box_ip.setText(defaults.ip_address)
        self._switch_box_tcp_port.setValue(defaults.tcp_port)
        self._switch_box_timeout_ms.setValue(defaults.timeout_ms)
        self._refresh_switch_box_config_fields()

    def _refresh_switch_box_config_fields(self) -> None:
        if not hasattr(self, "_switch_box_tcp_group") or not hasattr(self, "_switch_box_serial_group"):
            return

        is_serial = self._view_model.is_serial_connection(self._switch_box_connection_type.currentText())
        self._switch_box_tcp_group.setVisible(not is_serial)
        self._switch_box_serial_group.setVisible(is_serial)

    @staticmethod
    def _instrument_label(info: InstrumentInfo) -> str:
        if info.is_mock:
            return f"虚拟：{info.model} ({info.resource_name})"
        return f"{info.model} ({info.resource_name})"
