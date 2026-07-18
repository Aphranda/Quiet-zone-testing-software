from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from catr_loss_calibrator.storage.metadata_writer import write_metadata


@dataclass(frozen=True)
class ErrorReport:
    message: str
    detail: str = ""


def save_error_report(path: Path, report: ErrorReport) -> None:
    write_metadata(path, asdict(report))
