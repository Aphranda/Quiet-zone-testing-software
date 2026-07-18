from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from catr_loss_calibrator.storage.metadata_writer import write_metadata


@dataclass(frozen=True)
class LogRecord:
    timestamp: datetime
    level: str
    message: str


def save_log_record(path: Path, record: LogRecord) -> None:
    payload = asdict(record)
    payload["timestamp"] = record.timestamp.isoformat()
    write_metadata(path, payload)
