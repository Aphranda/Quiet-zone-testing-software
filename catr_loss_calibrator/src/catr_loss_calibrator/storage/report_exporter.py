from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from catr_loss_calibrator.storage.metadata_writer import write_metadata


def export_session_report(path: Path, session: dict[str, Any]) -> None:
    suffix = path.suffix.lower()
    path.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".json":
        write_metadata(path, session)
        return
    if suffix == ".csv":
        _export_session_csv(path, session)
        return
    raise ValueError("Unsupported report format.")


def _export_session_csv(path: Path, session: dict[str, Any]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["key", "value"])
        for key, value in session.items():
            writer.writerow([key, value])
