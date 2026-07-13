from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import numpy as np

from quiet_zone_tester.hardware.interfaces import InstrumentInfo
from quiet_zone_tester.hardware.transport.visa_scpi import (
    ScpiCommunicationError,
    ScpiConnectionConfig,
    VisaScpiSession,
)
from quiet_zone_tester.models import SParameterTrace
from quiet_zone_tester.shared.instrument_defaults import DEFAULT_VNA_TIMEOUT_MS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VnaScpiConfig:
    resource_name: str
    timeout_ms: int = DEFAULT_VNA_TIMEOUT_MS
    retries: int = 2
    retry_delay_s: float = 0.2
    expected_model: str | None = None


class ScpiVnaController:
    def __init__(self, config: VnaScpiConfig) -> None:
        self._config = config
        self._session = VisaScpiSession(
            ScpiConnectionConfig(
                resource_name=config.resource_name,
                timeout_ms=config.timeout_ms,
                retries=config.retries,
                retry_delay_s=config.retry_delay_s,
            )
        )
        self._connected = False
        self._info: InstrumentInfo | None = None
        self._start_hz = 10.0e9
        self._stop_hz = 17.0e9
        self._points = 801
        self._power_dbm = -10.0
        self._if_bandwidth_hz = 1000.0
        self._trace_name = "CH1_SPARAM"
        self._selected_parameter: str | None = None

    def connect(self) -> InstrumentInfo:
        try:
            self._session.open()
            idn = self._session.query("*IDN?")
            info = self._parse_idn(idn)
            expected_model = (self._config.expected_model or "").strip().upper()
            actual_model = self._idn_model(idn).upper()
            if expected_model and actual_model != expected_model:
                raise ScpiCommunicationError(
                    f"VNA model mismatch: configured {expected_model}, "
                    f"instrument reported {actual_model or 'UNKNOWN'}."
                )
        except Exception:
            self._session.close()
            raise
        self._connected = True
        self._info = info
        logger.info("Connected VNA: %s", info)
        return info

    def disconnect(self) -> None:
        logger.info("Disconnecting VNA: %s", self._config.resource_name)
        self._session.close()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._session.is_open

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        self._ensure_connected()
        if start_hz <= 0 or stop_hz <= start_hz:
            raise ValueError("Invalid VNA sweep frequency range.")
        if points < 2:
            raise ValueError("VNA sweep points must be greater than 1.")

        logger.info(
            "Configuring VNA sweep: start=%s Hz stop=%s Hz points=%s",
            start_hz,
            stop_hz,
            points,
        )
        self._prepare_for_reconfiguration()
        self._session.write(f"SENS:FREQ:STAR {start_hz:.12g}")
        self._session.write(f"SENS:FREQ:STOP {stop_hz:.12g}")
        self._session.write(f"SENS:SWE:POIN {points}")
        self._wait_for_operation_complete()
        self._raise_for_system_error()
        self._start_hz = float(self._session.query("SENS:FREQ:STAR?"))
        self._stop_hz = float(self._session.query("SENS:FREQ:STOP?"))
        self._points = int(float(self._session.query("SENS:SWE:POIN?")))

    def configure_power(self, power_dbm: float) -> None:
        self._ensure_connected()
        if not -90.0 <= power_dbm <= 30.0:
            raise ValueError("VNA power must be between -90 dBm and 30 dBm.")

        logger.info("Configuring VNA source power: %.2f dBm", power_dbm)
        self._prepare_for_reconfiguration()
        self._session.write(f"SOUR:POW {power_dbm:.6g}")
        self._wait_for_operation_complete()
        self._raise_for_system_error()
        self._power_dbm = power_dbm

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        self._ensure_connected()
        if bandwidth_hz <= 0.0:
            raise ValueError("VNA IF bandwidth must be greater than 0 Hz.")

        logger.info("Configuring VNA IF bandwidth: %.3f Hz", bandwidth_hz)
        self._prepare_for_reconfiguration()
        self._session.write(f"SENS:BAND:RES {bandwidth_hz:.12g}")
        self._wait_for_operation_complete()
        self._raise_for_system_error()
        self._if_bandwidth_hz = bandwidth_hz

    def configure_measurement_parameter(self, parameter: str) -> None:
        self._select_parameter(parameter)

    def configure_continuous_sweep(self, enabled: bool) -> None:
        self._ensure_connected()
        self._prepare_for_reconfiguration()
        self._set_sweep_mode("CONT" if enabled else "HOLD")

    def query_sweep_time_s(self) -> float:
        self._ensure_connected()
        return float(self._session.query("SENS1:SWE:TIME?"))

    def measure_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        self.trigger_sweep(parameter)
        return self.read_s_parameter(parameter)

    def trigger_sweep(self, parameter: str = "S21") -> None:
        self._ensure_connected()
        parameter = parameter.upper()
        logger.info("Triggering VNA sweep: %s", parameter)

        if self._selected_parameter != parameter:
            self._select_parameter(parameter)
        else:
            self._session.write(f"CALC:PAR:SEL '{self._trace_name}'")
        self._prepare_for_reconfiguration()
        self._session.write("TRIG:SOUR IMM")
        self._set_sweep_mode("SING")
        self._wait_for_operation_complete()
        self._raise_for_system_error()

    def read_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        self._ensure_connected()
        parameter = parameter.upper()
        logger.info("Reading VNA trace: %s", parameter)

        if self._selected_parameter != parameter:
            self._select_parameter(parameter)
        else:
            self._session.write(f"CALC:PAR:SEL '{self._trace_name}'")
        values = self._read_sdata()
        complex_values = self._values_to_complex(values)
        if complex_values.size != self._points:
            logger.warning(
                "VNA returned %s complex points, expected %s.",
                complex_values.size,
                self._points,
            )

        frequency_hz = np.linspace(self._start_hz, self._stop_hz, complex_values.size)
        return SParameterTrace(frequency_hz, complex_values, parameter)

    def _select_parameter(self, parameter: str) -> None:
        match = re.fullmatch(r"S([1-4])([1-4])", parameter)
        if match is None:
            raise ValueError(f"Unsupported S-parameter: {parameter}")

        trace_name = self._trace_name
        self._prepare_for_reconfiguration()
        self._session.write("*CLS")
        try:
            catalog = self._session.query("CALC1:PAR:CAT:EXT?")
            catalog_items = [item.strip().strip("'\"") for item in catalog.split(",")]
            measurement_names = set(catalog_items[0::2])
            if trace_name in measurement_names:
                self._session.write(f"CALC1:PAR:DEL '{trace_name}'")
                self._raise_for_system_error()
            self._session.write(f"CALC1:PAR:DEF:EXT '{trace_name}','{parameter}'")
            self._session.write(f"CALC1:PAR:SEL '{trace_name}'")
            self._raise_for_system_error()
            self._feed_trace_display(trace_name)
            self._session.query("*OPC?")
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
                self._session.write("*CLS")
                for command in commands:
                    self._session.write(command)
                self._raise_for_system_error()
                self._feed_trace_display(trace_name)
                self._session.query("*OPC?")
                self._selected_parameter = parameter
                logger.info("VNA measurement parameter configured: %s.", parameter)
                return
            except Exception as exc:  # noqa: BLE001 - try alternate vendor command families.
                errors.append(str(exc))
                logger.warning("VNA parameter configuration strategy failed: %s", exc)

        raise ScpiCommunicationError(
            f"Unable to configure VNA measurement parameter {parameter}: {'; '.join(errors)}"
        )

    def _read_sdata(self) -> list[float]:
        self._session.write("FORM:DATA REAL,64")
        self._session.write("FORM:BORD SWAP")
        try:
            return self._session.query_binary_values("CALC:DATA? SDATA", datatype="d", is_big_endian=False)
        except ScpiCommunicationError:
            logger.error("Binary SDATA read failed; refusing an unsafe in-session retry.")
            raise

    def _try_write(self, command: str) -> None:
        try:
            self._session.write(command)
        except ScpiCommunicationError:
            logger.debug("Optional VNA command failed: %s", command, exc_info=True)

    def _feed_trace_display(self, trace_name: str) -> None:
        self._try_write("DISP:WIND1:STAT ON")
        if self._display_trace_exists(1):
            self._try_write("DISP:WIND1:TRAC1:DEL")
        self._try_write(f"DISP:WIND1:TRAC1:FEED '{trace_name}'")
        self._drain_optional_display_error()

    def _display_trace_exists(self, trace_number: int) -> bool:
        try:
            catalog = self._session.query("DISP:WIND1:CAT?")
        except ScpiCommunicationError:
            return False

        tokens = [token.strip().strip("'\"") for token in catalog.split(",")]
        return str(int(trace_number)) in tokens

    def _drain_optional_display_error(self) -> None:
        try:
            response = self._session.query("SYST:ERR?")
        except ScpiCommunicationError:
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
        self._session.write(f"SENS1:SWE:MODE {normalized_mode}")
        self._wait_for_operation_complete()
        self._raise_for_system_error()

    def _query_sweep_mode(self) -> str | None:
        try:
            response = self._session.query("SENS1:SWE:MODE?")
        except ScpiCommunicationError:
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
        self._session.query("*OPC?")

    def _drain_stale_init_ignored_error(self) -> None:
        try:
            response = self._session.query("SYST:ERR?")
        except ScpiCommunicationError:
            return

        normalized = response.strip()
        if self._is_no_error(normalized):
            return
        if self._is_init_ignored(normalized):
            logger.info("Cleared stale VNA Init ignored state before reconfiguration: %s", normalized)
            return
        raise ScpiCommunicationError(f"VNA has pending SCPI error before reconfiguration: {normalized}")

    def _raise_for_system_error(self) -> None:
        try:
            response = self._session.query("SYST:ERR?")
        except ScpiCommunicationError:
            return

        normalized = response.strip()
        if self._is_no_error(normalized):
            return
        raise ScpiCommunicationError(f"VNA reported SCPI error: {normalized}")

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
    def _is_init_ignored(response: str) -> bool:
        return "INIT IGNORED" in response.strip().upper()

    @staticmethod
    def _is_ignored_optional_display_error(response: str) -> bool:
        normalized = response.strip().upper()
        return "DUPLICATE TRACE NUMBER" in normalized or "REQUESTED TRACE NOT FOUND" in normalized

    @staticmethod
    def _values_to_complex(values: list[float]) -> np.ndarray:
        array = np.asarray(values, dtype=float)
        if array.size % 2 != 0:
            raise ScpiCommunicationError("VNA SDATA response has an odd number of values.")
        real = array[0::2]
        imag = array[1::2]
        return real + 1j * imag

    def _parse_idn(self, idn: str) -> InstrumentInfo:
        parts = [part.strip() for part in idn.split(",")]
        manufacturer = parts[0] if len(parts) > 0 else "Unknown"
        model = parts[1] if len(parts) > 1 else "Vector Network Analyzer"
        serial = parts[2] if len(parts) > 2 else "UNKNOWN"
        return InstrumentInfo(
            resource_name=self._config.resource_name,
            model=f"{manufacturer} {model}".strip(),
            serial_number=serial,
            is_mock=False,
        )

    @staticmethod
    def _idn_model(idn: str) -> str:
        parts = [part.strip() for part in idn.split(",")]
        return parts[1] if len(parts) > 1 else ""

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError("VNA is not connected.")
