from __future__ import annotations

from dataclasses import dataclass
import logging
import re

import numpy as np

from catr_loss_calibrator.hardware.interfaces import InstrumentInfo, SParameterTrace, Vna
from catr_loss_calibrator.hardware.scpi import ScpiCommunicationError, ScpiConnectionConfig, VisaScpiSession
from catr_loss_calibrator.project.config import DEFAULT_VNA_POWER_DBM

logger = logging.getLogger(__name__)


@dataclass
class PyVisaVna(Vna):
    resource: str
    model: str = "UNKNOWN"
    timeout_ms: int = 10_000

    def __post_init__(self) -> None:
        self._connected = False
        self._resource = None
        self._session = VisaScpiSession(
            ScpiConnectionConfig(
                resource_name=self.resource,
                timeout_ms=self.timeout_ms,
            )
        )
        self._start_hz = 10e9
        self._stop_hz = 15e9
        self._points = 51
        self._power_dbm = DEFAULT_VNA_POWER_DBM
        self._ifbw_hz = 1000.0
        self._trace_name = "CH1_SPARAM"
        self._selected_parameter: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected and (self._session.is_open or self._resource is not None)

    def connect(self) -> InstrumentInfo:
        try:
            self._session.open()
            self._connected = True
            idn = self._query("*IDN?")
        except Exception:
            self._session.close()
            self._connected = False
            raise
        return self._parse_idn(idn)

    def disconnect(self) -> None:
        self._session.close()
        if self._resource is not None:
            try:
                self._resource.close()
            finally:
                self._resource = None
        self._connected = False

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        self._ensure_connected()
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
        self._start_hz = self._query_float_or_default("SENS:FREQ:STAR?", start_hz)
        self._stop_hz = self._query_float_or_default("SENS:FREQ:STOP?", stop_hz)
        self._points = int(self._query_float_or_default("SENS:SWE:POIN?", float(points)))

    def configure_power(self, power_dbm: float) -> None:
        self._ensure_connected()
        if not -90.0 <= power_dbm <= 30.0:
            raise ValueError("VNA power must be between -90 dBm and 30 dBm.")
        self._prepare_for_reconfiguration()
        self._write_with_error_fallback((f"SOUR:POW {power_dbm:.6g}", f"SOUR1:POW1:LEV:IMM:AMPL {power_dbm:.6g}"))
        self._wait_for_operation_complete()
        self._raise_for_system_error()
        self._power_dbm = power_dbm

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        self._ensure_connected()
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
        self._ensure_connected()
        self._prepare_for_reconfiguration()
        self._set_sweep_mode("CONT" if enabled else "HOLD")

    def query_sweep_time_s(self) -> float:
        self._ensure_connected()
        return float(self._query("SENS1:SWE:TIME?"))

    def trigger_sweep(self, parameter: str = "S21") -> None:
        self._ensure_connected()
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
        parameter = parameter.upper()
        if self._selected_parameter != parameter:
            self._select_parameter(parameter)
        else:
            self._write(f"CALC:PAR:SEL '{self._trace_name}'")

        value_db: np.ndarray | None = None
        phase: np.ndarray | None = None

        try:
            sdata = self._read_sdata()
            if sdata.size != self._points * 2:
                raise RuntimeError(f"VNA returned {sdata.size} SDATA values for {self._points} points.")
            complex_values = sdata[0::2] + 1j * sdata[1::2]
            magnitude = np.maximum(np.abs(complex_values), np.finfo(float).tiny)
            value_db = 20.0 * np.log10(magnitude)
            phase = np.degrees(np.angle(complex_values))
        except Exception:
            value_db = None

        if value_db is None:
            formatted = self._query_float_values("CALC1:DATA? FDATA")
            if formatted.size != self._points:
                formatted = self._query_float_values("CALC:DATA? FDATA")
            if formatted.size != self._points:
                raise RuntimeError(f"VNA returned {formatted.size} FDATA values for {self._points} points.")
            value_db = formatted

        frequency = np.linspace(self._start_hz, self._stop_hz, value_db.size)
        if phase is None:
            phase = np.zeros(value_db.size)
        return SParameterTrace(frequency, value_db, phase, parameter)

    def measure_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        self.trigger_sweep(parameter)
        return self.read_s_parameter(parameter)

    def send_command(self, command: str) -> str:
        self._ensure_connected()
        if command.strip().endswith("?"):
            return self._query(command)
        self._write(command)
        return "OK"

    def _write(self, command: str) -> None:
        if self._session.is_open:
            self._session.write(command)
            return
        if self._resource is None:
            raise RuntimeError("VNA is not connected.")
        self._resource.write(command)

    def _query(self, command: str) -> str:
        if self._session.is_open:
            return self._session.query(command)
        if self._resource is None:
            raise RuntimeError("VNA is not connected.")
        return str(self._resource.query(command)).strip()

    def _query_float_or_default(self, command: str, default: float) -> float:
        try:
            return float(self._query(command))
        except Exception:
            return float(default)

    def _query_float_values(self, command: str) -> np.ndarray:
        if self._session.is_open:
            return np.asarray(self._session.query_ascii_values(command), dtype=float)
        if self._resource is None:
            raise RuntimeError("VNA is not connected.")
        query_ascii_values = getattr(self._resource, "query_ascii_values", None)
        if callable(query_ascii_values):
            return np.asarray(query_ascii_values(command), dtype=float)
        response = str(self._resource.query(command))
        normalized = response.replace("\n", ",").replace("\r", ",").replace(";", ",")
        values = [part.strip() for part in normalized.split(",") if part.strip()]
        return np.asarray([float(value) for value in values], dtype=float)

    def _query_binary_float_values(self, command: str) -> np.ndarray:
        if self._session.is_open:
            return np.asarray(self._session.query_binary_values(command, datatype="d", is_big_endian=False), dtype=float)
        if self._resource is None:
            raise RuntimeError("VNA is not connected.")
        query_binary_values = getattr(self._resource, "query_binary_values", None)
        if not callable(query_binary_values):
            raise RuntimeError("VNA resource does not support binary value queries.")
        return np.asarray(query_binary_values(command, datatype="d", is_big_endian=False), dtype=float)

    def _read_sdata(self) -> np.ndarray:
        self._write("FORM:DATA REAL,64")
        self._write("FORM:BORD SWAP")
        try:
            return self._query_binary_float_values("CALC:DATA? SDATA")
        except Exception as exc:
            logger.warning("Binary SDATA read failed; falling back to ASCII SDATA: %s", exc)
            return self._query_float_values("CALC:DATA? SDATA")

    def _select_parameter(self, parameter: str) -> None:
        parameter = parameter.upper()
        if re.fullmatch(r"S([1-4])([1-4])", parameter) is None:
            raise ValueError(f"Unsupported S-parameter: {parameter}")

        trace_name = self._trace_name
        self._prepare_for_reconfiguration()
        self._write("*CLS")
        try:
            catalog = self._query("CALC1:PAR:CAT:EXT?")
            catalog_items = [item.strip().strip("'\"") for item in catalog.split(",")]
            measurement_names = set(catalog_items[0::2])
            if trace_name in measurement_names:
                self._write(f"CALC1:PAR:DEL '{trace_name}'")
                self._raise_for_system_error()
            self._write(f"CALC1:PAR:DEF:EXT '{trace_name}','{parameter}'")
            self._write(f"CALC1:PAR:SEL '{trace_name}'")
            self._raise_for_system_error()
            self._feed_trace_display(trace_name)
            self._wait_for_operation_complete()
            self._selected_parameter = parameter
            logger.info("VNA measurement parameter configured: %s.", parameter)
            return
        except Exception as exc:  # noqa: BLE001 - use legacy command variants as fallback.
            logger.warning("VNA catalog-based parameter configuration failed: %s", exc)

        strategies = (
            (
                f"CALC:PAR:SEL '{trace_name}'",
                f"CALC:PAR:MOD:EXT '{trace_name}','{parameter}'",
            ),
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
        errors: list[str] = []
        for commands in strategies:
            try:
                self._write("*CLS")
                for command in commands:
                    self._write(command)
                self._feed_trace_display(trace_name)
                self._wait_for_operation_complete()
                self._raise_for_system_error()
                self._selected_parameter = parameter
                logger.info("VNA measurement parameter configured: %s.", parameter)
                return
            except Exception as exc:  # noqa: BLE001 - alternate SCPI dialects.
                errors.append(str(exc))
                logger.warning("VNA parameter configuration strategy failed: %s", exc)
        raise ScpiCommunicationError(
            f"Unable to configure VNA measurement parameter {parameter}: {'; '.join(errors)}"
        )

    def _feed_trace_display(self, trace_name: str) -> None:
        self._try_write("DISP:WIND1:STAT ON")
        if self._display_trace_exists(1):
            self._try_write("DISP:WIND1:TRAC1:DEL")
        self._try_write(f"DISP:WIND1:TRAC1:FEED '{trace_name}'")
        self._drain_optional_display_error()

    def _display_trace_exists(self, trace_number: int) -> bool:
        try:
            catalog = self._query("DISP:WIND1:CAT?")
        except Exception:
            return False

        tokens = [token.strip().strip("'\"") for token in catalog.split(",")]
        return str(int(trace_number)) in tokens

    def _drain_optional_display_error(self) -> None:
        try:
            response = self._query("SYST:ERR?")
        except Exception:
            return

        normalized = response.strip()
        if self._is_no_error(normalized) or self._is_ignored_optional_display_error(normalized):
            return
        logger.warning("Optional VNA display command reported SCPI error: %s", normalized)

    def _prepare_for_reconfiguration(self) -> None:
        self._try_write("ABOR")
        self._wait_for_operation_complete()
        self._drain_stale_init_ignored_error()

    def _set_sweep_mode(self, mode: str) -> None:
        normalized_mode = mode.strip().upper()
        current = self._query_sweep_mode()
        if current == normalized_mode:
            return
        self._write(f"SENS1:SWE:MODE {normalized_mode}")
        self._wait_for_operation_complete()
        self._raise_for_system_error()

    def _query_sweep_mode(self) -> str | None:
        try:
            response = self._query("SENS1:SWE:MODE?")
        except Exception:
            return None

        normalized = response.strip().strip("'\"").upper()
        aliases = {
            "CONTINUOUS": "CONT",
            "CONT": "CONT",
            "SINGLE": "SING",
            "SING": "SING",
            "HOLD": "HOLD",
        }
        return aliases.get(normalized)

    def _wait_for_operation_complete(self) -> None:
        self._query("*OPC?")

    def _raise_for_system_error(self) -> None:
        try:
            response = self._query("SYST:ERR?")
        except Exception:
            return
        normalized = response.strip()
        if not self._is_no_error(normalized):
            raise RuntimeError(f"VNA reported SCPI error: {normalized}")

    def _drain_stale_init_ignored_error(self) -> None:
        try:
            response = self._query("SYST:ERR?")
        except Exception:
            return
        normalized = response.strip()
        if self._is_no_error(normalized):
            return
        if "INIT IGNORED" in normalized.upper():
            logger.info("Cleared stale VNA Init ignored state before reconfiguration: %s", normalized)
            return
        raise RuntimeError(f"VNA has pending SCPI error before reconfiguration: {response.strip()}")

    @staticmethod
    def _is_no_error(response: str) -> bool:
        normalized = response.strip()
        return (
            not normalized
            or normalized.startswith(("0,", "+0,"))
            or normalized in {"0", "+0"}
            or "NO ERROR" in normalized.upper()
        )

    @staticmethod
    def _is_ignored_optional_display_error(response: str) -> bool:
        normalized = response.strip().upper()
        return "DUPLICATE TRACE NUMBER" in normalized or "REQUESTED TRACE NOT FOUND" in normalized

    def _try_write(self, command: str) -> None:
        try:
            self._write(command)
        except Exception:
            return

    def _write_with_fallback(self, commands: tuple[str, ...]) -> None:
        last_error: Exception | None = None
        for command in commands:
            try:
                self._write(command)
                return
            except Exception as exc:  # noqa: BLE001 - alternate SCPI dialects.
                last_error = exc
        if last_error is not None:
            raise last_error

    def _write_with_error_fallback(self, commands: tuple[str, ...]) -> None:
        last_error: Exception | None = None
        for command in commands:
            try:
                self._write(command)
                self._raise_for_system_error()
                return
            except Exception as exc:  # noqa: BLE001 - alternate SCPI dialects.
                last_error = exc
                self._drain_stale_init_ignored_error()
        if last_error is not None:
            raise last_error

    def _parse_idn(self, idn: str) -> InstrumentInfo:
        parts = [part.strip() for part in idn.split(",")]
        model = parts[1] if len(parts) > 1 else self.model
        serial = parts[2] if len(parts) > 2 else ""
        return InstrumentInfo(resource=self.resource, model=model, serial=serial)

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError("VNA is not connected.")
