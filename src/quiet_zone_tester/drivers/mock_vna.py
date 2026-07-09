from __future__ import annotations

import logging
import time

import numpy as np

from quiet_zone_tester.drivers.base import InstrumentInfo
from quiet_zone_tester.models import SParameterTrace

logger = logging.getLogger(__name__)


class MockVnaController:
    """Mock VNA that waits for timeout and returns zeroed traces."""

    def __init__(self, timeout_ms: int = 5000) -> None:
        self._connected = False
        self._start_hz = 10.0e9
        self._stop_hz = 17.0e9
        self._points = 801
        self._power_dbm = -10.0
        self._if_bandwidth_hz = 1000.0
        self._parameter = "S21"
        self._timeout_s = max(timeout_ms / 1000.0, 0.001)

    def connect(self) -> InstrumentInfo:
        logger.info("Connecting mock VNA.")
        time.sleep(0.35)
        self._connected = True
        return InstrumentInfo(
            resource_name="MOCK::VNA::001",
            model="Mock Vector Network Analyzer",
            serial_number="VNA-MOCK-001",
            is_mock=True,
        )

    def disconnect(self) -> None:
        logger.info("Disconnecting mock VNA.")
        time.sleep(0.1)
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        self._ensure_connected()
        if start_hz <= 0 or stop_hz <= start_hz:
            raise ValueError("Invalid sweep range.")
        if points < 2:
            raise ValueError("Sweep points must be greater than 1.")

        logger.info(
            "Configuring mock VNA sweep: start=%s Hz, stop=%s Hz, points=%s",
            start_hz,
            stop_hz,
            points,
        )
        time.sleep(0.12)
        self._start_hz = start_hz
        self._stop_hz = stop_hz
        self._points = points

    def configure_power(self, power_dbm: float) -> None:
        self._ensure_connected()
        if not -90.0 <= power_dbm <= 30.0:
            raise ValueError("Mock VNA power must be between -90 dBm and 30 dBm.")

        logger.info("Configuring mock VNA power: %.2f dBm", power_dbm)
        time.sleep(0.05)
        self._power_dbm = power_dbm

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        self._ensure_connected()
        if bandwidth_hz <= 0.0:
            raise ValueError("Mock VNA IF bandwidth must be greater than 0 Hz.")

        logger.info("Configuring mock VNA IF bandwidth: %.3f Hz", bandwidth_hz)
        time.sleep(0.03)
        self._if_bandwidth_hz = bandwidth_hz

    def configure_measurement_parameter(self, parameter: str) -> None:
        self._ensure_connected()
        parameter = parameter.upper()
        logger.info("Configuring mock VNA measurement parameter: %s", parameter)
        self._parameter = parameter

    def measure_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        self._ensure_connected()
        parameter = (parameter or self._parameter).upper()
        self._parameter = parameter
        logger.info("Measuring mock %s trace.", parameter)
        time.sleep(self._timeout_s)

        freq_hz = np.linspace(self._start_hz, self._stop_hz, self._points)
        complex_values = np.zeros(freq_hz.shape, dtype=complex)
        return SParameterTrace(freq_hz, complex_values, parameter)

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Mock VNA is not connected.")
