from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from quiet_zone_tester.domains.data_management.filename_policy import FilenamePolicy
from quiet_zone_tester.domains.scan_management import ScanSettings
from quiet_zone_tester.models import SParameterTrace, ScanVolume


@dataclass
class TraceStorage:
    root_dir: Path | None = None
    filename_policy: FilenamePolicy = field(default_factory=FilenamePolicy)

    def __post_init__(self) -> None:
        if self.root_dir is None:
            self.root_dir = Path.cwd() / "test_results"
        else:
            self.root_dir = Path(self.root_dir)

    def save_trace_csv(
        self,
        trace: SParameterTrace,
        *,
        position_mm: tuple[float, float] | None,
        scan_mode: str,
        file_flag: str = "",
        filename_tag: str = "",
        point_index: int | None = None,
        output_dir: Path | None = None,
        timestamp: datetime | None = None,
        logical_position_mm: tuple[float, float] | None = None,
        physical_target_mm: tuple[float, float] | None = None,
        actual_position_mm: tuple[float, float] | None = None,
        position_error_mm: tuple[float, float] | None = None,
    ) -> Path:
        timestamp = timestamp or datetime.now()
        should_write_index = output_dir is not None
        target_dir = Path(output_dir) if output_dir is not None else Path(self.root_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = self.filename_policy.trace_filename(
            parameter=trace.parameter,
            position_mm=position_mm,
            scan_mode=scan_mode,
            file_flag=file_flag,
            filename_tag=filename_tag,
            point_index=point_index,
            timestamp=timestamp,
        )
        path = target_dir / filename
        self._write_trace_csv(
            path=path,
            trace=trace,
            timestamp=timestamp,
            position_mm=position_mm,
            scan_mode=scan_mode,
            file_flag=file_flag,
            point_index=point_index,
            logical_position_mm=logical_position_mm,
            physical_target_mm=physical_target_mm,
            actual_position_mm=actual_position_mm,
            position_error_mm=position_error_mm,
        )
        if should_write_index:
            self.append_trace_index(
                output_dir=target_dir,
                trace_path=path,
                timestamp=timestamp,
                trace=trace,
                position_mm=position_mm,
                scan_mode=scan_mode,
                file_flag=file_flag,
                point_index=point_index,
                logical_position_mm=logical_position_mm,
                physical_target_mm=physical_target_mm,
                actual_position_mm=actual_position_mm,
                position_error_mm=position_error_mm,
            )
        return path

    def create_scan_output_dir(
        self,
        *,
        settings: dict | ScanSettings,
        scan_mode: str,
        timestamp: datetime | None = None,
    ) -> Path:
        timestamp = timestamp or datetime.now()
        settings = self._settings_dict(settings)
        folder_name = self.filename_policy.scan_folder_name(
            settings=settings,
            scan_mode=scan_mode,
            timestamp=timestamp,
        )

        output_dir = Path(self.root_dir) / folder_name
        suffix = 1
        while output_dir.exists():
            suffix += 1
            output_dir = Path(self.root_dir) / f"{folder_name}_{suffix:02d}"

        output_dir.mkdir(parents=True, exist_ok=False)
        self.write_scan_metadata(output_dir, settings, scan_mode, timestamp)
        self.write_trace_index_header(output_dir)
        return output_dir

    def write_scan_metadata(
        self,
        output_dir: Path,
        settings: dict | ScanSettings,
        scan_mode: str,
        timestamp: datetime,
    ) -> None:
        settings = self._settings_dict(settings)
        volume = self._build_scan_volume(settings)
        connection_config = settings.get("connection_config")
        metadata = {
            "created_at": timestamp.isoformat(timespec="seconds"),
            "scan_mode": scan_mode,
            "file_flag": str(settings.get("file_flag", "")),
            "parameter": str(settings.get("parameter", "")),
            "frequency": {
                "start_ghz": float(settings.get("start_ghz", 0.0)),
                "stop_ghz": float(settings.get("stop_ghz", 0.0)),
                "step_mhz": float(settings.get("frequency_step_mhz", 0.0)),
                "points": int(settings.get("points", 0)),
                "if_bandwidth_hz": float(settings.get("if_bandwidth_hz", 0.0)),
                "vna_power_dbm": float(settings.get("vna_power_dbm", 0.0)),
            },
            "scan_volume": {
                "coordinate_mode": "relative_to_scan_start",
                "x_start_mm": volume.x_start_mm,
                "x_stop_mm": volume.x_stop_mm,
                "y_start_mm": volume.y_start_mm,
                "y_stop_mm": volume.y_stop_mm,
                "step_x_mm": volume.step_x_mm,
                "step_y_mm": volume.step_y_mm,
                "point_count": volume.point_count,
            },
            "motion": {
                "step_speed_mm_s": float(settings.get("step_speed_mm_s", 0.0)),
                "continuous_speed_mm_s": float(settings.get("continuous_speed_mm_s", 0.0)),
                "settle_delay_s": float(settings.get("settle_delay_s", 0.0)),
            },
            "connection": self.metadata_safe_value(connection_config),
        }
        (output_dir / "scan_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def write_trace_index_header(self, output_dir: Path) -> None:
        with (output_dir / "trace_index.csv").open("w", newline="", encoding="utf-8-sig") as index_file:
            writer = csv.writer(index_file)
            writer.writerow(
                [
                    "saved_at",
                    "flag",
                    "scan_mode",
                    "point_index",
                    "x_mm",
                    "y_mm",
                    "logical_x_mm",
                    "logical_y_mm",
                    "physical_target_x_mm",
                    "physical_target_y_mm",
                    "actual_x_mm",
                    "actual_y_mm",
                    "error_x_mm",
                    "error_y_mm",
                    "parameter",
                    "frequency_start_hz",
                    "frequency_stop_hz",
                    "frequency_points",
                    "filename",
                ]
            )

    def append_trace_index(
        self,
        *,
        output_dir: Path,
        trace_path: Path,
        timestamp: datetime,
        trace: SParameterTrace,
        position_mm: tuple[float, float] | None,
        scan_mode: str,
        file_flag: str,
        point_index: int | None,
        logical_position_mm: tuple[float, float] | None = None,
        physical_target_mm: tuple[float, float] | None = None,
        actual_position_mm: tuple[float, float] | None = None,
        position_error_mm: tuple[float, float] | None = None,
    ) -> None:
        index_path = output_dir / "trace_index.csv"
        if not index_path.exists():
            self.write_trace_index_header(output_dir)

        x_mm = "" if position_mm is None else f"{position_mm[0]:.6f}"
        y_mm = "" if position_mm is None else f"{position_mm[1]:.6f}"
        logical_x_mm, logical_y_mm = self._format_optional_pair(logical_position_mm)
        physical_target_x_mm, physical_target_y_mm = self._format_optional_pair(physical_target_mm)
        actual_x_mm, actual_y_mm = self._format_optional_pair(actual_position_mm)
        error_x_mm, error_y_mm = self._format_optional_pair(position_error_mm)
        with index_path.open("a", newline="", encoding="utf-8-sig") as index_file:
            writer = csv.writer(index_file)
            writer.writerow(
                [
                    timestamp.isoformat(timespec="microseconds"),
                    file_flag,
                    scan_mode,
                    "" if point_index is None else point_index,
                    x_mm,
                    y_mm,
                    logical_x_mm,
                    logical_y_mm,
                    physical_target_x_mm,
                    physical_target_y_mm,
                    actual_x_mm,
                    actual_y_mm,
                    error_x_mm,
                    error_y_mm,
                    trace.parameter,
                    f"{float(trace.frequency_hz[0]):.12g}",
                    f"{float(trace.frequency_hz[-1]):.12g}",
                    int(trace.frequency_hz.size),
                    trace_path.name,
                ]
            )

    @staticmethod
    def metadata_safe_value(value: Any) -> Any:
        try:
            json.dumps(value)
        except TypeError:
            return str(value)
        return value

    @staticmethod
    def _write_trace_csv(
        *,
        path: Path,
        trace: SParameterTrace,
        timestamp: datetime,
        position_mm: tuple[float, float] | None,
        scan_mode: str,
        file_flag: str,
        point_index: int | None,
        logical_position_mm: tuple[float, float] | None = None,
        physical_target_mm: tuple[float, float] | None = None,
        actual_position_mm: tuple[float, float] | None = None,
        position_error_mm: tuple[float, float] | None = None,
    ) -> None:
        x_mm = "" if position_mm is None else f"{position_mm[0]:.6f}"
        y_mm = "" if position_mm is None else f"{position_mm[1]:.6f}"
        logical_x_mm, logical_y_mm = TraceStorage._format_optional_pair(logical_position_mm)
        physical_target_x_mm, physical_target_y_mm = TraceStorage._format_optional_pair(physical_target_mm)
        actual_x_mm, actual_y_mm = TraceStorage._format_optional_pair(actual_position_mm)
        error_x_mm, error_y_mm = TraceStorage._format_optional_pair(position_error_mm)
        with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(
                [
                    "timestamp",
                    "flag",
                    "scan_mode",
                    "point_index",
                    "x_mm",
                    "y_mm",
                    "logical_x_mm",
                    "logical_y_mm",
                    "physical_target_x_mm",
                    "physical_target_y_mm",
                    "actual_x_mm",
                    "actual_y_mm",
                    "error_x_mm",
                    "error_y_mm",
                    "parameter",
                    "frequency_hz",
                    "real",
                    "imag",
                    "magnitude_db",
                    "phase_deg",
                ]
            )
            for frequency_hz, value, magnitude_db, phase_deg in zip(
                trace.frequency_hz,
                trace.complex_values,
                trace.magnitude_db,
                trace.phase_deg,
            ):
                writer.writerow(
                    [
                        timestamp.isoformat(timespec="microseconds"),
                        file_flag,
                        scan_mode,
                        "" if point_index is None else point_index,
                        x_mm,
                        y_mm,
                        logical_x_mm,
                        logical_y_mm,
                        physical_target_x_mm,
                        physical_target_y_mm,
                        actual_x_mm,
                        actual_y_mm,
                        error_x_mm,
                        error_y_mm,
                        trace.parameter,
                        f"{float(frequency_hz):.12g}",
                        f"{float(value.real):.12g}",
                        f"{float(value.imag):.12g}",
                        f"{float(magnitude_db):.12g}",
                        f"{float(phase_deg):.12g}",
                    ]
                )

    @staticmethod
    def _settings_dict(settings: dict | ScanSettings) -> dict:
        return ScanSettings.from_mapping(settings).to_dict()

    @staticmethod
    def _format_optional_pair(pair: tuple[float, float] | None) -> tuple[str, str]:
        if pair is None:
            return "", ""
        return f"{float(pair[0]):.6f}", f"{float(pair[1]):.6f}"

    @staticmethod
    def _build_scan_volume(settings: dict | ScanSettings) -> ScanVolume:
        return ScanSettings.from_mapping(settings).scan_volume
