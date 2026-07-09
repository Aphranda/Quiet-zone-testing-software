import unittest

from quiet_zone_tester.domains.scan_management import PhysicalOrigin, ScanRuntimeGeometry


class ScanRuntimeGeometryTest(unittest.TestCase):
    def test_physical_target_maps_logical_point_from_physical_origin(self) -> None:
        origin = PhysicalOrigin(x_mm=100.0, y_mm=200.0, logical_x_mm=10.0, logical_y_mm=20.0)

        target = ScanRuntimeGeometry.physical_target(origin, target_x_mm=12.5, target_y_mm=17.0)

        self.assertEqual(target.x_mm, 102.5)
        self.assertEqual(target.y_mm, 197.0)

    def test_axis_moves_start_with_y_then_x_and_skip_matching_axes(self) -> None:
        self.assertEqual(ScanRuntimeGeometry.axis_moves(None, None, 1.0, 2.0), [("Y", 2.0), ("X", 1.0)])
        self.assertEqual(ScanRuntimeGeometry.axis_moves(1.0, 2.0, 1.0, 3.0), [("Y", 3.0)])
        self.assertEqual(ScanRuntimeGeometry.axis_moves(1.0, 2.0, 4.0, 2.0), [("X", 4.0)])
        self.assertEqual(ScanRuntimeGeometry.axis_moves(1.0, 2.0, 1.0, 2.0), [])

    def test_next_continuous_motion_returns_first_required_axis_and_direction(self) -> None:
        points = [(0.0, 0.0), (10.0, 0.0), (10.0, -5.0), (5.0, -5.0)]

        self.assertEqual(ScanRuntimeGeometry.next_continuous_motion(points, 0, 0.0, 0.0), ("X", 1))
        self.assertEqual(ScanRuntimeGeometry.next_continuous_motion(points, 1, 10.0, 0.0), ("Y", -1))
        self.assertEqual(ScanRuntimeGeometry.next_continuous_motion(points, 2, 10.0, -5.0), ("X", -1))
        self.assertIsNone(ScanRuntimeGeometry.next_continuous_motion(points, 3, 5.0, -5.0))

    def test_should_stop_before_continuous_sample(self) -> None:
        self.assertFalse(ScanRuntimeGeometry.should_stop_before_continuous_sample(None, 0, None))
        self.assertFalse(ScanRuntimeGeometry.should_stop_before_continuous_sample("x", 1, ("X", 1)))
        self.assertTrue(ScanRuntimeGeometry.should_stop_before_continuous_sample("X", 1, None))
        self.assertTrue(ScanRuntimeGeometry.should_stop_before_continuous_sample("X", 1, ("Y", 1)))
        self.assertTrue(ScanRuntimeGeometry.should_stop_before_continuous_sample("X", 1, ("X", -1)))

    def test_normalize_axis_name_and_positions_match(self) -> None:
        self.assertEqual(ScanRuntimeGeometry.normalize_axis_name(" y "), "Y")
        self.assertEqual(ScanRuntimeGeometry.normalize_axis_name("anything"), "X")
        self.assertTrue(ScanRuntimeGeometry.positions_match(1.0, 1.0 + 1e-10))
        self.assertFalse(ScanRuntimeGeometry.positions_match(1.0, 1.0 + 1e-6))


if __name__ == "__main__":
    unittest.main()
