from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from catr_loss_calibrator.storage.metadata_writer import write_metadata


@dataclass(frozen=True)
class HardwareValidationRecord:
    date: str
    operator: str
    vna_model: str
    vna_serial: str
    vna_firmware: str
    link_box_model: str
    link_box_firmware: str
    connection_mode: str
    test_item_id: str
    notes: str = ""


def save_hardware_validation_record(path: Path, record: HardwareValidationRecord) -> None:
    write_metadata(path, record)
