from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from catr_loss_calibrator.storage.metadata_writer import write_metadata


@dataclass
class CalibrationSessionRepository:
    records: list[dict[str, Any]] = field(default_factory=list)

    def append(self, record: dict[str, Any]) -> None:
        self.records.append(dict(record))

    def append_dataclass(self, record: object) -> None:
        self.records.append(asdict(record) if hasattr(record, "__dataclass_fields__") else dict(record))  # type: ignore[arg-type]

    def save(self, path: Path) -> None:
        write_metadata(path, {"records": self.records})
