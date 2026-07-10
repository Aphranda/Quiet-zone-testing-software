from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass

import serial

from quiet_zone_tester.hardware.interfaces import InstrumentInfo
from quiet_zone_tester.domains.link_management import LinkRouter, switch_box_profile_from_commands
from quiet_zone_tester.shared.instrument_defaults import (
    DEFAULT_SWITCH_BOX_BAUDRATE,
    DEFAULT_SWITCH_BOX_CONNECTION_TYPE,
    DEFAULT_SWITCH_BOX_SERIAL_PORT,
    switch_box_model_defaults,
)

logger = logging.getLogger(__name__)


class Lcd74000fSwitchBoxError(RuntimeError):
    pass


@dataclass(frozen=True)
class Lcd74000fSwitchBoxConfig:
    connection_type: str = DEFAULT_SWITCH_BOX_CONNECTION_TYPE
    ip_address: str = switch_box_model_defaults("LCD74000F").ip_address
    tcp_port: int = switch_box_model_defaults("LCD74000F").tcp_port
    serial_port: str = DEFAULT_SWITCH_BOX_SERIAL_PORT
    baudrate: int = DEFAULT_SWITCH_BOX_BAUDRATE
    timeout_ms: int = switch_box_model_defaults("LCD74000F").timeout_ms
    command_terminator: str = "\n"
    identify_command: str = "*IDN?"
    s11_command: str = "CONFigure:LINK H,VNA1"
    s21_command: str = "CONFigure:LINK H,VNA1"
    s12_command: str = "CONFigure:LINK V,VNA1"
    s22_command: str = "CONFigure:LINK V,VNA1"
    retries: int = 1
    retry_delay_s: float = 0.2
    serial_open_settle_s: float = 0.3


class Lcd74000fSwitchBoxController:
    """LCD74000F switch box controller using the documented SCPI link commands."""

    def __init__(self, config: Lcd74000fSwitchBoxConfig) -> None:
        self._config = config
        self._socket: socket.socket | None = None
        self._serial: serial.Serial | None = None
        self._connected = False
        self._idn = "UNKNOWN"
        self._selected_parameter: str | None = None
        self._selected_command: str | None = None

    def connect(self) -> InstrumentInfo:
        logger.info("Connecting LCD74000F switch box: %s", self._resource_name)
        if self.is_connected:
            self.disconnect()

        if self._is_serial:
            self._open_serial()
        else:
            self._open_tcp_socket()

        self._connected = True
        try:
            self._idn = self._query_checked(self._config.identify_command)
        except Exception:
            self.disconnect()
            raise

        return InstrumentInfo(
            resource_name=self._resource_name,
            model=f"LCD74000F RF Switch Box {self._idn}".strip(),
            serial_number="UNKNOWN",
            is_mock=False,
        )

    def disconnect(self) -> None:
        logger.info("Disconnecting LCD74000F switch box: %s", self._resource_name)
        tcp_socket = self._socket
        serial_port = self._serial
        self._socket = None
        self._serial = None
        self._connected = False

        if tcp_socket is not None:
            try:
                tcp_socket.close()
            except Exception:
                logger.exception("Failed to close LCD74000F TCP socket.")
        if serial_port is not None:
            try:
                serial_port.close()
            except Exception:
                logger.exception("Failed to close LCD74000F serial port.")

    @property
    def is_connected(self) -> bool:
        if self._is_serial:
            return self._connected and self._serial is not None and self._serial.is_open
        return self._connected and self._socket is not None

    def select_s_parameter(self, parameter: str) -> str:
        self._ensure_connected()
        parameter = parameter.upper()
        command = self._command_for_parameter(parameter)

        self._write_checked(command)
        self._selected_parameter = parameter
        self._selected_command = command
        logger.info("LCD74000F switch box selected %s with command %s.", parameter, command)
        return command

    def send_command(self, command: str) -> str:
        self._ensure_connected()
        command = command.strip()
        self._write_checked(command)
        logger.info("LCD74000F switch box executed command %s.", command)
        return command

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
            raise Lcd74000fSwitchBoxError(f"无法连接 LCD74000F TCP/IP {self._resource_name}: {exc}") from exc

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
            time.sleep(max(0.0, self._config.serial_open_settle_s))
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
        except Exception as exc:
            raise Lcd74000fSwitchBoxError(f"无法打开 LCD74000F 串口 {self._resource_name}: {exc}") from exc

    def _write_checked(self, command: str) -> None:
        command = command.strip()
        if not command:
            raise Lcd74000fSwitchBoxError("LCD74000F 命令不能为空。")

        attempts = max(1, self._config.retries + 1)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                logger.info("Sending LCD74000F command %s attempt %s/%s.", command, attempt, attempts)
                self._write_once(command)
                opc = self._query_once("*OPC?")
                if opc.strip() not in {"", "1"}:
                    raise Lcd74000fSwitchBoxError(f"LCD74000F *OPC? 返回异常：{opc}")
                self._raise_for_error_queue()
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LCD74000F command failed: command=%s attempt=%s/%s error=%s",
                    command,
                    attempt,
                    attempts,
                    exc,
                )
                if attempt < attempts:
                    time.sleep(self._config.retry_delay_s)

        raise Lcd74000fSwitchBoxError(f"LCD74000F 命令 {command} 执行失败：{last_error}") from last_error

    def _query_checked(self, command: str) -> str:
        command = command.strip()
        if not command:
            raise Lcd74000fSwitchBoxError("LCD74000F 查询命令不能为空。")

        attempts = max(1, self._config.retries + 1)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = self._query_once(command)
                if response:
                    return response
                raise Lcd74000fSwitchBoxError(f"LCD74000F 查询 {command} 未收到响应。")
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LCD74000F query failed: command=%s attempt=%s/%s error=%s",
                    command,
                    attempt,
                    attempts,
                    exc,
                )
                if attempt < attempts:
                    time.sleep(self._config.retry_delay_s)

        raise Lcd74000fSwitchBoxError(f"LCD74000F 查询 {command} 失败：{last_error}") from last_error

    def _raise_for_error_queue(self) -> None:
        try:
            count = self._query_once("SYSTem:ERRor:COUNt?").strip()
            if count in {"", "0"}:
                return
            error = self._query_once("SYSTem:ERRor:NEXT?")
            raise Lcd74000fSwitchBoxError(f"LCD74000F 错误队列：{error or count}")
        except Lcd74000fSwitchBoxError:
            raise
        except Exception:
            logger.debug("LCD74000F error queue query is unavailable.", exc_info=True)

    def _write_once(self, command: str) -> None:
        payload = f"{command}{self._config.command_terminator}".encode("ascii", errors="ignore")
        if self._is_serial:
            self._write_serial(payload)
        else:
            self._write_tcp(payload)

    def _query_once(self, command: str) -> str:
        self._write_once(command)
        if self._is_serial:
            return self._read_serial_response()
        return self._read_socket_response()

    def _write_tcp(self, payload: bytes) -> None:
        if self._socket is None:
            raise Lcd74000fSwitchBoxError("LCD74000F TCP/IP 连接未打开。")
        self._socket.sendall(payload)

    def _write_serial(self, payload: bytes) -> None:
        if self._serial is None or not self._serial.is_open:
            raise Lcd74000fSwitchBoxError("LCD74000F 串口未打开。")
        self._serial.write(payload)
        self._serial.flush()

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
            if chunk.endswith((b"\n", b"\r")):
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
                if chunk.endswith((b"\n", b"\r")):
                    break
            else:
                time.sleep(0.01)
        return b"".join(chunks).decode("utf-8", errors="replace").strip()

    def _command_for_parameter(self, parameter: str) -> str:
        profile = switch_box_profile_from_commands(
            "LCD74000F",
            s11_command=self._config.s11_command,
            s21_command=self._config.s21_command,
            s12_command=self._config.s12_command,
            s22_command=self._config.s22_command,
        )
        return LinkRouter(profile).resolve(parameter).command

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError("LCD74000F switch box is not connected.")
