import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from quiet_zone_tester.domains.data_management import TraceStorage
from quiet_zone_tester.domains.scan_management import ProbeOffset, ScanSettings, SweepSettings


def _settings_dict() -> dict:
    return {
        "start_ghz": 10.0,
        "stop_ghz": 17.0,
        "points": 801,
        "vna_power_dbm": -10.0,
        "if_bandwidth_hz": 1000.0,
        "parameter": "s21",
        "scan_mode": "step",
        "x_start_mm": 0.0,
        "x_stop_mm": 10.0,
        "y_start_mm": 0.0,
        "y_stop_mm": 5.0,
        "step_input_mode": "bidirectional",
        "step_x_mm": 5.0,
        "step_y_mm": 5.0,
        "step_x_turns": 0.2,
        "step_y_turns": 0.2,
        "x_mm_per_turn": 24.0,
        "y_mm_per_turn": 24.0,
        "step_speed_mm_s": 20.0,
        "continuous_speed_mm_s": 20.0,
        "settle_delay_s": 0.3,
        "probe_offset_preset": "右上",
        "probe_x_offset_mm": -61.5,
        "probe_y_offset_mm": 61.5,
        "file_flag": "case 1",
        "connection_config": {"vna": {"resource_name": "MOCK"}},
        "custom_marker": "kept",
    }


class ScanSettingsTest(unittest.TestCase):
    def test_scan_settings_from_dict_normalizes_and_preserves_legacy_shape(self) -> None:
        settings = ScanSettings.from_mapping(_settings_dict())
        legacy = settings.to_dict()

        self.assertEqual(settings.sweep.parameter, "S21")
        self.assertEqual(settings.scan_mode, "step")
        self.assertEqual(settings.scan_volume.point_count, 6)
        self.assertEqual(settings.probe_offset, ProbeOffset("右上", -61.5, 61.5))
        self.assertEqual(legacy["parameter"], "S21")
        self.assertEqual(legacy["x_start_mm"], 0.0)
        self.assertEqual(legacy["probe_offset_preset"], "右上")
        self.assertEqual(legacy["connection_config"], {"vna": {"resource_name": "MOCK"}})
        self.assertEqual(legacy["custom_marker"], "kept")

    def test_sweep_settings_reject_invalid_frequency_range(self) -> None:
        with self.assertRaises(ValueError):
            SweepSettings(start_ghz=17.0, stop_ghz=10.0)

    def test_scan_settings_reject_invalid_scan_mode_and_zero_continuous_speed(self) -> None:
        invalid_mode = dict(_settings_dict(), scan_mode="bad")
        with self.assertRaises(ValueError):
            ScanSettings.from_mapping(invalid_mode)

        zero_speed = dict(_settings_dict(), scan_mode="continuous", continuous_speed_mm_s=0.0)
        with self.assertRaises(ValueError):
            ScanSettings.from_mapping(zero_speed)

    def test_continuous_scan_allows_negative_speed_for_reverse_motion(self) -> None:
        settings = ScanSettings.from_mapping(
            dict(_settings_dict(), scan_mode="continuous", continuous_speed_mm_s=-50.0)
        )

        self.assertEqual(settings.scan_mode, "continuous")
        self.assertEqual(settings.continuous_speed_mm_s, -50.0)

    def test_scan_settings_rejects_speed_above_limit(self) -> None:
        with self.assertRaises(ValueError):
            ScanSettings.from_mapping(dict(_settings_dict(), step_speed_mm_s=50.001))
        with self.assertRaises(ValueError):
            ScanSettings.from_mapping(dict(_settings_dict(), continuous_speed_mm_s=-50.001))

    def test_trace_storage_accepts_scan_settings_dataclass(self) -> None:
        scan_settings = ScanSettings.from_mapping(_settings_dict())

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = TraceStorage(root_dir=Path(temp_dir))
            output_dir = storage.create_scan_output_dir(
                settings=scan_settings,
                scan_mode=scan_settings.scan_mode,
                timestamp=datetime(2026, 7, 9, 12, 0, 0),
            )

            metadata = json.loads((output_dir / "scan_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["parameter"], "S21")
            self.assertEqual(metadata["file_flag"], "case 1")
            self.assertEqual(metadata["scan_volume"]["coordinate_mode"], "relative_to_scan_start")
            self.assertEqual(metadata["scan_volume"]["point_count"], 6)


if __name__ == "__main__":
    unittest.main()
