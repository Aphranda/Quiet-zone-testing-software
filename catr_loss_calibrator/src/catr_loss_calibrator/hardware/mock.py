from __future__ import annotations

import numpy as np

from catr_loss_calibrator.hardware.interfaces import InstrumentInfo, SParameterTrace


class MockVna:
    def __init__(self) -> None:
        self._connected = False
        self._start_hz = 10e9
        self._stop_hz = 15e9
        self._points = 51

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> InstrumentInfo:
        self._connected = True
        return InstrumentInfo(resource="MOCK::VNA", model="MOCK-VNA")

    def disconnect(self) -> None:
        self._connected = False

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        self._start_hz = start_hz
        self._stop_hz = stop_hz
        self._points = points

    def configure_power(self, power_dbm: float) -> None:
        _ = power_dbm

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        _ = bandwidth_hz

    def trigger_sweep(self, parameter: str = "S21") -> None:
        _ = parameter

    def read_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        frequency = np.linspace(self._start_hz, self._stop_hz, self._points)
        value_db = np.linspace(-1.0, -2.0, self._points)
        phase = np.zeros(self._points)
        return SParameterTrace(frequency, value_db, phase, parameter)


class MockLinkBox:
    def __init__(self) -> None:
        self._connected = False
        self.commands: list[str] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> InstrumentInfo:
        self._connected = True
        return InstrumentInfo(resource="MOCK::LINKBOX", model="LCD74000F-MOCK")

    def disconnect(self) -> None:
        self._connected = False

    def send_command(self, command: str) -> str:
        if not self._connected:
            raise RuntimeError("Mock link box is not connected.")
        self.commands.append(command)
        return "OK"
