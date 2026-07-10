from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Mapping

from quiet_zone_tester.models import DEFAULT_FREQUENCY_STEP_MHZ, SParameterTrace, ScanVolume
from quiet_zone_tester.domains.scan_management.scan_planner import plan_scan_points


@dataclass(frozen=True)
class ScanPoint:
    index: int
    x_mm: float
    y_mm: float

    @property
    def position_mm(self) -> tuple[float, float]:
        return self.x_mm, self.y_mm


@dataclass(frozen=True)
class SweepSettings:
    start_ghz: float = 10.0
    stop_ghz: float = 17.0
    frequency_step_mhz: float = DEFAULT_FREQUENCY_STEP_MHZ
    points: int = 801
    vna_power_dbm: float = -10.0
    if_bandwidth_hz: float = 1000.0
    parameter: str = "S21"

    def __post_init__(self) -> None:
        if self.start_ghz <= 0.0:
            raise ValueError("Sweep start frequency must be greater than 0 GHz.")
        if self.stop_ghz <= self.start_ghz:
            raise ValueError("Sweep stop frequency must be greater than start frequency.")
        if self.frequency_step_mhz <= 0.0:
            raise ValueError("Sweep frequency step must be greater than 0 MHz.")
        if self.points < 2:
            raise ValueError("Sweep points must be greater than 1.")
        if self.if_bandwidth_hz <= 0.0:
            raise ValueError("VNA IF bandwidth must be greater than 0 Hz.")
        parameter = str(self.parameter).strip().upper()
        if not parameter:
            raise ValueError("S-parameter cannot be empty.")
        object.__setattr__(self, "parameter", parameter)

    @classmethod
    def from_mapping(cls, settings: Mapping[str, Any] | None) -> "SweepSettings":
        settings = settings or {}
        return cls(
            start_ghz=float(settings.get("start_ghz", 10.0)),
            stop_ghz=float(settings.get("stop_ghz", 17.0)),
            frequency_step_mhz=float(settings.get("frequency_step_mhz", DEFAULT_FREQUENCY_STEP_MHZ)),
            points=int(settings.get("points", 801)),
            vna_power_dbm=float(settings.get("vna_power_dbm", -10.0)),
            if_bandwidth_hz=float(settings.get("if_bandwidth_hz", 1000.0)),
            parameter=str(settings.get("parameter", "S21")).strip().upper(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ghz": self.start_ghz,
            "stop_ghz": self.stop_ghz,
            "frequency_step_mhz": self.frequency_step_mhz,
            "points": self.points,
            "vna_power_dbm": self.vna_power_dbm,
            "if_bandwidth_hz": self.if_bandwidth_hz,
            "parameter": self.parameter,
        }


@dataclass(frozen=True)
class ProbeOffset:
    preset: str = ""
    x_offset_mm: float = 0.0
    y_offset_mm: float = 0.0

    @classmethod
    def from_mapping(cls, settings: Mapping[str, Any] | None) -> "ProbeOffset":
        settings = settings or {}
        return cls(
            preset=str(settings.get("probe_offset_preset", "")).strip(),
            x_offset_mm=float(settings.get("probe_x_offset_mm", 0.0)),
            y_offset_mm=float(settings.get("probe_y_offset_mm", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_offset_preset": self.preset,
            "probe_x_offset_mm": self.x_offset_mm,
            "probe_y_offset_mm": self.y_offset_mm,
        }


@dataclass(frozen=True)
class ScanSettings:
    sweep: SweepSettings
    scan_volume: ScanVolume
    scan_mode: str = "step"
    step_input_mode: str = "bidirectional"
    step_x_turns: float = 0.0
    step_y_turns: float = 0.0
    x_mm_per_turn: float = 24.0
    y_mm_per_turn: float = 24.0
    step_speed_mm_s: float = 20.0
    continuous_speed_mm_s: float = 20.0
    settle_delay_s: float = 0.3
    probe_offset: ProbeOffset = field(default_factory=ProbeOffset)
    file_flag: str = ""
    connection_config: Any = None
    scan_output_dir: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    _KNOWN_KEYS: ClassVar[set[str]] = {
        "start_ghz",
        "stop_ghz",
        "frequency_step_mhz",
        "points",
        "vna_power_dbm",
        "if_bandwidth_hz",
        "parameter",
        "scan_mode",
        "x_start_mm",
        "x_stop_mm",
        "y_start_mm",
        "y_stop_mm",
        "step_x_mm",
        "step_y_mm",
        "step_input_mode",
        "step_x_turns",
        "step_y_turns",
        "x_mm_per_turn",
        "y_mm_per_turn",
        "step_speed_mm_s",
        "continuous_speed_mm_s",
        "settle_delay_s",
        "probe_offset_preset",
        "probe_x_offset_mm",
        "probe_y_offset_mm",
        "file_flag",
        "connection_config",
        "scan_output_dir",
    }

    def __post_init__(self) -> None:
        scan_mode = str(self.scan_mode).strip().lower() or "step"
        if scan_mode not in {"step", "continuous"}:
            raise ValueError(f"Unsupported scan mode: {self.scan_mode}")
        if self.step_speed_mm_s <= 0.0:
            raise ValueError("Step scan speed must be greater than 0 mm/s.")
        if abs(self.continuous_speed_mm_s) <= 1e-9:
            raise ValueError("Continuous scan speed cannot be 0 mm/s.")
        if self.settle_delay_s < 0.0:
            raise ValueError("Settle delay cannot be negative.")
        object.__setattr__(self, "scan_mode", scan_mode)

    @classmethod
    def from_mapping(cls, settings: Mapping[str, Any] | "ScanSettings") -> "ScanSettings":
        if isinstance(settings, ScanSettings):
            return settings
        settings = settings or {}
        extra = {key: value for key, value in settings.items() if key not in cls._KNOWN_KEYS}
        step_speed = float(settings.get("step_speed_mm_s", 20.0))
        return cls(
            sweep=SweepSettings.from_mapping(settings),
            scan_volume=ScanVolume(
                x_start_mm=float(settings["x_start_mm"]),
                x_stop_mm=float(settings["x_stop_mm"]),
                y_start_mm=float(settings["y_start_mm"]),
                y_stop_mm=float(settings["y_stop_mm"]),
                step_x_mm=float(settings["step_x_mm"]),
                step_y_mm=float(settings["step_y_mm"]),
            ),
            scan_mode=str(settings.get("scan_mode", "step")),
            step_input_mode=str(settings.get("step_input_mode", "bidirectional")),
            step_x_turns=float(settings.get("step_x_turns", 0.0)),
            step_y_turns=float(settings.get("step_y_turns", 0.0)),
            x_mm_per_turn=float(settings.get("x_mm_per_turn", 24.0)),
            y_mm_per_turn=float(settings.get("y_mm_per_turn", 24.0)),
            step_speed_mm_s=step_speed,
            continuous_speed_mm_s=float(settings.get("continuous_speed_mm_s", settings.get("step_speed_mm_s", 20.0))),
            settle_delay_s=float(settings.get("settle_delay_s", 0.3)),
            probe_offset=ProbeOffset.from_mapping(settings),
            file_flag=str(settings.get("file_flag", "")),
            connection_config=settings.get("connection_config"),
            scan_output_dir=None if not settings.get("scan_output_dir") else str(settings.get("scan_output_dir")),
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        settings = dict(self.extra)
        settings.update(self.sweep.to_dict())
        settings.update(
            {
                "scan_mode": self.scan_mode,
                "x_start_mm": self.scan_volume.x_start_mm,
                "x_stop_mm": self.scan_volume.x_stop_mm,
                "y_start_mm": self.scan_volume.y_start_mm,
                "y_stop_mm": self.scan_volume.y_stop_mm,
                "step_x_mm": self.scan_volume.step_x_mm,
                "step_y_mm": self.scan_volume.step_y_mm,
                "step_input_mode": self.step_input_mode,
                "step_x_turns": self.step_x_turns,
                "step_y_turns": self.step_y_turns,
                "x_mm_per_turn": self.x_mm_per_turn,
                "y_mm_per_turn": self.y_mm_per_turn,
                "step_speed_mm_s": self.step_speed_mm_s,
                "continuous_speed_mm_s": self.continuous_speed_mm_s,
                "settle_delay_s": self.settle_delay_s,
                "file_flag": self.file_flag,
            }
        )
        settings.update(self.probe_offset.to_dict())
        if self.connection_config is not None:
            settings["connection_config"] = self.connection_config
        if self.scan_output_dir:
            settings["scan_output_dir"] = self.scan_output_dir
        return settings


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
    return [
        ScanPoint(index=point.index, x_mm=point.x_mm, y_mm=point.y_mm)
        for point in plan_scan_points(volume)
    ]
