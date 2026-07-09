from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from quiet_zone_tester.models import SParameterTrace, ScanVolume


@dataclass(frozen=True)
class ScanPoint:
    index: int
    x_mm: float
    y_mm: float

    @property
    def position_mm(self) -> tuple[float, float]:
        return self.x_mm, self.y_mm


@dataclass(frozen=True)
class ScanSessionConfig:
    scan_volume: ScanVolume
    scan_mode: str
    parameter: str
    output_root: Path
    file_flag: str = ""
    connection_config: dict[str, Any] | None = None
    settings_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TraceRecord:
    point_index: int
    position_mm: tuple[float, float] | None
    parameter: str
    trace: SParameterTrace | None
    acquired_at: datetime
    file_path: Path | None = None


@dataclass(frozen=True)
class ScanEvent:
    timestamp: datetime
    level: str
    event_type: str
    message: str


@dataclass
class ScanSession:
    session_id: str
    config: ScanSessionConfig
    planned_points: list[ScanPoint]
    output_dir: Path
    started_at: datetime
    records: list[TraceRecord] = field(default_factory=list)
    events: list[ScanEvent] = field(default_factory=list)
    finished_at: datetime | None = None
    final_state: str | None = None

    @property
    def point_count(self) -> int:
        return len(self.planned_points)

    @property
    def completed_count(self) -> int:
        return len(self.records)

    @property
    def is_finalized(self) -> bool:
        return self.finished_at is not None and self.final_state is not None

    def append_record(self, record: TraceRecord) -> None:
        if self.is_finalized:
            raise ValueError("Cannot append trace records after scan session is finalized.")
        self.records.append(record)

    def append_event(self, event: ScanEvent) -> None:
        self.events.append(event)

    def finalize(self, final_state: str, finished_at: datetime | None = None) -> None:
        if self.is_finalized:
            raise ValueError("Scan session is already finalized.")
        self.final_state = str(final_state)
        self.finished_at = finished_at or datetime.now()

    def metadata_summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "scan_mode": self.config.scan_mode,
            "parameter": self.config.parameter,
            "file_flag": self.config.file_flag,
            "point_count": self.point_count,
            "completed_count": self.completed_count,
            "output_dir": str(self.output_dir),
            "started_at": self.started_at.isoformat(),
            "finished_at": None if self.finished_at is None else self.finished_at.isoformat(),
            "final_state": self.final_state,
            "scan_volume": {
                "x_start_mm": self.config.scan_volume.x_start_mm,
                "x_stop_mm": self.config.scan_volume.x_stop_mm,
                "y_start_mm": self.config.scan_volume.y_start_mm,
                "y_stop_mm": self.config.scan_volume.y_stop_mm,
                "step_x_mm": self.config.scan_volume.step_x_mm,
                "step_y_mm": self.config.scan_volume.step_y_mm,
            },
        }


def scan_points_from_volume(volume: ScanVolume) -> list[ScanPoint]:
    points = volume.scan_points()
    return [
        ScanPoint(index=index, x_mm=float(point[0]), y_mm=float(point[1]))
        for index, point in enumerate(points, start=1)
    ]
