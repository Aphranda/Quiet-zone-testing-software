import unittest

from quiet_zone_tester.domains.scan_management import scan_points_from_volume
from quiet_zone_tester.models import ScanVolume


class ScanPointsTest(unittest.TestCase):
    def test_scan_points_from_volume_keeps_snake_order_and_indices(self) -> None:
        volume = ScanVolume(
            x_start_mm=0.0,
            x_stop_mm=10.0,
            y_start_mm=0.0,
            y_stop_mm=10.0,
            step_x_mm=5.0,
            step_y_mm=10.0,
        )

        points = scan_points_from_volume(volume)

        self.assertEqual([point.index for point in points], [1, 2, 3, 4, 5, 6])
        self.assertEqual(
            [point.position_mm for point in points],
            [
                (0.0, 0.0),
                (5.0, 0.0),
                (10.0, 0.0),
                (10.0, 10.0),
                (5.0, 10.0),
                (0.0, 10.0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
