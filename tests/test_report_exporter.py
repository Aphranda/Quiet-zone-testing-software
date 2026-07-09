import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np

from quiet_zone_tester.domains.data_management import ReportExporter, ScanRepository, TraceStorage
from quiet_zone_tester.models import SParameterTrace


def _settings() -> dict:
    return {
        "file_flag": "report",
        "parameter": "S21",
        "start_ghz": 1.0,
        "stop_ghz": 2.0,
        "points": 2,
        "if_bandwidth_hz": 1000.0,
        "vna_power_dbm": -10.0,
        "x_start_mm": 0.0,
        "x_stop_mm": 10.0,
        "y_start_mm": 0.0,
        "y_stop_mm": 0.0,
        "step_x_mm": 5.0,
        "step_y_mm": 5.0,
        "step_speed_mm_s": 20.0,
        "continuous_speed_mm_s": 20.0,
        "settle_delay_s": 0.3,
    }


def _trace() -> SParameterTrace:
    return SParameterTrace(
        frequency_hz=np.array([1.0e9, 2.0e9], dtype=float),
        complex_values=np.array([1.0 + 0.0j, 0.0 + 1.0j], dtype=complex),
        parameter="S21",
    )


class ReportExporterTest(unittest.TestCase):
    def test_export_markdown_writes_session_summary_and_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ScanRepository(TraceStorage(root_dir=Path(temp_dir)))
            session = repository.create_session(_settings(), timestamp=datetime(2026, 7, 10, 12, 0, 0))
            repository.save_trace(
                session,
                _trace(),
                position_mm=(1.0, 2.0),
                point_index=1,
                timestamp=datetime(2026, 7, 10, 12, 1, 0),
            )
            repository.append_event(session, level="info", event_type="finish", message="done")
            repository.finalize(session, final_state="Completed", timestamp=datetime(2026, 7, 10, 12, 2, 0))

            report_path = ReportExporter().export_markdown(session)

            text = report_path.read_text(encoding="utf-8")
            self.assertIn("# 扫描报告", text)
            self.assertIn("- 状态：Completed", text)
            self.assertIn("| 1 | 1.000000 | 2.000000 | S21 |", text)
            self.assertIn("| 2026-07-10T", text)


if __name__ == "__main__":
    unittest.main()
