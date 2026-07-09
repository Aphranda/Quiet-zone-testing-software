from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass

import serial

from quiet_zone_tester.hardware.interfaces import InstrumentInfo
from quiet_zone_tester.domains.link_management import LinkRouter, switch_box_profile_from_commands

logger = logging.getLogger(__name__)


class Tc500SwitchBoxError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tc500SwitchBoxConfig:
    connection_type: str = "TCP/IP"
    ip_address: str = "192.168.1.120"
    tcp_port: int = 35
    serial_port: str = "COM3"
    baudrate: int = 115200
    timeout_ms: int = 1500
    command_terminator: str = "\r\n"
    identify_command: str = "PASSIVE"
    s11_command: str = "PASSIVE"
    s21_command: str = "PASSIVE"
    s12_command: str = "PASSIVE"
    s22_command: str = "PASSIVE"
    expected_tokens: tuple[str, ...] = ("DONE", "SUCCESSFUL")
    retries: int = 1
    retry_delay_s: float = 0.2
    serial_open_settle_s: float = 0.5


class Tc500SwitchBoxController:
    """TC500 RF switch box controller based on the vendor app's text commands."""

    def __init__(self, config: Tc500SwitchBoxConfig) -> None:
        self._config = config
        self._socket: socket.socket | None = None
        self._serial: serial.Serial | None = None
        self._connected = False
        self._selected_parameter: str | None = None
        self._selected_command: str | None = None

    def connect(self) -> InstrumentInfo:
        logger.info("Connecting TC500 switch box: %s", self._resource_name)
        if self.is_connected:
            self.disconnect()

        if self._is_serial:
            self._open_serial()
        else:
            self._open_tcp_socket()

        self._connected = True
        try:
            self._send_checked_command(self._config.identify_command)
        except Exception:
            self.disconnect()
            raise

        return InstrumentInfo(
            resource_name=self._resource_name,
            model="TC500 RF Switch Box",
            serial_number="UNKNOWN",
            is_mock=False,
        )

    def disconnect(self) -> None:
        logger.info("Disconnecting TC500 switch box: %s", self._resource_name)
        tcp_socket = self._socket
        serial_port = self._serial
        self._socket = None
        self._serial = None
        self._connected = False

        if tcp_socket is not None:
            try:
                tcp_socket.close()
            except Exception:
                logger.exception("Failed to close TC500 TCP socket.")
        if serial_port is not None:
            try:
                serial_port.close()
            except Exception:
                logger.exception("Failed to close TC500 serial port.")

    @property
    def is_connected(self) -> bool:
        if self._is_serial:
            return self._connected and self._serial is not None and self._serial.is_open
        return self._connected and self._socket is not None

    def select_s_parameter(self, parameter: str) -> str:
        self._ensure_connected()
        parameter = parameter.upper()
        command = self._command_for_parameter(parameter)

        response = self._send_checked_command(command)
        self._selected_parameter = parameter
        self._selected_command = command
        logger.info("TC500 switch box selected %s with command %s: %s", parameter, command, response)
        return command

    def send_command(self, command: str) -> str:
        self._ensure_connected()
        response = self._send_checked_command(command)
        logger.info("TC500 switch box executed command %s: %s", command, response)
        return response

    @property
    def _is_serial(self) -> bool:
        return self._config.connection_type.strip().upper() in {"SERIAL", "串口", "RS232", "RS485"}

    @property
    def _resource_name(self) -> str:
        if self._is_serial:
            return f"{self._config.serial_port} @ {self._config.baudrate}"
        return f"{self._config.ip_address}:{self._config.tcp_port}"

    def _open_tcp_socket(self) -> None:
        timeout_s = max(0.1, self._config.timeout_ms / 1000.0)
        try:
            self._socket = socket.create_connection(
                (self._config.ip_address, self._config.tcp_port),
                timeout=timeout_s,
            )
            self._socket.settimeout(timeout_s)
        except Exception as exc:
            raise Tc500SwitchBoxError(f"无法连接 TC500 TCP/IP {self._resource_name}: {exc}") from exc

    def _open_serial(self) -> None:
        try:
            self._serial = serial.Serial(
                port=self._config.serial_port,
                baudrate=self._config.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=max(0.1, self._config.timeout_ms / 1000.0),
                write_timeout=max(0.1, self._config.timeout_ms / 1000.0),
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            self._serial.dtr = False
            self._serial.rts = False
            time.sleep(max(0.0, self._config.serial_open_settle_s))
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
        except Exception as exc:
            raise Tc500SwitchBoxError(f"无法打开 TC500 串口 {self._resource_name}: {exc}") from exc

    def _send_checked_command(self, command: str) -> str:
        command = command.strip().upper()
        if not command:
            raise Tc500SwitchBoxError("TC500 命令不能为空。")

        attempts = max(1, self._config.retries + 1)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                logger.info("Sending TC500 command %s attempt %s/%s.", command, attempt, attempts)
                response = self._send_command_once(command)
                if self._is_success_response(response):
                    return response
                raise Tc500SwitchBoxError(f"TC500 命令 {command} 未收到成功响应：{response or '<empty>'}")
            except Exception as exc:
                last_error = exc
                logger.warning("TC500 command failed: command=%s attempt=%s/%s error=%s", command, attempt, attempts, exc)
                if attempt < attempts:
                    time.sleep(self._config.retry_delay_s)

        raise Tc500SwitchBoxError(f"TC500 命令 {command} 执行失败：{last_error}") from last_error

    def _send_command_once(self, command: str) -> str:
        payload = f"{command}{self._config.command_terminator}".encode("ascii", errors="ignore")
        if self._is_serial:
            return self._send_serial_once(payload)
        return self._send_tcp_once(payload)

    def _send_tcp_once(self, payload: bytes) -> str:
        if self._socket is None:
            raise Tc500SwitchBoxError("TC500 TCP/IP 连接未打开。")

        self._socket.sendall(payload)
        return self._read_socket_response()

    def _send_serial_once(self, payload: bytes) -> str:
        if self._serial is None or not self._serial.is_open:
            raise Tc500SwitchBoxError("TC500 串口未打开。")

        self._serial.write(payload)
        self._serial.flush()
        return self._read_serial_response()

    def _read_socket_response(self) -> str:
        if self._socket is None:
            return ""

        chunks: list[bytes] = []
        while True:
            try:
                chunk = self._socket.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
            if chunk.endswith((b"\n", b"\r")) or self._is_success_response_bytes(b"".join(chunks)):
                break
        return b"".join(chunks).decode("utf-8", errors="replace").strip()

    def _read_serial_response(self) -> str:
        if self._serial is None:
            return ""

        deadline = time.monotonic() + max(0.1, self._config.timeout_ms / 1000.0)
        chunks: list[bytes] = []
        while time.monotonic() < deadline:
            waiting = self._serial.in_waiting
            if waiting:
                chunk = self._serial.read(waiting)
                chunks.append(chunk)
                payload = b"".join(chunks)
                if chunk.endswith((b"\n", b"\r")) or self._is_success_response_bytes(payload):
                    break
            else:
                time.sleep(0.01)
        return b"".join(chunks).decode("utf-8", errors="replace").strip()

    def _is_success_response(self, response: str) -> bool:
        normalized = response.upper()
        return any(token.upper() in normalized for token in self._config.expected_tokens)

    def _is_success_response_bytes(self, response: bytes) -> bool:
        return self._is_success_response(response.decode("utf-8", errors="ignore"))

    def _command_for_parameter(self, parameter: str) -> str:
        profile = switch_box_profile_from_commands(
            "TC500",
            s11_command=self._config.s11_command,
            s21_command=self._config.s21_command,
            s12_command=self._config.s12_command,
            s22_command=self._config.s22_command,
        )
        return LinkRouter(profile).resolve(parameter).command

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError("TC500 switch box is not connected.")
