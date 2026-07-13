from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import serial

from quiet_zone_tester.shared.instrument_defaults import (
    DEFAULT_POSITIONER_BAUDRATE,
    DEFAULT_POSITIONER_BYTESIZE,
    DEFAULT_POSITIONER_PARITY,
    DEFAULT_POSITIONER_RETRIES,
    DEFAULT_POSITIONER_RETRY_DELAY_S,
    DEFAULT_POSITIONER_STOPBITS,
)

logger = logging.getLogger(__name__)


class ModbusRtuError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModbusRtuConfig:
    port: str
    baudrate: int = DEFAULT_POSITIONER_BAUDRATE
    bytesize: int = DEFAULT_POSITIONER_BYTESIZE
    parity: str = DEFAULT_POSITIONER_PARITY
    stopbits: int = DEFAULT_POSITIONER_STOPBITS
    timeout_s: float = 1.0
    retries: int = DEFAULT_POSITIONER_RETRIES
    retry_delay_s: float = DEFAULT_POSITIONER_RETRY_DELAY_S


class ModbusRtuSession:
    def __init__(self, config: ModbusRtuConfig) -> None:
        self._config = config
        self._serial: serial.Serial | None = None
        self._lock = threading.RLock()

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def open(self) -> None:
        if self.is_open:
            return

        try:
            logger.info("Opening Modbus RTU port: %s", self._config.port)
            self._serial = serial.Serial(
                port=self._config.port,
                baudrate=self._config.baudrate,
                bytesize=self._config.bytesize,
                parity=self._config.parity,
                stopbits=self._config.stopbits,
                timeout=self._config.timeout_s,
                write_timeout=self._config.timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 - serial backend errors are wrapped here.
            logger.exception("Failed to open Modbus RTU port: %s", self._config.port)
            raise ModbusRtuError(f"Failed to open serial port {self._config.port}: {exc}") from exc

    def close(self) -> None:
        port = self._serial
        self._serial = None
        if port is None:
            return

        try:
            logger.info("Closing Modbus RTU port: %s", self._config.port)
            port.close()
        except Exception:
            logger.exception("Failed while closing Modbus RTU port: %s", self._config.port)

    def clear(self) -> None:
        with self._lock:
            port = self._require_serial()
            port.reset_input_buffer()
            port.reset_output_buffer()

    def transact(self, payload: bytes, expected_min_length: int = 5) -> bytes:
        attempts = max(1, self._config.retries + 1)
        last_error: Exception | None = None
        frame = payload + self.crc16(payload).to_bytes(2, byteorder="little")

        with self._lock:
            for attempt in range(1, attempts + 1):
                try:
                    port = self._require_serial()
                    logger.debug("Modbus RTU write attempt %s/%s: %s", attempt, attempts, frame.hex(" "))
                    port.reset_input_buffer()
                    port.write(frame)
                    port.flush()
                    response = self._read_response_frame(port, expected_min_length)
                    self._validate_response(response)
                    logger.debug("Modbus RTU read: %s", response.hex(" "))
                    return response
                except Exception as exc:  # noqa: BLE001 - retry boundary.
                    last_error = exc
                    logger.warning(
                        "Modbus RTU transaction failed on %s attempt %s/%s: payload=%s error=%s",
                        self._config.port,
                        attempt,
                        attempts,
                        payload.hex(" "),
                        exc,
                    )
                    if attempt < attempts:
                        try:
                            self._require_serial().reset_input_buffer()
                        except Exception:
                            logger.debug("Failed to clear Modbus input buffer before retry.", exc_info=True)
                        time.sleep(self._config.retry_delay_s)

        raise ModbusRtuError(
            f"Modbus RTU transaction failed after {attempts} attempt(s): {last_error}"
        ) from last_error

    def _require_serial(self) -> serial.Serial:
        if self._serial is None or not self._serial.is_open:
            raise ModbusRtuError(f"Serial port is not open: {self._config.port}")
        return self._serial

    def _read_response_frame(self, port: serial.Serial, expected_min_length: int) -> bytes:
        deadline = time.monotonic() + max(float(self._config.timeout_s), 0.001)
        response = bytearray()
        minimum = max(int(expected_min_length), 5)

        while len(response) < 2:
            response.extend(self._read_available(port, deadline, 1))

        function = response[1]
        if function & 0x80:
            expected_length = 5
        elif function in (0x03, 0x04):
            while len(response) < 3:
                response.extend(self._read_available(port, deadline, 1))
            expected_length = 3 + int(response[2]) + 2
        elif function in (0x05, 0x06, 0x10):
            expected_length = 8
        else:
            expected_length = minimum

        expected_length = max(expected_length, minimum)
        while len(response) < expected_length:
            response.extend(self._read_available(port, deadline, expected_length - len(response)))

        return bytes(response)

    def _read_available(self, port: serial.Serial, deadline: float, requested: int) -> bytes:
        while time.monotonic() <= deadline:
            chunk = port.read(max(1, int(requested)))
            if chunk:
                return chunk
        raise ModbusRtuError(f"Modbus response timeout after {self._config.timeout_s:.3f} s.")

    @classmethod
    def _validate_response(cls, response: bytes) -> None:
        if len(response) < 5:
            raise ModbusRtuError(f"Modbus response too short: {response.hex(' ')}")
        body = response[:-2]
        received_crc = int.from_bytes(response[-2:], byteorder="little")
        expected_crc = cls.crc16(body)
        if received_crc != expected_crc:
            raise ModbusRtuError(
                f"Modbus CRC mismatch: received=0x{received_crc:04X} expected=0x{expected_crc:04X}"
            )
        function = response[1]
        if function & 0x80:
            raise ModbusRtuError(f"Modbus exception response: {response.hex(' ')}")

    @staticmethod
    def crc16(data: bytes) -> int:
        crc = 0xFFFF
        for value in data:
            crc ^= value
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF
