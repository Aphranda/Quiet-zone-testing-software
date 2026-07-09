from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Protocol

from quiet_zone_tester.domains.scan_management import ScanSettings
from quiet_zone_tester.models import SParameterTrace

logger = logging.getLogger(__name__)


class AcquisitionVnaController(Protocol):
    @property
    def is_connected(self) -> bool:
        ...

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        ...

    def configure_power(self, power_dbm: float) -> None:
        ...

    def measure_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        ...


class AcquisitionServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SweepConfiguration:
    start_hz: float
    stop_hz: float
    points: int
    parameter: str
    power_dbm: float = -10.0
    if_bandwidth_hz: float = 1000.0

    @classmethod
    def from_ghz(
        cls,
        *,
        start_ghz: float,
        stop_ghz: float,
        points: int,
        parameter: str,
        power_dbm: float = -10.0,
        if_bandwidth_hz: float = 1000.0,
    ) -> SweepConfiguration:
        return cls(
            start_hz=float(start_ghz) * 1e9,
            stop_hz=float(stop_ghz) * 1e9,
            points=int(points),
            parameter=str(parameter),
            power_dbm=float(power_dbm),
            if_bandwidth_hz=float(if_bandwidth_hz),
        )


@dataclass(frozen=True)
class AcquisitionService:
    vna: AcquisitionVnaController

    def configure_trace(
        self,
        *,
        start_ghz: float,
        stop_ghz: float,
        points: int,
        parameter: str,
        power_dbm: float = -10.0,
        if_bandwidth_hz: float = 1000.0,
    ) -> None:
        config = SweepConfiguration.from_ghz(
            start_ghz=start_ghz,
            stop_ghz=stop_ghz,
            points=points,
            parameter=parameter,
            power_dbm=power_dbm,
            if_bandwidth_hz=if_bandwidth_hz,
        )
        self.configure(config, configure_parameter=True)

    def configure_for_scan(self, settings: dict | ScanSettings) -> None:
        if isinstance(settings, ScanSettings):
            sweep = settings.sweep
            config = SweepConfiguration.from_ghz(
                start_ghz=sweep.start_ghz,
                stop_ghz=sweep.stop_ghz,
                points=sweep.points,
                parameter=sweep.parameter,
                power_dbm=sweep.vna_power_dbm,
                if_bandwidth_hz=sweep.if_bandwidth_hz,
            )
            self.configure(config, configure_parameter=False)
            return

        config = SweepConfiguration.from_ghz(
            start_ghz=float(settings["start_ghz"]),
            stop_ghz=float(settings["stop_ghz"]),
            points=int(settings["points"]),
            parameter=str(settings["parameter"]),
            power_dbm=float(settings["vna_power_dbm"]),
            if_bandwidth_hz=float(settings.get("if_bandwidth_hz", 1000.0)),
        )
        self.configure(config, configure_parameter=False)

    def configure(self, config: SweepConfiguration, *, configure_parameter: bool) -> None:
        self._ensure_connected()
        try:
            self.vna.configure_power(config.power_dbm)
            self._configure_if_bandwidth(config.if_bandwidth_hz)
            self.vna.configure_sweep(config.start_hz, config.stop_hz, config.points)
            if configure_parameter:
                configure_measurement = getattr(self.vna, "configure_measurement_parameter", None)
                if callable(configure_measurement):
                    configure_measurement(config.parameter)
        except Exception as exc:
            logger.exception("VNA sweep configuration failed.")
            raise AcquisitionServiceError(f"VNA sweep configuration failed: {exc}") from exc

    def acquire_trace(
        self,
        *,
        start_ghz: float,
        stop_ghz: float,
        points: int,
        parameter: str,
        power_dbm: float = -10.0,
        if_bandwidth_hz: float = 1000.0,
    ) -> SParameterTrace:
        self.configure_trace(
            start_ghz=start_ghz,
            stop_ghz=stop_ghz,
            points=points,
            parameter=parameter,
            power_dbm=power_dbm,
            if_bandwidth_hz=if_bandwidth_hz,
        )
        return self.sample_trace(parameter)

    def sample_trace(self, parameter: str) -> SParameterTrace:
        self._ensure_connected()
        try:
            trace = self.vna.measure_s_parameter(str(parameter))
        except Exception as exc:
            logger.exception("VNA trace measurement failed.")
            raise AcquisitionServiceError(f"VNA trace measurement failed: {exc}") from exc
        return self._validated_trace(trace)

    def sample_scan_trace(
        self,
        parameter: str,
        *,
        stop_requested: Callable[[], bool] | None = None,
    ) -> SParameterTrace:
        self._raise_if_stopped(stop_requested)
        trace = self.sample_trace(parameter)
        self._raise_if_stopped(stop_requested)
        return trace

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        self._ensure_connected()
        try:
            self._configure_if_bandwidth(bandwidth_hz)
        except Exception as exc:
            logger.exception("VNA IF bandwidth configuration failed.")
            raise AcquisitionServiceError(f"VNA IF bandwidth configuration failed: {exc}") from exc

    def _configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        configure_if_bandwidth = getattr(self.vna, "configure_if_bandwidth", None)
        if callable(configure_if_bandwidth):
            configure_if_bandwidth(float(bandwidth_hz))

    def _ensure_connected(self) -> None:
        if not self.vna.is_connected:
            raise AcquisitionServiceError("VNA controller is not connected.")

    @staticmethod
    def _validated_trace(trace: SParameterTrace) -> SParameterTrace:
        if trace.frequency_hz.size == 0 or trace.complex_values.size == 0:
            raise AcquisitionServiceError("VNA returned an empty trace.")
        return trace

    @staticmethod
    def _raise_if_stopped(stop_requested: Callable[[], bool] | None) -> None:
        if stop_requested is not None and stop_requested():
            raise AcquisitionServiceError("Acquisition stopped.")
