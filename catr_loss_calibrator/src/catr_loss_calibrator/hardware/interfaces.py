from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class InstrumentInfo:
    resource: str
    model: str
    serial: str = ""


@dataclass(frozen=True)
class SParameterTrace:
    frequency_hz: np.ndarray
    value_db: np.ndarray
    phase_deg: np.ndarray | None = None
    parameter: str = "S21"


class Vna(Protocol):
    @property
    def is_connected(self) -> bool:
        ...

    def connect(self) -> InstrumentInfo:
        ...

    def disconnect(self) -> None:
        ...

    def configure_sweep(self, start_hz: float, stop_hz: float, points: int) -> None:
        ...

    def configure_power(self, power_dbm: float) -> None:
        ...

    def configure_if_bandwidth(self, bandwidth_hz: float) -> None:
        ...

    def trigger_sweep(self, parameter: str = "S21") -> None:
        ...

    def read_s_parameter(self, parameter: str = "S21") -> SParameterTrace:
        ...

    def send_command(self, command: str) -> str:
        ...


class LinkBox(Protocol):
    @property
    def is_connected(self) -> bool:
        ...

    def connect(self) -> InstrumentInfo:
        ...

    def disconnect(self) -> None:
        ...

    def send_command(self, command: str) -> str:
        ...
