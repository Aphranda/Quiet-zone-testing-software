from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path

import numpy as np

from catr_loss_calibrator.hardware.interfaces import SParameterTrace
from catr_loss_calibrator.storage.metadata_writer import write_metadata
from catr_loss_calibrator.storage.loss_file_storage import save_loss_record_with_policy
from catr_loss_calibrator.storage.loss_file_storage import save_loss_record
from catr_loss_calibrator.storage.models import MetadataRecord
from catr_loss_calibrator.storage.raw_trace_storage import trace_record_from_sparameter


def test_trace_record_from_sparameter_preserves_source_metadata() -> None:
    trace = SParameterTrace(
        frequency_hz=np.array([1.0, 2.0]),
        value_db=np.array([-10.0, -20.0]),
        parameter="S21",
    )
    record = trace_record_from_sparameter(trace, source_cal="LINK-CAL-001", source_step="CAL001-H")
    assert record.source_cal == "LINK-CAL-001"
    assert record.source_step == "CAL001-H"
    assert record.parameter == "S21"
    assert record.output_role == "raw_s21"


def test_save_loss_record_requires_file_identifiers() -> None:
    trace = SParameterTrace(
        frequency_hz=np.array([1.0]),
        value_db=np.array([-10.0]),
        parameter="L_TEST",
    )
    record = trace_record_from_sparameter(trace, source_cal="LINK-CAL-001", source_step="CAL001-H")
    record = record.__class__(
        frequency_hz=record.frequency_hz,
        value_db=record.value_db,
        parameter="L_TEST",
        source_cal=record.source_cal,
        source_step=record.source_step,
        band="10_15G",
        feed="F10_17G",
        horn="H10_15G",
    )
    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "loss.csv"
        save_loss_record(path, record)
        assert path.exists()
        content = path.read_text(encoding="utf-8-sig")
        assert "output_role" in content


def test_write_metadata_serializes_dataclass_records() -> None:
    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "metadata.json"
        record = MetadataRecord(
            session_id="S001",
            project_name="CATR",
            project_version="1.0",
            calibration_item="LINK-CAL-001",
            calibration_step="CAL001-H",
            instrument_snapshot={"vna": "mock"},
            link_commands=("CONFigure:LINK H, VNA1",),
            manual_confirmation=True,
            input_files=("in.csv",),
            input_hashes=("abc",),
        )
        write_metadata(path, record)
        assert path.exists()
        assert "\"session_id\": \"S001\"" in path.read_text(encoding="utf-8")


def test_save_loss_record_with_policy_builds_filename_from_feed_and_horn() -> None:
    trace = SParameterTrace(
        frequency_hz=np.array([1.0]),
        value_db=np.array([-10.0]),
        parameter="L_VNA_FEED_H",
    )
    record = trace_record_from_sparameter(trace, source_cal="LINK-CAL-002", source_step="CAL002-MAIN")
    record = record.__class__(
        frequency_hz=record.frequency_hz,
        value_db=record.value_db,
        parameter=record.parameter,
        source_cal=record.source_cal,
        source_step=record.source_step,
        band="",
        feed="F10_17G",
        horn="H10_15G",
    )
    with TemporaryDirectory() as tmpdir:
        path = save_loss_record_with_policy(Path(tmpdir), record)
        assert path.name == "L_VNA_FEED_H_10_15G_F10_17G_H10_15G.csv"
        assert path.exists()
