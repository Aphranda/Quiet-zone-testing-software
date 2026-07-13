from __future__ import annotations

import logging
import re
import socket
from dataclasses import dataclass
from typing import Callable

from serial.tools import list_ports

from quiet_zone_tester.domains.instrument_management import InstrumentConnectionConfig
from quiet_zone_tester.shared.instrument_defaults import (
    DEFAULT_POSITIONER_BAUDRATE,
    DEFAULT_POSITIONER_PULSES_PER_MM,
    DEFAULT_POSITIONER_SPEED_MM_S,
    DEFAULT_POSITIONER_TIMEOUT_MS,
    DEFAULT_POSITIONER_X_AXIS,
    DEFAULT_POSITIONER_Y_AXIS,
    DEFAULT_SWITCH_BOX_BAUDRATE,
    DEFAULT_SWITCH_BOX_CONNECTION_TYPE,
    DEFAULT_SWITCH_BOX_MODEL,
    DEFAULT_VNA_MODEL,
    DEFAULT_VNA_IP_ADDRESS,
    DEFAULT_VNA_PORT,
    DEFAULT_VNA_TIMEOUT_MS,
    SUPPORTED_SWITCH_BOX_MODELS,
    SUPPORTED_VNA_MODELS,
    SwitchBoxModelDefaults,
    switch_box_model_defaults,
    vna_model_defaults,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VnaFormState:
    virtual_enabled: bool = False
    model: str = DEFAULT_VNA_MODEL
    ip_address: str = DEFAULT_VNA_IP_ADDRESS
    port: int = DEFAULT_VNA_PORT
    resource_name: str = ""
    timeout_ms: int = DEFAULT_VNA_TIMEOUT_MS


@dataclass(frozen=True)
class PositionerFormState:
    port_name: str = ""
    baudrate: int = DEFAULT_POSITIONER_BAUDRATE
    default_speed: float = DEFAULT_POSITIONER_SPEED_MM_S
    timeout_ms: int = DEFAULT_POSITIONER_TIMEOUT_MS
    x_axis: int = DEFAULT_POSITIONER_X_AXIS
    y_axis: int = DEFAULT_POSITIONER_Y_AXIS
    pulses_per_mm: float = DEFAULT_POSITIONER_PULSES_PER_MM


@dataclass(frozen=True)
class SwitchBoxFormState:
    virtual_enabled: bool = False
    model: str = DEFAULT_SWITCH_BOX_MODEL
    connection_type: str = DEFAULT_SWITCH_BOX_CONNECTION_TYPE
    ip_address: str = switch_box_model_defaults(DEFAULT_SWITCH_BOX_MODEL).ip_address
    tcp_port: int = switch_box_model_defaults(DEFAULT_SWITCH_BOX_MODEL).tcp_port
    serial_port: str = ""
    baudrate: int = DEFAULT_SWITCH_BOX_BAUDRATE
    timeout_ms: int = switch_box_model_defaults(DEFAULT_SWITCH_BOX_MODEL).timeout_ms


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
    def __init__(
        self,
        serial_port_provider: Callable[[], list[str]] | None = None,
        visa_resource_provider: Callable[[], list[str]] | None = None,
    ) -> None:
        self._serial_port_provider = serial_port_provider or self.enumerate_serial_ports
        self._visa_resource_provider = visa_resource_provider or self.enumerate_visa_resources

    @staticmethod
    def default_vna_form_state() -> VnaFormState:
        defaults = vna_model_defaults(DEFAULT_VNA_MODEL)
        return VnaFormState(
            model=DEFAULT_VNA_MODEL,
            ip_address=defaults.ip_address,
            port=defaults.port,
            timeout_ms=defaults.timeout_ms,
        )

    @staticmethod
    def default_positioner_form_state() -> PositionerFormState:
        return PositionerFormState()

    @staticmethod
    def default_switch_box_form_state() -> SwitchBoxFormState:
        return SwitchBoxFormState()

    @staticmethod
    def supported_switch_box_models() -> tuple[str, ...]:
        return SUPPORTED_SWITCH_BOX_MODELS

    @staticmethod
    def supported_vna_models() -> tuple[str, ...]:
        return SUPPORTED_VNA_MODELS

    @staticmethod
    def vna_defaults(model: str):
        return vna_model_defaults(model)

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
                    "model": vna.model.strip().upper(),
                    "ip_address": vna.ip_address.strip(),
                    "port": vna.port,
                    "resource_name": self.vna_resource_name(
                        vna.ip_address,
                        vna.port,
                        resource_name=vna.resource_name,
                    ),
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

    def available_visa_resources(self) -> list[str]:
        try:
            return list(self._visa_resource_provider())
        except Exception:
            logger.exception("Failed to enumerate VISA resources.")
            return []

    def available_vna_visa_resources(self, model: str) -> list[str]:
        return self.filter_visa_resources_by_model(self.available_visa_resources(), model)

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
    def vna_resource_name(ip_address: str, port: int, *, resource_name: str = "") -> str:
        resource_name = str(resource_name).strip()
        if resource_name:
            return resource_name
        ip_address = str(ip_address).strip()
        if not ip_address:
            return ""
        return f"TCPIP0::{ip_address}::{int(port)}::SOCKET"

    @classmethod
    def host_port_from_visa_resource(cls, resource_name: str) -> tuple[str, int] | None:
        resource_name = str(resource_name).strip()
        match = re.match(r"^TCPIP\d*::([^:]+)::(?:(\d+)::SOCKET|[^:]+::INSTR)$", resource_name, flags=re.IGNORECASE)
        if not match:
            return None
        host = match.group(1)
        port = int(match.group(2) or DEFAULT_VNA_PORT)
        return cls.resolve_host_if_possible(host), port

    @staticmethod
    def resolve_host_if_possible(host: str) -> str:
        host = str(host).strip()
        if not host:
            return host
        if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", host):
            return host
        try:
            return socket.gethostbyname(host)
        except OSError:
            logger.info("VISA host could not be resolved to IPv4, keeping host name: %s", host)
            return host

    @staticmethod
    def switch_box_defaults(model: str) -> SwitchBoxModelDefaults:
        return switch_box_model_defaults(model)

    @staticmethod
    def is_serial_connection(connection_type: str) -> bool:
        return str(connection_type).strip().upper() in {"SERIAL", "串口", "RS232", "RS485"}

    @staticmethod
    def enumerate_serial_ports() -> list[str]:
        return [port.device for port in list_ports.comports()]

    @staticmethod
    def enumerate_visa_resources() -> list[str]:
        import pyvisa

        resource_manager = pyvisa.ResourceManager()
        return [str(resource) for resource in resource_manager.list_resources()]

    @staticmethod
    def filter_visa_resources_by_model(resources: list[str], model: str) -> list[str]:
        model = str(model).strip().upper()
        if not model:
            return list(resources)
        tokens = {model}
        if len(model) > 1 and model[0].isalpha():
            tokens.add(model[1:])
        return [resource for resource in resources if any(token in str(resource).upper() for token in tokens)]
