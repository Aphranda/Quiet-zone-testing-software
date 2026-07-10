from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from serial.tools import list_ports

from quiet_zone_tester.domains.instrument_management import InstrumentConnectionConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VnaFormState:
    virtual_enabled: bool = False
    ip_address: str = "192.168.1.10"
    port: int = 5025
    timeout_ms: int = 5000


@dataclass(frozen=True)
class PositionerFormState:
    port_name: str = ""
    baudrate: int = 115200
    default_speed: float = 20.0
    timeout_ms: int = 1000
    x_axis: int = 2
    y_axis: int = 3
    pulses_per_mm: float = 400.0


@dataclass(frozen=True)
class SwitchBoxFormState:
    virtual_enabled: bool = False
    model: str = "LCD74000F"
    connection_type: str = "TCP/IP"
    ip_address: str = "192.168.1.113"
    tcp_port: int = 7
    serial_port: str = ""
    baudrate: int = 115200
    timeout_ms: int = 2000


@dataclass(frozen=True)
class SwitchBoxModelDefaults:
    connection_type: str
    ip_address: str
    tcp_port: int
    timeout_ms: int


@dataclass(frozen=True)
class ConnectionState:
    vna_connected: bool = False
    positioner_connected: bool = False
    switch_box_connected: bool = False

    @property
    def all_connected(self) -> bool:
        return self.vna_connected and self.positioner_connected and self.switch_box_connected

    @property
    def has_any_connection(self) -> bool:
        return self.vna_connected or self.positioner_connected or self.switch_box_connected


@dataclass(frozen=True)
class ConnectionPanelState:
    state_text: str
    connect_all_enabled: bool
    disconnect_all_enabled: bool
    connect_vna_enabled: bool
    disconnect_vna_enabled: bool
    connect_positioner_enabled: bool
    disconnect_positioner_enabled: bool
    connect_switch_box_enabled: bool
    disconnect_switch_box_enabled: bool


class ConnectionViewModel:
    DEFAULT_POSITIONER_PULSES_PER_MM = 400.0
    DEFAULT_POSITIONER_X_AXIS = 2
    DEFAULT_POSITIONER_Y_AXIS = 3

    def __init__(self, serial_port_provider: Callable[[], list[str]] | None = None) -> None:
        self._serial_port_provider = serial_port_provider or self.enumerate_serial_ports

    def build_config(
        self,
        *,
        vna: VnaFormState,
        positioner: PositionerFormState,
        switch_box: SwitchBoxFormState,
    ) -> dict:
        config = InstrumentConnectionConfig.from_dict(
            {
                "vna": {
                    "virtual_enabled": vna.virtual_enabled,
                    "ip_address": vna.ip_address.strip(),
                    "port": vna.port,
                    "resource_name": self.vna_resource_name(vna.ip_address, vna.port),
                    "timeout_ms": vna.timeout_ms,
                },
                "positioner": {
                    "port_name": positioner.port_name.strip(),
                    "resource_name": positioner.port_name.strip(),
                    "baudrate": positioner.baudrate,
                    "x_axis": positioner.x_axis,
                    "y_axis": positioner.y_axis,
                    "pulses_per_mm": positioner.pulses_per_mm,
                    "x_pulses_per_mm": positioner.pulses_per_mm,
                    "y_pulses_per_mm": positioner.pulses_per_mm,
                    "default_speed": positioner.default_speed,
                    "timeout_ms": positioner.timeout_ms,
                },
                "switch_box": {
                    "virtual_enabled": switch_box.virtual_enabled,
                    "model": switch_box.model.strip(),
                    "connection_type": switch_box.connection_type.strip(),
                    "ip_address": switch_box.ip_address.strip(),
                    "tcp_port": switch_box.tcp_port,
                    "serial_port": switch_box.serial_port.strip(),
                    "baudrate": switch_box.baudrate,
                    "timeout_ms": switch_box.timeout_ms,
                },
            }
        )
        return config.to_dict()

    def available_serial_ports(self) -> list[str]:
        try:
            return list(self._serial_port_provider())
        except Exception:
            logger.exception("Failed to enumerate serial ports.")
            return []

    @staticmethod
    def panel_state(*, connection: ConnectionState, busy: bool) -> ConnectionPanelState:
        busy = bool(busy)
        if busy:
            state_text = "处理中..."
        elif connection.all_connected:
            state_text = "全部已连接"
        elif connection.has_any_connection:
            connected_names = []
            if connection.vna_connected:
                connected_names.append("网分")
            if connection.positioner_connected:
                connected_names.append("扫描架")
            if connection.switch_box_connected:
                connected_names.append("开关箱")
            state_text = "已连接：" + "、".join(connected_names)
        else:
            state_text = "未连接"

        return ConnectionPanelState(
            state_text=state_text,
            connect_all_enabled=not busy and not connection.all_connected,
            disconnect_all_enabled=not busy and connection.has_any_connection,
            connect_vna_enabled=not busy and not connection.vna_connected,
            disconnect_vna_enabled=not busy and connection.vna_connected,
            connect_positioner_enabled=not busy and not connection.positioner_connected,
            disconnect_positioner_enabled=not busy and connection.positioner_connected,
            connect_switch_box_enabled=not busy and not connection.switch_box_connected,
            disconnect_switch_box_enabled=not busy and connection.switch_box_connected,
        )

    @staticmethod
    def vna_resource_name(ip_address: str, port: int) -> str:
        ip_address = str(ip_address).strip()
        if not ip_address:
            return ""
        return f"TCPIP0::{ip_address}::{int(port)}::SOCKET"

    @staticmethod
    def switch_box_defaults(model: str) -> SwitchBoxModelDefaults:
        if str(model).strip().upper() == "LCD74000F":
            return SwitchBoxModelDefaults(
                connection_type="TCP/IP",
                ip_address="192.168.1.113",
                tcp_port=7,
                timeout_ms=2000,
            )
        return SwitchBoxModelDefaults(
            connection_type="Serial",
            ip_address="192.168.1.120",
            tcp_port=35,
            timeout_ms=1500,
        )

    @staticmethod
    def is_serial_connection(connection_type: str) -> bool:
        return str(connection_type).strip().upper() in {"SERIAL", "串口", "RS232", "RS485"}

    @staticmethod
    def enumerate_serial_ports() -> list[str]:
        return [port.device for port in list_ports.comports()]
