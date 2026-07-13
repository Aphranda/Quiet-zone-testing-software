from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from quiet_zone_tester.models import SParameterTrace


@dataclass(frozen=True)
class InstrumentInfo:
    resource_name: str
    model: str
    serial_number: str
    is_mock: bool = False


@dataclass(frozen=True)
class Position:
    x_mm: float
    y_mm: float


class VnaController(Protocol):
    def connect(self) -> InstrumentInfo:
        ...

    def disconnect(self) -> None:
        ...

    @property
    def is_connected(self) -> bool:
        ...

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        ...

    def configure_power(self, power_dbm: float) -> None:
        ...

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        ...

    def configure_measurement_parameter(self, parameter: str) -> None:
        ...

    def configure_continuous_sweep(self, enabled: bool) -> None:
        ...

    def query_sweep_time_s(self) -> float:
        ...

    def trigger_sweep(self, parameter: str = "S21") -> None:
        ...

    def read_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        ...

    def measure_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        ...


class PositionerController(Protocol):
    def connect(self) -> InstrumentInfo:
        ...

    def disconnect(self) -> None:
        ...

    @property
    def is_connected(self) -> bool:
        ...

    @property
    def position(self) -> Position:
        ...

    def move_to(self, x_mm: float, y_mm: float, speed_mm_s: float | None = None) -> Position:
        ...

    def move_axis_to(self, axis: int, position_mm: float, speed_mm_s: float | None = None) -> Position:
        ...

    def jog_axis(self, axis: int, speed_mm_s: float) -> None:
        ...

    def stop_axis(self, axis: int) -> None:
        ...

    def stop_all(self) -> None:
        ...


class SwitchBoxController(Protocol):
    def connect(self) -> InstrumentInfo:
        ...

    def disconnect(self) -> None:
        ...

    @property
    def is_connected(self) -> bool:
        ...

    def select_s_parameter(self, parameter: str) -> str:
        ...

    def send_command(self, command: str) -> str:
        ...
