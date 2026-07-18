from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from catr_loss_calibrator.diagnostics.hardware_validation import HardwareValidationRecord, save_hardware_validation_record


def test_hardware_validation_record_can_be_saved() -> None:
    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "validation.json"
        record = HardwareValidationRecord(
            date="2026-07-18",
            operator="Codex",
            vna_model="VNA-X",
            vna_serial="123",
            vna_firmware="1.0",
            link_box_model="LCD74000F",
            link_box_firmware="2.0",
            connection_mode="TCP/IP",
            test_item_id="LINK-CAL-001",
        )
        save_hardware_validation_record(path, record)
        assert path.exists()
        assert "\"test_item_id\": \"LINK-CAL-001\"" in path.read_text(encoding="utf-8")
