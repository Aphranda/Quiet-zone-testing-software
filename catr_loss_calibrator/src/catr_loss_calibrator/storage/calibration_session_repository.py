from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CalibrationSessionRepository:
    records: list[dict[str, str]] = field(default_factory=list)

    def append(self, record: dict[str, str]) -> None:
        self.records.append(dict(record))

