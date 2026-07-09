import json
import unittest
from datetime import datetime
from pathlib import Path

from quiet_zone_tester.domains.scan_management import (
    ScanSession,
    ScanSessionConfig,
    TraceRecord,
)
from quiet_zone_tester.models import ScanVolume


def _session() -> ScanSession:
    config = ScanSessionConfig(
        scan_volume=ScanVolume(0.0, 10.0, 0.0, 0.0, 5.0, 5.0),
        scan_mode="X",
        parameter="S21",
        output_root=Path("test_results"),
        file_flag="H_M_X",
    )
    return ScanSession(
        session_id="session-001",
        config=config,
        planned_points=[],
        output_dir=Path("test_results/session-001"),
        started_at=datetime(2026, 7, 9, 12, 0, 0),
    )


class ScanSessionTest(unittest.TestCase):
    def test_metadata_summary_is_json_serializable(self) -> None:
        session = _session()
        session.append_record(
            TraceRecord(
                point_index=1,
                position_mm=(0.0, 0.0),
                parameter="S21",
                trace=None,
                acquired_at=datetime(2026, 7, 9, 12, 0, 1),
                file_path=Path("test_results/session-001/trace.csv"),
            )
        )
        session.finalize("Completed", datetime(2026, 7, 9, 12, 0, 2))

        payload = session.metadata_summary()

        self.assertEqual(payload["completed_count"], 1)
        self.assertEqual(payload["final_state"], "Completed")
        json.dumps(payload)

    def test_rejects_record_after_finalize(self) -> None:
        session = _session()
        session.finalize("Completed", datetime(2026, 7, 9, 12, 0, 2))

        with self.assertRaises(ValueError):
            session.append_record(
                TraceRecord(
                    point_index=1,
                    position_mm=(0.0, 0.0),
                    parameter="S21",
                    trace=None,
                    acquired_at=datetime(2026, 7, 9, 12, 0, 3),
                )
            )


if __name__ == "__main__":
    unittest.main()
