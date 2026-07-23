from __future__ import annotations

import numpy as np

from catr_loss_calibrator.hardware.interfaces import InstrumentInfo, SParameterTrace
from catr_loss_calibrator.project.config import DEFAULT_VNA_POWER_DBM


class MockVna:
    def __init__(self, resource: str = "MOCK::VNA", model: str = "MOCK-VNA") -> None:
        self.resource = resource
        self.model = model
        self._connected = False
        self._start_hz = 10e9
        self._stop_hz = 17e9
        self._points = 71
        self._power_dbm = DEFAULT_VNA_POWER_DBM
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
        self.settings: dict[str, str] = {
            "frequency_cw": "10000000000",
            "power_level": "-10",
            "output_state": "0",
            "center_frequency": "10000000000",
            "span": "100000000",
            "points": "1001",
            "rbw": "1000000",
            "vbw": "1000000",
            "reference_level": "0",
            "attenuation": "10",
            "preamp_state": "0",
            "continuous": "0",
            "marker_frequency": "10000000000",
            "marker_power": "-42.0",
        }

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
        if upper == "*OPC?":
            return "1"
        specific_response = self._handle_common_scpi(command)
        if specific_response is not None:
            return specific_response
        if upper.endswith("?"):
            return "0"
        return "OK"

    def _handle_common_scpi(self, command: str) -> str | None:
        normalized = command.strip()
        upper = normalized.upper()
        value = self._command_value(normalized)

        query_map = {
            "FREQUENCY:CW?": "frequency_cw",
            "FREQ:CW?": "frequency_cw",
            "POWER:LEVEL?": "power_level",
            "POW:LEV?": "power_level",
            "OUTPUT:STATE?": "output_state",
            "OUTP:STAT?": "output_state",
            "FREQUENCY:CENTER?": "center_frequency",
            "FREQ:CENT?": "center_frequency",
            "FREQUENCY:SPAN?": "span",
            "FREQ:SPAN?": "span",
            "SWEEP:POINTS?": "points",
            "SWE:POIN?": "points",
            "BANDWIDTH:RESOLUTION?": "rbw",
            "BAND:RES?": "rbw",
            "BANDWIDTH:VIDEO?": "vbw",
            "BAND:VID?": "vbw",
            "CALCULATE:MARKER1:X?": "marker_frequency",
            "CALC:MARK1:X?": "marker_frequency",
            "CALCULATE:MARKER1:Y?": "marker_power",
            "CALC:MARK1:Y?": "marker_power",
        }
        if upper in query_map:
            return self.settings[query_map[upper]]
        if upper in {"SYSTEM:ERROR?", "SYSTEM:ERROR:NEXT?", "SYST:ERR?", "SYST:ERR:NEXT?"}:
            return "0,No error"

        write_prefixes = (
            ("FREQUENCY:CW ", "frequency_cw"),
            ("FREQ:CW ", "frequency_cw"),
            ("POWER:LEVEL ", "power_level"),
            ("POW:LEV ", "power_level"),
            ("FREQUENCY:CENTER ", "center_frequency"),
            ("FREQ:CENT ", "center_frequency"),
            ("FREQUENCY:SPAN ", "span"),
            ("FREQ:SPAN ", "span"),
            ("SWEEP:POINTS ", "points"),
            ("SWE:POIN ", "points"),
            ("BANDWIDTH:RESOLUTION ", "rbw"),
            ("BAND:RES ", "rbw"),
            ("BANDWIDTH:VIDEO ", "vbw"),
            ("BAND:VID ", "vbw"),
            ("DISPLAY:WINDOW:TRACE:Y:RLEVEL ", "reference_level"),
            ("DISP:WIND:TRAC:Y:RLEV ", "reference_level"),
            ("POWER:ATTENUATION ", "attenuation"),
            ("POW:ATT ", "attenuation"),
        )
        for prefix, key in write_prefixes:
            if upper.startswith(prefix) and value:
                self.settings[key] = value
                return "OK"
        if upper.startswith("OUTPUT:STATE ") or upper.startswith("OUTP:STAT "):
            self.settings["output_state"] = self._state_value(value)
            return "OK"
        if upper.startswith("POWER:GAIN:STATE ") or upper.startswith("POW:GAIN:STAT "):
            self.settings["preamp_state"] = self._state_value(value)
            return "OK"
        if upper.startswith("INITIATE:CONTINUOUS ") or upper.startswith("INIT:CONT "):
            self.settings["continuous"] = self._state_value(value)
            return "OK"
        if upper in {"CALCULATE:MARKER1:MAXIMUM", "CALC:MARK1:MAX"}:
            self.settings["marker_frequency"] = self.settings["center_frequency"]
            return "OK"
        return None

    @staticmethod
    def _command_value(command: str) -> str:
        parts = command.strip().split(maxsplit=1)
        return parts[1].strip() if len(parts) == 2 else ""

    @staticmethod
    def _state_value(value: str) -> str:
        normalized = value.strip().upper()
        if normalized in {"ON", "1", "TRUE"}:
            return "1"
        if normalized in {"OFF", "0", "FALSE"}:
            return "0"
        return normalized


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
