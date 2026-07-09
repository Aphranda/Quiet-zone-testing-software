import unittest
from datetime import datetime

from quiet_zone_tester.domains.data_management import FilenamePolicy


class FilenamePolicyTest(unittest.TestCase):
    def test_safe_part_replaces_invalid_chars_and_limits_length(self) -> None:
        policy = FilenamePolicy()

        self.assertEqual(policy.safe_part(" H/V: bad name?.csv "), "H_V__bad_name_.csv")
        self.assertEqual(len(policy.safe_part("a" * 120)), 80)

    def test_probe_offset_tag_uses_preset_and_signed_offsets(self) -> None:
        policy = FilenamePolicy()

        tag = policy.probe_offset_tag_from_settings(
            {
                "probe_offset_preset": "右上",
                "probe_x_offset_mm": -61.5,
                "probe_y_offset_mm": 61.5,
            }
        )

        self.assertEqual(tag, "probe_右上_X-61.500_Y+61.500")

    def test_trace_filename_keeps_existing_shape(self) -> None:
        policy = FilenamePolicy()

        filename = policy.trace_filename(
            parameter="S21",
            position_mm=(1.0, 2.5),
            scan_mode="step",
            file_flag="FLAG A",
            filename_tag="probe:corner",
            point_index=3,
            timestamp=datetime(2026, 7, 9, 12, 34, 56, 123456),
        )

        self.assertEqual(
            filename,
            "FLAG_A_probe_corner_X1.000_Y2.500_20260709_123456_123456_step_S21_P0003.csv",
        )

    def test_scan_folder_name_adds_probe_tag_when_present(self) -> None:
        policy = FilenamePolicy()

        folder_name = policy.scan_folder_name(
            settings={
                "file_flag": "case 1",
                "parameter": "S11",
                "probe_offset_preset": "自定义",
                "probe_x_offset_mm": 1.25,
                "probe_y_offset_mm": -2.5,
            },
            scan_mode="continuous",
            timestamp=datetime(2026, 7, 9, 12, 34, 56),
        )

        self.assertEqual(
            folder_name,
            "20260709_123456_case_1_probe_自定义_X+1.250_Y-2.500_continuous_S11",
        )


if __name__ == "__main__":
    unittest.main()
