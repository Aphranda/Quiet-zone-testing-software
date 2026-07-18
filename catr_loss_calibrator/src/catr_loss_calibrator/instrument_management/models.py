from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentConnectionConfig:
    resource: str
    model: str
    use_mock: bool = True


@dataclass(frozen=True)
class InstrumentState:
    name: str
    is_connected: bool
    resource: str = ""
    model: str = ""

