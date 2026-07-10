from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _bool_from_config(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "虚拟连接", "虚拟"}
    return bool(value)


@dataclass(frozen=True)
class VnaConnectionConfig:
    virtual_enabled: bool = False
    ip_address: str = ""
    port: int = 5025
    resource_name: str = ""
    timeout_ms: int = 5000
    retries: int = 2
    retry_delay_s: float = 0.2

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "VnaConnectionConfig":
        config = config or {}
        return cls(
            virtual_enabled=_bool_from_config(config.get("virtual_enabled"), False),
            ip_address=str(config.get("ip_address", "")).strip(),
            port=int(config.get("port", 5025)),
            resource_name=str(config.get("resource_name", "")).strip(),
            timeout_ms=int(config.get("timeout_ms", 5000)),
            retries=int(config.get("retries", 2)),
            retry_delay_s=float(config.get("retry_delay_s", 0.2)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "virtual_enabled": self.virtual_enabled,
            "ip_address": self.ip_address,
            "port": self.port,
            "resource_name": self.resource_name,
            "timeout_ms": self.timeout_ms,
            "retries": self.retries,
            "retry_delay_s": self.retry_delay_s,
        }


@dataclass(frozen=True)
class PositionerConnectionConfig:
    port_name: str = ""
    resource_name: str = ""
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    timeout_ms: int = 1000
    retries: int = 2
    retry_delay_s: float = 0.05
    x_axis: int = 2
    y_axis: int = 3
    pulses_per_mm: float = 1.0
    pulses_per_degree: float | None = None
    x_pulses_per_mm: float | None = None
    y_pulses_per_mm: float | None = None
    x_units_per_turn: float | None = None
    y_units_per_turn: float | None = None
    x_mm_per_turn: float | None = None
    y_mm_per_turn: float | None = None
    default_speed: float = 20.0
    virtual_enabled: bool = False

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "PositionerConnectionConfig":
        config = config or {}
        port_name = str(config.get("port_name") or config.get("resource_name") or "").strip()
        return cls(
            port_name=port_name,
            resource_name=str(config.get("resource_name") or port_name).strip(),
            baudrate=int(config.get("baudrate", 115200)),
            bytesize=int(config.get("bytesize", 8)),
            parity=str(config.get("parity", "N")).strip().upper() or "N",
            stopbits=int(config.get("stopbits", 1)),
            timeout_ms=int(config.get("timeout_ms", 1000)),
            retries=int(config.get("retries", 2)),
            retry_delay_s=float(config.get("retry_delay_s", 0.05)),
            x_axis=int(config.get("x_axis", 2)),
            y_axis=int(config.get("y_axis", 3)),
            pulses_per_mm=float(config.get("pulses_per_mm", config.get("pulses_per_degree", 1.0))),
            pulses_per_degree=_optional_float(config.get("pulses_per_degree")),
            x_pulses_per_mm=_optional_float(config.get("x_pulses_per_mm")),
            y_pulses_per_mm=_optional_float(config.get("y_pulses_per_mm")),
            x_units_per_turn=_optional_float(config.get("x_units_per_turn")),
            y_units_per_turn=_optional_float(config.get("y_units_per_turn")),
            x_mm_per_turn=_optional_float(config.get("x_mm_per_turn")),
            y_mm_per_turn=_optional_float(config.get("y_mm_per_turn")),
            default_speed=float(config.get("default_speed", 20.0)),
            virtual_enabled=_bool_from_config(config.get("virtual_enabled"), False),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "port_name": self.port_name,
            "resource_name": self.resource_name,
            "baudrate": self.baudrate,
            "bytesize": self.bytesize,
            "parity": self.parity,
            "stopbits": self.stopbits,
            "timeout_ms": self.timeout_ms,
            "retries": self.retries,
            "retry_delay_s": self.retry_delay_s,
            "x_axis": self.x_axis,
            "y_axis": self.y_axis,
            "pulses_per_mm": self.pulses_per_mm,
            "default_speed": self.default_speed,
            "virtual_enabled": self.virtual_enabled,
        }
        _set_optional(data, "pulses_per_degree", self.pulses_per_degree)
        _set_optional(data, "x_pulses_per_mm", self.x_pulses_per_mm)
        _set_optional(data, "y_pulses_per_mm", self.y_pulses_per_mm)
        _set_optional(data, "x_units_per_turn", self.x_units_per_turn)
        _set_optional(data, "y_units_per_turn", self.y_units_per_turn)
        _set_optional(data, "x_mm_per_turn", self.x_mm_per_turn)
        _set_optional(data, "y_mm_per_turn", self.y_mm_per_turn)
        return data


@dataclass(frozen=True)
class SwitchBoxConnectionConfig:
    virtual_enabled: bool = False
    model: str = "LCD74000F"
    connection_type: str = "TCP/IP"
    ip_address: str = ""
    tcp_port: int = 7
    port: int | None = None
    serial_port: str = "COM3"
    baudrate: int = 115200
    timeout_ms: int = 2000
    command_terminator: str | None = None
    identify_command: str | None = None
    s11_command: str | None = None
    s21_command: str | None = None
    s12_command: str | None = None
    s22_command: str | None = None
    retries: int = 1
    retry_delay_s: float = 0.2

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "SwitchBoxConnectionConfig":
        config = config or {}
        model = str(config.get("model", "LCD74000F")).strip().upper() or "LCD74000F"
        default_tcp_port = 35 if model == "TC500" else 7
        return cls(
            virtual_enabled=_bool_from_config(config.get("virtual_enabled"), False),
            model=model,
            connection_type=str(config.get("connection_type", "TCP/IP")).strip() or "TCP/IP",
            ip_address=str(config.get("ip_address", "")).strip(),
            tcp_port=int(config.get("tcp_port", config.get("port", default_tcp_port))),
            port=_optional_int(config.get("port")),
            serial_port=str(config.get("serial_port", "COM3")).strip(),
            baudrate=int(config.get("baudrate", 115200)),
            timeout_ms=int(config.get("timeout_ms", 2000 if model == "LCD74000F" else 1500)),
            command_terminator=_optional_str(config.get("command_terminator")),
            identify_command=_optional_str(config.get("identify_command")),
            s11_command=_optional_str(config.get("s11_command")),
            s21_command=_optional_str(config.get("s21_command")),
            s12_command=_optional_str(config.get("s12_command")),
            s22_command=_optional_str(config.get("s22_command")),
            retries=int(config.get("retries", 1)),
            retry_delay_s=float(config.get("retry_delay_s", 0.2)),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "virtual_enabled": self.virtual_enabled,
            "model": self.model,
            "connection_type": self.connection_type,
            "ip_address": self.ip_address,
            "tcp_port": self.tcp_port,
            "serial_port": self.serial_port,
            "baudrate": self.baudrate,
            "timeout_ms": self.timeout_ms,
            "retries": self.retries,
            "retry_delay_s": self.retry_delay_s,
        }
        _set_optional(data, "port", self.port)
        _set_optional(data, "command_terminator", self.command_terminator)
        _set_optional(data, "identify_command", self.identify_command)
        _set_optional(data, "s11_command", self.s11_command)
        _set_optional(data, "s21_command", self.s21_command)
        _set_optional(data, "s12_command", self.s12_command)
        _set_optional(data, "s22_command", self.s22_command)
        return data


@dataclass(frozen=True)
class InstrumentConnectionConfig:
    vna: VnaConnectionConfig = field(default_factory=VnaConnectionConfig)
    positioner: PositionerConnectionConfig = field(default_factory=PositionerConnectionConfig)
    switch_box: SwitchBoxConnectionConfig = field(default_factory=SwitchBoxConnectionConfig)

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "InstrumentConnectionConfig":
        config = config or {}
        return cls(
            vna=VnaConnectionConfig.from_dict(config.get("vna", {})),
            positioner=PositionerConnectionConfig.from_dict(config.get("positioner", {})),
            switch_box=SwitchBoxConnectionConfig.from_dict(config.get("switch_box", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "vna": self.vna.to_dict(),
            "positioner": self.positioner.to_dict(),
            "switch_box": self.switch_box.to_dict(),
        }


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _set_optional(data: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        data[key] = value
