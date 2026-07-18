from __future__ import annotations

from dataclasses import dataclass
import re

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
        self._trace_name = "CH1_SPARAM"
        self._selected_parameter: str | None = None

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
        if start_hz <= 0 or stop_hz <= start_hz:
            raise ValueError("Invalid VNA sweep frequency range.")
        if points < 2:
            raise ValueError("VNA sweep points must be greater than 1.")
        self._prepare_for_reconfiguration()
        self._write(f"SENS:FREQ:STAR {start_hz:.12g}")
        self._write(f"SENS:FREQ:STOP {stop_hz:.12g}")
        self._write(f"SENS:SWE:POIN {points}")
        self._wait_for_operation_complete()
        self._raise_for_system_error()
        self._start_hz = start_hz
        self._stop_hz = stop_hz
        self._points = points

    def configure_power(self, power_dbm: float) -> None:
        if not -90.0 <= power_dbm <= 30.0:
            raise ValueError("VNA power must be between -90 dBm and 30 dBm.")
        self._prepare_for_reconfiguration()
        self._write(f"SOUR:POW {power_dbm:.6g}")
        self._wait_for_operation_complete()
        self._raise_for_system_error()
        self._power_dbm = power_dbm

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        if bandwidth_hz <= 0:
            raise ValueError("VNA IF bandwidth must be greater than 0 Hz.")
        self._prepare_for_reconfiguration()
        self._write(f"SENS:BAND:RES {bandwidth_hz:.12g}")
        self._wait_for_operation_complete()
        self._raise_for_system_error()
        self._ifbw_hz = bandwidth_hz

    def configure_measurement_parameter(self, parameter: str) -> None:
        self._select_parameter(parameter)

    def configure_continuous_sweep(self, enabled: bool) -> None:
        self._prepare_for_reconfiguration()
        self._set_sweep_mode("CONT" if enabled else "HOLD")

    def query_sweep_time_s(self) -> float:
        return float(self._query("SENS1:SWE:TIME?"))

    def trigger_sweep(self, parameter: str = "S21") -> None:
        parameter = parameter.upper()
        if self._selected_parameter != parameter:
            self._select_parameter(parameter)
        else:
            self._write(f"CALC:PAR:SEL '{self._trace_name}'")
        self._prepare_for_reconfiguration()
        self._write("TRIG:SOUR IMM")
        self._set_sweep_mode("SING")
        self._wait_for_operation_complete()
        self._raise_for_system_error()

    def read_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        if not self.is_connected:
            raise RuntimeError("VNA is not connected.")
        frequency = np.linspace(self._start_hz, self._stop_hz, self._points)
        value_db = np.zeros(self._points)
        phase = np.zeros(self._points)
        return SParameterTrace(frequency, value_db, phase, parameter)

    def measure_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        self.trigger_sweep(parameter)
        return self.read_s_parameter(parameter)

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

    def _select_parameter(self, parameter: str) -> None:
        parameter = parameter.upper()
        if re.fullmatch(r"S([1-4])([1-4])", parameter) is None:
            raise ValueError(f"Unsupported S-parameter: {parameter}")

        trace_name = self._trace_name
        self._prepare_for_reconfiguration()
        self._write("*CLS")
        strategies = (
            (
                f"CALC1:PAR:DEF:EXT '{trace_name}','{parameter}'",
                f"CALC1:PAR:SEL '{trace_name}'",
            ),
            (
                f"CALC:PAR:DEF:EXT '{trace_name}','{parameter}'",
                f"CALC:PAR:SEL '{trace_name}'",
            ),
            (
                f"CALC:PAR:DEF '{trace_name}',{parameter}",
                f"CALC:PAR:SEL '{trace_name}'",
            ),
        )
        last_error: Exception | None = None
        for commands in strategies:
            try:
                for command in commands:
                    self._write(command)
                self._feed_trace_display(trace_name)
                self._wait_for_operation_complete()
                self._raise_for_system_error()
                self._selected_parameter = parameter
                return
            except Exception as exc:  # noqa: BLE001 - alternate SCPI dialects.
                last_error = exc
        if last_error is not None:
            raise last_error

    def _feed_trace_display(self, trace_name: str) -> None:
        self._try_write("DISP:WIND1:STAT ON")
        self._try_write("DISP:WIND1:TRAC1:DEL")
        self._try_write(f"DISP:WIND1:TRAC1:FEED '{trace_name}'")

    def _prepare_for_reconfiguration(self) -> None:
        self._try_write("ABOR")
        self._wait_for_operation_complete()
        self._drain_stale_init_ignored_error()

    def _set_sweep_mode(self, mode: str) -> None:
        self._write(f"SENS1:SWE:MODE {mode.strip().upper()}")
        self._wait_for_operation_complete()
        self._raise_for_system_error()

    def _wait_for_operation_complete(self) -> None:
        self._query("*OPC?")

    def _raise_for_system_error(self) -> None:
        try:
            response = self._query("SYST:ERR?")
        except Exception:
            return
        normalized = response.strip()
        if normalized and not normalized.startswith(("0,", "+0,")) and normalized not in {"0", "+0"} and "NO ERROR" not in normalized.upper():
            raise RuntimeError(f"VNA reported SCPI error: {normalized}")

    def _drain_stale_init_ignored_error(self) -> None:
        try:
            response = self._query("SYST:ERR?")
        except Exception:
            return
        normalized = response.strip().upper()
        if not normalized or normalized.startswith(("0,", "+0,")) or normalized in {"0", "+0"} or "NO ERROR" in normalized:
            return
        if "INIT IGNORED" in normalized:
            return
        raise RuntimeError(f"VNA has pending SCPI error before reconfiguration: {response.strip()}")

    def _try_write(self, command: str) -> None:
        try:
            self._write(command)
        except Exception:
            return
