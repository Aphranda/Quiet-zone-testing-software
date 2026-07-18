from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from catr_loss_calibrator.diagnostics.error_report import ErrorReport, save_error_report
from catr_loss_calibrator.diagnostics.log_record import LogRecord, save_log_record
from catr_loss_calibrator.storage.calibration_session_repository import CalibrationSessionRepository
from catr_loss_calibrator.storage.report_exporter import export_session_report


def test_session_repository_saves_records() -> None:
    repo = CalibrationSessionRepository()
    repo.append({"session_id": "S1", "status": "done"})
    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "session.json"
        repo.save(path)
        assert path.exists()
        assert "\"session_id\": \"S1\"" in path.read_text(encoding="utf-8")


def test_log_and_error_records_can_be_saved() -> None:
    with TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "log.json"
        err_path = Path(tmpdir) / "error.json"
        save_log_record(log_path, LogRecord(timestamp=datetime(2026, 7, 18, 12, 0, 0), level="INFO", message="ok"))
        save_error_report(err_path, ErrorReport(message="boom", detail="trace"))
        assert log_path.exists()
        assert err_path.exists()


def test_session_report_export_supports_json_and_csv() -> None:
    session = {"session_id": "S1", "item": "LINK-CAL-001"}
    with TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "report.json"
        csv_path = Path(tmpdir) / "report.csv"
        export_session_report(json_path, session)
        export_session_report(csv_path, session)
        assert json_path.exists()
        assert csv_path.exists()
