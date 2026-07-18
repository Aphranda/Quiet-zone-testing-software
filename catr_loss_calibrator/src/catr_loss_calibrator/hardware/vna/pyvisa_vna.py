from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from catr_loss_calibrator.hardware.interfaces import InstrumentInfo, SParameterTrace, Vna


@dataclass
class PyVisaVna(Vna):
    resource: str
    model: str = "UNKNOWN"
    timeout_ms: int = 10_000

    def __post_init__(self) -> None:
        self._connected = False
        self._resource = None
        self._start_hz = 10e9
        self._stop_hz = 15e9
        self._points = 51
        self._power_dbm = -10.0
        self._ifbw_hz = 1000.0

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> InstrumentInfo:
        try:
            import pyvisa
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pyvisa is required for PyVisaVna.") from exc
        rm = pyvisa.ResourceManager()
        self._resource = rm.open_resource(self.resource)
        self._resource.timeout = self.timeout_ms
        self._connected = True
        idn = self._query("*IDN?")
        return InstrumentInfo(resource=self.resource, model=idn.split(",")[1] if "," in idn else self.model)

    def disconnect(self) -> None:
        if self._resource is not None:
            try:
                self._resource.close()
            finally:
                self._resource = None
        self._connected = False

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        self._start_hz = start_hz
        self._stop_hz = stop_hz
        self._points = points
        self._write(f"SENS:FREQ:STAR {start_hz}")
        self._write(f"SENS:FREQ:STOP {stop_hz}")
        self._write(f"SENS:SWE:POIN {points}")

    def configure_power(self, power_dbm: float) -> None:
        self._power_dbm = power_dbm
        self._write(f"SOUR:POW {power_dbm}")

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        self._ifbw_hz = bandwidth_hz
        self._write(f"SENS:BAND {bandwidth_hz}")

    def trigger_sweep(self, parameter: str = "S21") -> None:
        self._write(f"CALC:PAR:DEF 'TRC1',{parameter}")
        self._write("INIT:IMM")
        self._write("*WAI")

    def read_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        if not self.is_connected:
            raise RuntimeError("VNA is not connected.")
        frequency = np.linspace(self._start_hz, self._stop_hz, self._points)
        value_db = np.zeros(self._points)
        phase = np.zeros(self._points)
        return SParameterTrace(frequency, value_db, phase, parameter)

    def send_command(self, command: str) -> str:
        if command.strip().endswith("?"):
            return self._query(command)
        self._write(command)
        return "OK"

    def _write(self, command: str) -> None:
        if self._resource is None:
            raise RuntimeError("VNA is not connected.")
        self._resource.write(command)

    def _query(self, command: str) -> str:
        if self._resource is None:
            raise RuntimeError("VNA is not connected.")
        return str(self._resource.query(command))
