import unittest

from quiet_zone_tester.hardware.positioner.icl import (
    IclPositionerConfig,
    IclPositionerController,
    IclPositionerError,
    MotionMode,
)


class PositionerTimeoutTest(unittest.TestCase):
    def test_timeout_scales_with_distance_and_speed(self) -> None:
        timeout_ms = IclPositionerController.calculate_motion_timeout_ms(
            100.0,
            10.0,
            minimum_timeout_ms=1000,
        )

        self.assertEqual(timeout_ms, 20000)

    def test_timeout_honors_configured_minimum(self) -> None:
        timeout_ms = IclPositionerController.calculate_motion_timeout_ms(
            1.0,
            100.0,
            minimum_timeout_ms=8000,
        )

        self.assertEqual(timeout_ms, 8000)

    def test_timeout_uses_configurable_margin(self) -> None:
        timeout_ms = IclPositionerController.calculate_motion_timeout_ms(
            200.0,
            20.0,
            minimum_timeout_ms=1000,
            timeout_margin_s=20.0,
        )

        self.assertEqual(timeout_ms, 35000)

    def test_timeout_rejects_zero_speed(self) -> None:
        with self.assertRaises(IclPositionerError):
            IclPositionerController.calculate_motion_timeout_ms(
                10.0,
                0.0,
                minimum_timeout_ms=1000,
            )

    def test_wait_axes_stops_axis_and_reports_last_position_on_timeout(self) -> None:
        controller = IclPositionerController(IclPositionerConfig(port="COM1"))
        stopped: list[tuple[int, MotionMode]] = []
        controller.STOP_POLL_INTERVAL_S = 0.0
        controller._axis_has_stopped = lambda axis, target: (False, 0, 4.0)
        controller._execute_motion = lambda axis, mode: stopped.append((axis, mode))

        with self.assertRaisesRegex(IclPositionerError, r"target=10\.000 mm, actual=4\.000 mm, error=-6\.000 mm"):
            controller.wait_axes([2], timeout_ms=1, target_positions_mm={2: 10.0})

        self.assertEqual(stopped, [(2, MotionMode.STOP)])


if __name__ == "__main__":
    unittest.main()
