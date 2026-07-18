from __future__ import annotations

from pathlib import Path

from catr_loss_calibrator.storage.csv_storage import save_loss_csv
from catr_loss_calibrator.storage.models import TraceRecord


def save_loss_record(path: Path, record: TraceRecord) -> None:
    if not record.band or not record.feed or not record.horn:
        raise ValueError("TraceRecord.band/feed/horn are required for final loss file output.")
    save_loss_csv(
        path,
        frequency_hz=record.frequency_hz,
        value_db=record.value_db,
        param=record.parameter,
        band=record.band,
        feed=record.feed,
        horn=record.horn,
        source_cal=record.source_cal,
    )
