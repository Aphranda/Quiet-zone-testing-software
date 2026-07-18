from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SweepConfig:
    start_hz: float = 10e9
    stop_hz: float = 15e9
    points: int = 501
    if_bandwidth_hz: float = 1000.0
    power_dbm: float = -10.0


@dataclass(frozen=True)
class ProjectConfig:
    feed: str = "F10_17G"
    horn: str = "H10_15G"
    output_root: str = "calibration_results"
    sweep: SweepConfig = SweepConfig()
