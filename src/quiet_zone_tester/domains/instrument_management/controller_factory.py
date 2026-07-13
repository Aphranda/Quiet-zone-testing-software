from __future__ import annotations

from dataclasses import dataclass

from quiet_zone_tester.hardware import (
    MockPositionerController,
    MockSwitchBoxController,
    MockVnaController,
    PositionerController,
    SwitchBoxController,
    VnaController,
)
from quiet_zone_tester.hardware import (
    IclPositionerConfig,
    IclPositionerController,
    Lcd74000fSwitchBoxConfig,
    Lcd74000fSwitchBoxController,
    ScpiVnaController,
    Tc500SwitchBoxConfig,
    Tc500SwitchBoxController,
    VnaScpiConfig,
)
from quiet_zone_tester.shared.instrument_defaults import (
    DEFAULT_POSITIONER_BAUDRATE,
    DEFAULT_POSITIONER_BYTESIZE,
    DEFAULT_POSITIONER_PARITY,
    DEFAULT_POSITIONER_PULSES_PER_MM,
    DEFAULT_POSITIONER_RETRIES,
    DEFAULT_POSITIONER_RETRY_DELAY_S,
    DEFAULT_POSITIONER_SPEED_MM_S,
    DEFAULT_POSITIONER_STOPBITS,
    DEFAULT_POSITIONER_TIMEOUT_MS,
    DEFAULT_POSITIONER_X_AXIS,
    DEFAULT_POSITIONER_Y_AXIS,
    DEFAULT_SWITCH_BOX_BAUDRATE,
    DEFAULT_SWITCH_BOX_CONNECTION_TYPE,
    DEFAULT_SWITCH_BOX_MODEL,
    DEFAULT_SWITCH_BOX_SERIAL_PORT,
    DEFAULT_VNA_PORT,
    DEFAULT_VNA_TIMEOUT_MS,
    MAX_POSITIONER_SPEED_MM_S,
    SUPPORTED_VNA_MODELS,
    switch_box_model_defaults,
)


class InstrumentControllerFactoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstrumentControllerFactory:
    def create_vna(self, config: dict) -> VnaController:
        if self.virtual_enabled(config):
            return MockVnaController(timeout_ms=int(config.get("timeout_ms", DEFAULT_VNA_TIMEOUT_MS)))

        resource_name = str(config.get("resource_name", "")).strip()
        if not resource_name:
            ip_address = str(config.get("ip_address", "")).strip()
            port = int(config.get("port", DEFAULT_VNA_PORT))
            if ip_address:
                resource_name = f"TCPIP0::{ip_address}::{port}::SOCKET"

        if not resource_name:
            raise InstrumentControllerFactoryError("VNA VISA 资源不能为空，真实测试模式需要填写仪器资源。")
        if resource_name.upper().startswith("MOCK"):
            raise InstrumentControllerFactoryError("当前为真实测试模式，VNA 不能使用 MOCK 资源。")

        model = str(config.get("model", "")).strip().upper()
        if model and model not in SUPPORTED_VNA_MODELS:
            raise InstrumentControllerFactoryError(f"不支持的网分型号：{model}。")

        return ScpiVnaController(
            VnaScpiConfig(
                resource_name=resource_name,
                timeout_ms=int(config.get("timeout_ms", DEFAULT_VNA_TIMEOUT_MS)),
                retries=int(config.get("retries", 2)),
                retry_delay_s=float(config.get("retry_delay_s", 0.2)),
                expected_model=model or None,
            )
        )

    def create_positioner(self, config: dict) -> PositionerController:
        if self.virtual_enabled(config):
            return MockPositionerController(
                x_axis=self.axis_from_config(config, "x_axis", DEFAULT_POSITIONER_X_AXIS),
                y_axis=self.axis_from_config(config, "y_axis", DEFAULT_POSITIONER_Y_AXIS),
            )

        port_name = str(config.get("port_name") or config.get("resource_name") or "").strip()
        if not port_name:
            raise InstrumentControllerFactoryError("扫描架串口不能为空，真实测试模式需要填写 COM 口。")
        if port_name.upper().startswith("MOCK"):
            raise InstrumentControllerFactoryError("当前为真实测试模式，扫描架不能使用 MOCK 资源。")

        legacy_pulses_per_mm, x_pulses_per_mm, y_pulses_per_mm = self.positioner_scales_from_config(config)

        default_speed = float(config.get("default_speed", DEFAULT_POSITIONER_SPEED_MM_S))
        if not 0.0 < default_speed <= MAX_POSITIONER_SPEED_MM_S:
            raise InstrumentControllerFactoryError(
                f"扫描架默认速度必须大于 0 且不能超过 {MAX_POSITIONER_SPEED_MM_S:g} mm/s。"
            )

        return IclPositionerController(
            IclPositionerConfig(
                port=port_name,
                baudrate=int(config.get("baudrate", DEFAULT_POSITIONER_BAUDRATE)),
                bytesize=int(config.get("bytesize", DEFAULT_POSITIONER_BYTESIZE)),
                parity=str(config.get("parity", DEFAULT_POSITIONER_PARITY)).strip().upper() or DEFAULT_POSITIONER_PARITY,
                stopbits=int(config.get("stopbits", DEFAULT_POSITIONER_STOPBITS)),
                timeout_ms=int(config.get("timeout_ms", DEFAULT_POSITIONER_TIMEOUT_MS)),
                retries=int(config.get("retries", DEFAULT_POSITIONER_RETRIES)),
                retry_delay_s=float(config.get("retry_delay_s", DEFAULT_POSITIONER_RETRY_DELAY_S)),
                x_axis=self.axis_from_config(config, "x_axis", DEFAULT_POSITIONER_X_AXIS),
                y_axis=self.axis_from_config(config, "y_axis", DEFAULT_POSITIONER_Y_AXIS),
                pulses_per_mm=legacy_pulses_per_mm,
                x_pulses_per_mm=x_pulses_per_mm,
                y_pulses_per_mm=y_pulses_per_mm,
                default_speed=default_speed,
            )
        )

    def create_switch_box(self, config: dict) -> SwitchBoxController:
        if self.virtual_enabled(config):
            return MockSwitchBoxController()

        model = str(config.get("model", DEFAULT_SWITCH_BOX_MODEL)).strip().upper()
        connection_type = str(config.get("connection_type", DEFAULT_SWITCH_BOX_CONNECTION_TYPE)).strip() or DEFAULT_SWITCH_BOX_CONNECTION_TYPE
        normalized_type = connection_type.upper()
        if normalized_type in {"SERIAL", "串口", "RS232", "RS485"}:
            serial_port = str(config.get("serial_port") or config.get("port_name") or "").strip()
            if not serial_port:
                raise InstrumentControllerFactoryError("开关箱串口不能为空，串口模式需要填写 COM 口。")
            if serial_port.upper().startswith("MOCK"):
                raise InstrumentControllerFactoryError("当前为真实测试模式，开关箱不能使用 MOCK 资源。")
        else:
            ip_address = str(config.get("ip_address", "")).strip()
            if not ip_address:
                raise InstrumentControllerFactoryError("开关箱 TCP/IP 地址不能为空。")
            serial_port = str(config.get("serial_port", DEFAULT_SWITCH_BOX_SERIAL_PORT)).strip()

        if model == "LCD74000F":
            defaults = switch_box_model_defaults(model)
            return Lcd74000fSwitchBoxController(
                Lcd74000fSwitchBoxConfig(
                    connection_type=connection_type,
                    ip_address=str(config.get("ip_address", defaults.ip_address)).strip(),
                    tcp_port=int(config.get("tcp_port", config.get("port", defaults.tcp_port))),
                    serial_port=serial_port,
                    baudrate=int(config.get("baudrate", DEFAULT_SWITCH_BOX_BAUDRATE)),
                    timeout_ms=int(config.get("timeout_ms", defaults.timeout_ms)),
                    command_terminator=str(config.get("command_terminator", "\n")),
                    identify_command=str(config.get("identify_command", "*IDN?")).strip(),
                    s11_command=str(config.get("s11_command", "CONFigure:LINK H,VNA1")).strip(),
                    s21_command=str(config.get("s21_command", "CONFigure:LINK H,VNA1")).strip(),
                    s12_command=str(config.get("s12_command", "CONFigure:LINK V,VNA1")).strip(),
                    s22_command=str(config.get("s22_command", "CONFigure:LINK V,VNA1")).strip(),
                    retries=int(config.get("retries", 1)),
                    retry_delay_s=float(config.get("retry_delay_s", 0.2)),
                )
            )

        defaults = switch_box_model_defaults(model)
        return Tc500SwitchBoxController(
            Tc500SwitchBoxConfig(
                connection_type=connection_type,
                ip_address=str(config.get("ip_address", defaults.ip_address)).strip(),
                tcp_port=int(config.get("tcp_port", config.get("port", defaults.tcp_port))),
                serial_port=serial_port,
                baudrate=int(config.get("baudrate", DEFAULT_SWITCH_BOX_BAUDRATE)),
                timeout_ms=int(config.get("timeout_ms", defaults.timeout_ms)),
                command_terminator=str(config.get("command_terminator", "\r\n")),
                identify_command=str(config.get("identify_command", "PASSIVE")).strip().upper(),
                s11_command=str(config.get("s11_command", "PASSIVE")).strip().upper(),
                s21_command=str(config.get("s21_command", "PASSIVE")).strip().upper(),
                s12_command=str(config.get("s12_command", "PASSIVE")).strip().upper(),
                s22_command=str(config.get("s22_command", "PASSIVE")).strip().upper(),
                retries=int(config.get("retries", 1)),
                retry_delay_s=float(config.get("retry_delay_s", 0.2)),
            )
        )

    def positioner_scales_from_config(self, config: dict) -> tuple[float, float, float]:
        legacy_pulses_per_mm = float(
            config.get(
                "pulses_per_mm",
                config.get("pulses_per_degree", DEFAULT_POSITIONER_PULSES_PER_MM),
            )
        )
        x_pulses_per_mm = self.axis_scale_from_config(
            config,
            "x_pulses_per_mm",
            "x_units_per_turn",
            "x_mm_per_turn",
            legacy_pulses_per_mm,
        )
        y_pulses_per_mm = self.axis_scale_from_config(
            config,
            "y_pulses_per_mm",
            "y_units_per_turn",
            "y_mm_per_turn",
            legacy_pulses_per_mm,
        )
        legacy_pulses_per_mm = x_pulses_per_mm
        if legacy_pulses_per_mm <= 0 or x_pulses_per_mm <= 0 or y_pulses_per_mm <= 0:
            raise InstrumentControllerFactoryError("扫描架每毫米电机单位必须大于 0。")
        return legacy_pulses_per_mm, x_pulses_per_mm, y_pulses_per_mm

    @staticmethod
    def axis_scale_from_config(
        config: dict,
        direct_key: str,
        units_per_turn_key: str,
        mm_per_turn_key: str,
        fallback: float,
    ) -> float:
        if units_per_turn_key in config and mm_per_turn_key in config:
            units_per_turn = float(config[units_per_turn_key])
            mm_per_turn = float(config[mm_per_turn_key])
            if mm_per_turn <= 0:
                raise InstrumentControllerFactoryError("扫描架每圈距离必须大于 0。")
            return units_per_turn / mm_per_turn
        return float(config.get(direct_key, fallback))

    @staticmethod
    def axis_from_config(config: dict, key: str, default_axis_id: int) -> int:
        raw_value = int(config.get(key, default_axis_id))
        if 0 <= raw_value <= 247:
            return raw_value
        raise InstrumentControllerFactoryError(f"扫描架轴号超出范围：{key}={raw_value}，有效范围为 0-247。")

    @staticmethod
    def virtual_enabled(config: dict) -> bool:
        value = config.get("virtual_enabled", False)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on", "虚拟连接", "虚拟"}
        return bool(value)
