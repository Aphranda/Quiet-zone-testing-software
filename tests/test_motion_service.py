import unittest

from quiet_zone_tester.domains.motion_control import MotionService, MotionServiceError
from quiet_zone_tester.drivers import Position


class _Positioner:
    def __init__(self, connected: bool = True) -> None:
        self._connected = connected
        self._position = Position(1.0, 2.0)
        self.calls: list[tuple] = []
        self.cancelled = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def position(self) -> Position:
        self.calls.append(("position",))
        return self._position

    def move_to(self, x_mm: float, y_mm: float, speed_mm_s: float | None = None) -> Position:
        self.calls.append(("move_to", x_mm, y_mm, speed_mm_s))
        self._position = Position(x_mm, y_mm)
        return self._position

    def jog_axis(self, axis: int, speed_mm_s: float) -> None:
        self.calls.append(("jog_axis", axis, speed_mm_s))

    def stop_axis(self, axis: int) -> None:
        self.calls.append(("stop_axis", axis))

    def stop_all(self) -> None:
        self.calls.append(("stop_all",))

    def cancel_motion(self) -> None:
        self.cancelled = True


class MotionServiceTest(unittest.TestCase):
    def test_manual_motion_commands_delegate_to_positioner(self) -> None:
        positioner = _Positioner()
        service = MotionService(positioner)

        service.jog_axis(2, 10.0)
        absolute = service.move_absolute(3.0, 4.0, 20.0)
        relative = service.move_relative(1.5, -0.5, 30.0)
        service.stop_axis(3)
        service.stop_all()

        self.assertEqual(absolute, Position(3.0, 4.0))
        self.assertEqual(relative, Position(4.5, 3.5))
        self.assertEqual(
            positioner.calls,
            [
                ("jog_axis", 2, 10.0),
                ("move_to", 3.0, 4.0, 20.0),
                ("position",),
                ("move_to", 4.5, 3.5, 30.0),
                ("stop_axis", 3),
                ("stop_all",),
            ],
        )

    def test_query_position_returns_current_position(self) -> None:
        positioner = _Positioner()

        self.assertEqual(MotionService(positioner).query_position(), Position(1.0, 2.0))

    def test_rejects_unconnected_positioner(self) -> None:
        service = MotionService(_Positioner(connected=False))

        with self.assertRaises(MotionServiceError):
            service.jog_axis(2, 10.0)
        with self.assertRaises(MotionServiceError):
            service.query_position()

    def test_cancel_motion_is_optional(self) -> None:
        positioner = _Positioner()

        MotionService(positioner).cancel_motion_if_supported()

        self.assertTrue(positioner.cancelled)


if __name__ == "__main__":
    unittest.main()
