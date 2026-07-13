import csv
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np

from quiet_zone_tester.domains.data_management import TraceStorage
from quiet_zone_tester.models import SParameterTrace


def _trace() -> SParameterTrace:
    return SParameterTrace(
        frequency_hz=np.array([1.0e9, 2.0e9], dtype=float),
        complex_values=np.array([1.0 + 0.0j, 0.0 + 1.0j], dtype=complex),
        parameter="S21",
    )


def _settings() -> dict:
    return {
        "file_flag": "case 1",
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


class TraceStorageTest(unittest.TestCase):
    def test_save_trace_csv_writes_rows_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = TraceStorage(root_dir=Path(temp_dir))
            output_dir = Path(temp_dir) / "session"
            output_dir.mkdir()

            path = storage.save_trace_csv(
                _trace(),
                position_mm=(1.0, 2.0),
                scan_mode="step",
                file_flag="case 1",
                filename_tag="probe_右上",
                point_index=7,
                output_dir=output_dir,
                timestamp=datetime(2026, 7, 9, 12, 34, 56, 123456),
            )

            self.assertTrue(path.exists())
            self.assertEqual(
                path.name,
                "case_1_probe_右上_X1.000_Y2.000_20260709_123456_123456_step_S21_P0007.csv",
            )

            with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
                rows = list(csv.reader(csv_file))
            self.assertEqual(rows[0][0:4], ["timestamp", "flag", "scan_mode", "point_index"])
            self.assertEqual(rows[1][1:8], ["case 1", "step", "7", "1.000000", "2.000000", "", ""])
            self.assertEqual(rows[1][15:18], ["1000000000", "1", "0"])

            with (output_dir / "trace_index.csv").open("r", newline="", encoding="utf-8-sig") as index_file:
                index_rows = list(csv.reader(index_file))
            self.assertEqual(index_rows[0][-1], "filename")
            self.assertEqual(index_rows[1][1:8], ["case 1", "step", "7", "1.000000", "2.000000", "", ""])
            self.assertEqual(index_rows[1][-1], path.name)

    def test_create_scan_output_dir_writes_metadata_and_unique_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = TraceStorage(root_dir=Path(temp_dir))
            timestamp = datetime(2026, 7, 9, 12, 34, 56)

            first = storage.create_scan_output_dir(settings=_settings(), scan_mode="step", timestamp=timestamp)
            second = storage.create_scan_output_dir(settings=_settings(), scan_mode="step", timestamp=timestamp)

            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertTrue(second.name.endswith("_02"))

            metadata = json.loads((first / "scan_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["created_at"], "2026-07-09T12:34:56")
            self.assertEqual(metadata["frequency"]["points"], 2)
            self.assertEqual(metadata["scan_volume"]["point_count"], 3)


if __name__ == "__main__":
    unittest.main()
