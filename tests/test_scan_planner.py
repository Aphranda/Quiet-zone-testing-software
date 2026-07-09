import unittest

from quiet_zone_tester.domains.scan_management import ScanPlanner
from quiet_zone_tester.models import ScanVolume


class ScanPlannerTest(unittest.TestCase):
    def test_x_line_scan_keeps_x_direction_and_constant_y(self) -> None:
        volume = ScanVolume(0.0, 10.0, 2.0, 2.0, 5.0, 1.0)

        plan = ScanPlanner().plan(volume)

        self.assertEqual(
            [point.position_mm for point in plan.points],
            [(0.0, 2.0), (5.0, 2.0), (10.0, 2.0)],
        )

    def test_y_line_scan_keeps_y_direction_and_constant_x(self) -> None:
        volume = ScanVolume(3.0, 3.0, 0.0, 10.0, 1.0, 5.0)

        plan = ScanPlanner().plan(volume)

        self.assertEqual(
            [point.position_mm for point in plan.points],
            [(3.0, 0.0), (3.0, 5.0), (3.0, 10.0)],
        )

    def test_two_dimensional_scan_uses_snake_order(self) -> None:
        volume = ScanVolume(0.0, 10.0, 0.0, 10.0, 5.0, 10.0)

        plan = ScanPlanner().plan(volume)

        self.assertEqual(
            [point.position_mm for point in plan.points],
            [
                (0.0, 0.0),
                (5.0, 0.0),
                (10.0, 0.0),
                (10.0, 10.0),
                (5.0, 10.0),
                (0.0, 10.0),
            ],
        )

    def test_reverse_scan_preserves_start_stop_and_snake_order(self) -> None:
        volume = ScanVolume(10.0, 0.0, 10.0, 0.0, 5.0, 5.0)

        plan = ScanPlanner().plan(volume)

        self.assertEqual(
            [point.position_mm for point in plan.points],
            [
                (10.0, 10.0),
                (5.0, 10.0),
                (0.0, 10.0),
                (0.0, 5.0),
                (5.0, 5.0),
                (10.0, 5.0),
                (10.0, 0.0),
                (5.0, 0.0),
                (0.0, 0.0),
            ],
        )

    def test_axis_includes_stop_when_step_does_not_divide_span(self) -> None:
        volume = ScanVolume(0.0, 10.0, 0.0, 0.0, 6.0, 1.0)

        plan = ScanPlanner().plan(volume)

        self.assertEqual([point.position_mm for point in plan.points], [(0.0, 0.0), (6.0, 0.0), (10.0, 0.0)])
        self.assertEqual(ScanPlanner().point_count(volume), 3)
        self.assertEqual(volume.point_count, 3)


if __name__ == "__main__":
    unittest.main()
