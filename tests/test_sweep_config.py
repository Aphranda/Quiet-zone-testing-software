import unittest

from quiet_zone_tester.models import DEFAULT_FREQUENCY_STEP_MHZ, calculate_sweep_points


class SweepConfigTest(unittest.TestCase):
    def test_default_five_mhz_step_scales_points_with_frequency_span(self) -> None:
        self.assertEqual(DEFAULT_FREQUENCY_STEP_MHZ, 5.0)
        self.assertEqual(calculate_sweep_points(10.0, 17.0), 1401)
        self.assertEqual(calculate_sweep_points(10.0, 40.0), 6001)

    def test_sweep_points_has_minimum_of_two(self) -> None:
        self.assertEqual(calculate_sweep_points(10.0, 10.0), 2)


if __name__ == "__main__":
    unittest.main()
