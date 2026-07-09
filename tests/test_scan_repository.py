import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np

from quiet_zone_tester.domains.data_management import ScanRepository, TraceStorage
from quiet_zone_tester.models import SParameterTrace


def _trace() -> SParameterTrace:
    return SParameterTrace(
        frequency_hz=np.array([1.0e9, 2.0e9], dtype=float),
        complex_values=np.array([1.0 + 0.0j, 0.0 + 1.0j], dtype=complex),
        parameter="S21",
    )


def _settings() -> dict:
    return {
        "file_flag": "repo",
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
        "connection_config": {"vna": {"resource_name": "MOCK"}},
    }


class ScanRepositoryTest(unittest.TestCase):
    def test_create_session_writes_metadata_and_planned_points(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ScanRepository(TraceStorage(root_dir=Path(temp_dir)))

            session = repository.create_session(
                _settings(),
                scan_mode="step",
                timestamp=datetime(2026, 7, 10, 12, 0, 0),
            )

            self.assertTrue((session.output_dir / "scan_metadata.json").exists())
            self.assertTrue((session.output_dir / "trace_index.csv").exists())
            self.assertEqual(session.config.parameter, "S21")
            self.assertEqual(session.point_count, 3)
            self.assertEqual(session.completed_count, 0)

    def test_save_trace_appends_session_record_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ScanRepository(TraceStorage(root_dir=Path(temp_dir)))
            session = repository.create_session(_settings(), timestamp=datetime(2026, 7, 10, 12, 0, 0))

            record = repository.save_trace(
                session,
                _trace(),
                position_mm=(1.0, 2.0),
                point_index=1,
                timestamp=datetime(2026, 7, 10, 12, 1, 0),
            )

            self.assertEqual(session.completed_count, 1)
            self.assertTrue(record.file_path.exists())
            with (session.output_dir / "trace_index.csv").open("r", newline="", encoding="utf-8-sig") as index_file:
                rows = list(csv.reader(index_file))
            self.assertEqual(rows[1][3:7], ["1", "1.000000", "2.000000", "S21"])

    def test_append_event_and_finalize_update_session_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ScanRepository(TraceStorage(root_dir=Path(temp_dir)))
            session = repository.create_session(_settings(), timestamp=datetime(2026, 7, 10, 12, 0, 0))

            event = repository.append_event(session, level="info", event_type="start", message="started")
            repository.finalize(session, final_state="Completed", timestamp=datetime(2026, 7, 10, 12, 2, 0))

            self.assertEqual(event.level, "INFO")
            self.assertEqual(session.events[0].message, "started")
            self.assertTrue(session.is_finalized)
            self.assertEqual(session.final_state, "Completed")


if __name__ == "__main__":
    unittest.main()
