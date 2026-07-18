from __future__ import annotations

import numpy as np

from catr_loss_calibrator.hardware.interfaces import InstrumentInfo, SParameterTrace


class MockVna:
    def __init__(self, resource: str = "MOCK::VNA", model: str = "MOCK-VNA") -> None:
        self.resource = resource
        self.model = model
        self._connected = False
        self._start_hz = 10e9
        self._stop_hz = 17e9
        self._points = 71
        self._power_dbm = -10.0
        self._if_bandwidth_hz = 1000.0
        self._parameter = "S21"
        self._continuous_sweep = False
        self.commands: list[str] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> InstrumentInfo:
        self._connected = True
        return InstrumentInfo(resource=self.resource, model=self.model)

    def disconnect(self) -> None:
        self._connected = False

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        self._start_hz = start_hz
        self._stop_hz = stop_hz
        self._points = points

    def configure_power(self, power_dbm: float) -> None:
        self._power_dbm = power_dbm

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        self._if_bandwidth_hz = bandwidth_hz

    def configure_measurement_parameter(self, parameter: str) -> None:
        self._parameter = parameter.upper()

    def configure_continuous_sweep(self, enabled: bool) -> None:
        self._continuous_sweep = enabled

    def query_sweep_time_s(self) -> float:
        return max(self._points, 1) / max(self._if_bandwidth_hz, 1.0)

    def measure_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        self.trigger_sweep(parameter)
        return self.read_s_parameter(parameter)

    def trigger_sweep(self, parameter: str = "S21") -> None:
        self._parameter = parameter.upper()

    def read_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        frequency = np.linspace(self._start_hz, self._stop_hz, self._points)
        value_db = np.linspace(-1.0, -2.0, self._points)
        phase = np.zeros(self._points)
        return SParameterTrace(frequency, value_db, phase, parameter.upper())

    def send_command(self, command: str) -> str:
        if not self._connected:
            raise RuntimeError("Mock VNA is not connected.")
        self.commands.append(command)
        upper = command.strip().upper()
        if upper == "*IDN?":
            return f"MOCK,{self.model},0001,1.0"
        if upper.endswith("?"):
            return "0"
        return "OK"


class MockScpiInstrument:
    def __init__(self, name: str, model: str, resource: str | None = None) -> None:
        self.name = name
        self.model = model
        self.resource = resource or f"MOCK::{name}"
        self._connected = False
        self.commands: list[str] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> InstrumentInfo:
        self._connected = True
        return InstrumentInfo(resource=self.resource, model=self.model)

    def disconnect(self) -> None:
        self._connected = False

    def send_command(self, command: str) -> str:
        if not self._connected:
            raise RuntimeError(f"Mock {self.name} is not connected.")
        self.commands.append(command)
        upper = command.strip().upper()
        if upper == "*IDN?":
            return f"MOCK,{self.model},0001,1.0"
        if upper.endswith("?"):
            return "0"
        return "OK"


class MockLinkBox:
    def __init__(self, resource: str = "MOCK::LINKBOX", model: str = "LCD74000F-MOCK") -> None:
        self.resource = resource
        self.model = model
        self._connected = False
        self.commands: list[str] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> InstrumentInfo:
        self._connected = True
        return InstrumentInfo(resource=self.resource, model=self.model)

    def disconnect(self) -> None:
        self._connected = False

    def send_command(self, command: str) -> str:
        if not self._connected:
            raise RuntimeError("Mock link box is not connected.")
        self.commands.append(command)
        upper = command.strip().upper()
        if upper == "*IDN?":
            return f"MOCK,{self.model},0001,1.0"
        if upper == "*OPC?":
            return "1"
        if upper == "SYSTEM:ERROR:COUNT?":
            return "0"
        if upper == "SYSTEM:ERROR:NEXT?":
            return "0,No error"
        return "OK"
