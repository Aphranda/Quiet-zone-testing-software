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
        self._session.open()
        idn = self._session.query("*IDN?")
        info = self._parse_idn(idn)
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
        self._session.write(f"SENS:FREQ:STAR {start_hz:.12g}")
        self._session.write(f"SENS:FREQ:STOP {stop_hz:.12g}")
        self._session.write(f"SENS:SWE:POIN {points}")
        self._start_hz = start_hz
        self._stop_hz = stop_hz
        self._points = points

    def configure_power(self, power_dbm: float) -> None:
        self._ensure_connected()
        if not -90.0 <= power_dbm <= 30.0:
            raise ValueError("VNA power must be between -90 dBm and 30 dBm.")

        logger.info("Configuring VNA source power: %.2f dBm", power_dbm)
        self._session.write(f"SOUR:POW {power_dbm:.6g}")
        self._power_dbm = power_dbm

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        self._ensure_connected()
        if bandwidth_hz <= 0.0:
            raise ValueError("VNA IF bandwidth must be greater than 0 Hz.")

        logger.info("Configuring VNA IF bandwidth: %.3f Hz", bandwidth_hz)
        self._session.write("*CLS")
        self._session.write(f"SENS:BAND:RES {bandwidth_hz:.12g}")
        self._raise_for_system_error()
        self._if_bandwidth_hz = bandwidth_hz

    def configure_measurement_parameter(self, parameter: str) -> None:
        self._select_parameter(parameter)

    def measure_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        self._ensure_connected()
        parameter = parameter.upper()
        logger.info("Measuring VNA trace: %s", parameter)

        if self._selected_parameter != parameter:
            self._select_parameter(parameter)
        else:
            self._session.write(f"CALC:PAR:SEL '{self._trace_name}'")
        self._session.write("INIT:IMM")
        self._session.query("*OPC?")
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
        self._session.write("*CLS")
        strategies = (
            (
                f"CALC:PAR:SEL '{trace_name}'",
                f"CALC:PAR:MOD {parameter}",
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
                self._try_write(f"DISP:WIND1:TRAC1:FEED '{trace_name}'")
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
            logger.info("Binary SDATA read failed, falling back to ASCII SDATA.")
            self._session.write("FORM:DATA ASCii,0")
            for command in ("CALC:DATA? SDATA", "CALC:DATA? SDAT", "CALC:DATA:SDAT?"):
                try:
                    response = self._session.query(command)
                    return [float(value) for value in response.replace("\n", "").split(",") if value.strip()]
                except ScpiCommunicationError:
                    logger.info("ASCII SDATA read failed with command %s.", command)
            raise

    def _try_write(self, command: str) -> None:
        try:
            self._session.write(command)
        except ScpiCommunicationError:
            logger.debug("Optional VNA command failed: %s", command, exc_info=True)

    def _raise_for_system_error(self) -> None:
        try:
            response = self._session.query("SYST:ERR?")
        except ScpiCommunicationError:
            return

        normalized = response.strip()
        if not normalized:
            return
        if normalized.startswith(("0,", "+0,")) or normalized in {"0", "+0"}:
            return
        if "NO ERROR" in normalized.upper():
            return
        raise ScpiCommunicationError(f"VNA reported SCPI error: {normalized}")

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

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError("VNA is not connected.")
