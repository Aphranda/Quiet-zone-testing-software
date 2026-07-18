from __future__ import annotations

from pathlib import Path

from catr_loss_calibrator.storage.csv_storage import save_loss_csv
from catr_loss_calibrator.storage.loss_file_policy import LossFilePolicy
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


def save_loss_record_with_policy(root: Path, record: TraceRecord, policy: LossFilePolicy | None = None) -> Path:
    policy = policy or LossFilePolicy()
    band = policy.band_for(record.feed, record.horn)
    path = policy.path_for(root, param=record.parameter, feed=record.feed, horn=record.horn)
    normalized_record = record.__class__(
        frequency_hz=record.frequency_hz,
        value_db=record.value_db,
        parameter=record.parameter,
        source_cal=record.source_cal,
        source_step=record.source_step,
        band=band,
        feed=record.feed.strip().upper(),
        horn=record.horn.strip().upper(),
    )
    save_loss_record(path, normalized_record)
    return path
