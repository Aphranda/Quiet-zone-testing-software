from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from quiet_zone_tester.domains.data_management.trace_storage import TraceStorage
from quiet_zone_tester.domains.scan_management import (
    ScanEvent,
    ScanSession,
    ScanSessionConfig,
    ScanSettings,
    TraceRecord,
    scan_points_from_volume,
)
from quiet_zone_tester.models import SParameterTrace


@dataclass
class ScanRepository:
    storage: TraceStorage = field(default_factory=TraceStorage)

    def create_session(
        self,
        settings: dict | ScanSettings,
        *,
        scan_mode: str | None = None,
        timestamp: datetime | None = None,
    ) -> ScanSession:
        started_at = timestamp or datetime.now()
        scan_settings = ScanSettings.from_mapping(settings)
        mode = str(scan_mode or scan_settings.scan_mode)
        output_dir = self.storage.create_scan_output_dir(
            settings=scan_settings,
            scan_mode=mode,
            timestamp=started_at,
        )
        return ScanSession(
            session_id=output_dir.name,
            config=ScanSessionConfig(
                scan_volume=scan_settings.scan_volume,
                scan_mode=mode,
                parameter=scan_settings.sweep.parameter,
                output_root=Path(self.storage.root_dir),
                file_flag=scan_settings.file_flag,
                connection_config=scan_settings.connection_config,
                settings_snapshot=scan_settings.to_dict(),
            ),
            planned_points=scan_points_from_volume(scan_settings.scan_volume),
            output_dir=output_dir,
            started_at=started_at,
        )

    def save_trace(
        self,
        session: ScanSession,
        trace: SParameterTrace,
        *,
        position_mm: tuple[float, float] | None,
        point_index: int,
        timestamp: datetime | None = None,
        filename_tag: str = "",
    ) -> TraceRecord:
        acquired_at = timestamp or datetime.now()
        path = self.storage.save_trace_csv(
            trace,
            position_mm=position_mm,
            scan_mode=session.config.scan_mode,
            file_flag=session.config.file_flag,
            filename_tag=filename_tag,
            point_index=point_index,
            output_dir=session.output_dir,
            timestamp=acquired_at,
        )
        record = TraceRecord(
            point_index=point_index,
            position_mm=position_mm,
            parameter=trace.parameter,
            trace=trace,
            acquired_at=acquired_at,
            file_path=path,
        )
        session.append_record(record)
        return record

    def append_event(
        self,
        session: ScanSession,
        *,
        level: str,
        event_type: str,
        message: str,
        timestamp: datetime | None = None,
    ) -> ScanEvent:
        event = ScanEvent(
            timestamp=timestamp or datetime.now(),
            level=str(level).strip().upper() or "INFO",
            event_type=str(event_type).strip(),
            message=str(message),
        )
        session.append_event(event)
        return event

    def finalize(
        self,
        session: ScanSession,
        *,
        final_state: str,
        timestamp: datetime | None = None,
    ) -> None:
        session.finalize(final_state, finished_at=timestamp)
