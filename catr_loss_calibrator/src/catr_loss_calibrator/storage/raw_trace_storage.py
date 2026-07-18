from __future__ import annotations

from pathlib import Path

from catr_loss_calibrator.hardware.interfaces import SParameterTrace
from catr_loss_calibrator.storage.csv_storage import save_loss_csv


def save_raw_trace(path: Path, trace: SParameterTrace, *, source_cal: str) -> None:
    save_loss_csv(
        path,
        frequency_hz=trace.frequency_hz,
        value_db=trace.value_db,
        param=trace.parameter,
        band="RAW",
        feed="RAW",
        horn="RAW",
        source_cal=source_cal,
    )

