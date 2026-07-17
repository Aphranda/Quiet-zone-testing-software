import unittest
from dataclasses import dataclass

import quiet_zone_tester.domains.motion_control.motion_service as motion_service_module
from quiet_zone_tester.domains.motion_control import MotionService, MotionServiceError
from quiet_zone_tester.hardware import Position


@dataclass
class _Config:
    x_axis: int = 2
    y_axis: int = 3


class _Positioner:
    def __init__(self, connected: bool = True) -> None:
        self._connected = connected
        self._position = Position(1.0, 2.0)
        self._config = _Config()
        self.position_sequence: list[Position] = []
        self.calls: list[tuple] = []
        self.cancelled = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def position(self) -> Position:
        self.calls.append(("position",))
        if self.position_sequence:
            self._position = self.position_sequence.pop(0)
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

    def update_runtime_config(self, **kwargs) -> None:
        self.calls.append(("update_runtime_config", kwargs))


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

    def test_update_runtime_config_delegates_parsed_axis_and_scale_values(self) -> None:
        positioner = _Positioner()

        MotionService(positioner).update_runtime_config(
            {
                "x_axis": 4,
                "y_axis": 5,
                "pulses_per_mm": 100.0,
                "x_units_per_turn": 2000.0,
                "x_mm_per_turn": 2.0,
                "y_pulses_per_mm": 120.0,
                "default_speed": 25.0,
            }
        )

        self.assertEqual(positioner.calls[0][0], "update_runtime_config")
        self.assertEqual(
            positioner.calls[0][1],
            {
                "x_axis": 4,
                "y_axis": 5,
                "pulses_per_mm": 1000.0,
                "x_pulses_per_mm": 1000.0,
                "y_pulses_per_mm": 120.0,
                "default_speed": 25.0,
                "motion_timeout_margin_s": 20.0,
            },
        )

    def test_update_runtime_config_passes_motion_timeout_margin(self) -> None:
        positioner = _Positioner()

        MotionService(positioner).update_runtime_config({"motion_timeout_margin_s": 30.0})

        self.assertEqual(positioner.calls[0][0], "update_runtime_config")
        self.assertEqual(positioner.calls[0][1]["motion_timeout_margin_s"], 30.0)

    def test_update_runtime_config_rejects_invalid_scale(self) -> None:
        positioner = _Positioner()

        with self.assertRaises(MotionServiceError):
            MotionService(positioner).update_runtime_config({"pulses_per_mm": 0.0})

    def test_move_axis_to_uses_axis_specific_fallback_when_controller_lacks_axis_move(self) -> None:
        positioner = _Positioner()
        service = MotionService(positioner)

        y_position = service.move_axis_to("Y", 7.0, 11.0)
        x_position = service.move_axis_to("X", -3.0, 12.0)

        self.assertEqual(y_position, Position(1.0, 7.0))
        self.assertEqual(x_position, Position(-3.0, 7.0))
        self.assertEqual(
            positioner.calls,
            [
                ("position",),
                ("move_to", 1.0, 7.0, 11.0),
                ("position",),
                ("move_to", -3.0, 7.0, 12.0),
            ],
        )

    def test_jog_axis_until_starts_jog_and_returns_active_axis_when_target_crossed(self) -> None:
        positioner = _Positioner()
        positioner.position_sequence = [Position(0.0, 0.0), Position(2.0, 0.0)]

        active_axis_name, active_direction = MotionService(positioner).jog_axis_until(
            axis_name="X",
            target_position_mm=1.0,
            speed_mm_s=10.0,
            active_axis_name=None,
            active_direction=0,
            wait_if_paused=lambda: None,
            raise_if_stopped=lambda: None,
            is_paused=lambda: False,
        )

        self.assertEqual((active_axis_name, active_direction), ("X", 1))
        self.assertEqual(positioner.calls, [("position",), ("jog_axis", 2, 10.0), ("position",)])

    def test_jog_axis_until_stops_axis_when_feedback_freezes(self) -> None:
        positioner = _Positioner()
        positioner._position = Position(0.0, 0.0)
        original_frozen_timeout = motion_service_module.JOG_FROZEN_TIMEOUT_S
        original_poll_interval = motion_service_module.JOG_POLL_INTERVAL_S
        motion_service_module.JOG_FROZEN_TIMEOUT_S = 0.0
        motion_service_module.JOG_POLL_INTERVAL_S = 0.0
        try:
            with self.assertRaises(MotionServiceError):
                MotionService(positioner).jog_axis_until(
                    axis_name="X",
                    target_position_mm=1.0,
                    speed_mm_s=10.0,
                    active_axis_name=None,
                    active_direction=0,
                    wait_if_paused=lambda: None,
                    raise_if_stopped=lambda: None,
                    is_paused=lambda: False,
                )
        finally:
            motion_service_module.JOG_FROZEN_TIMEOUT_S = original_frozen_timeout
            motion_service_module.JOG_POLL_INTERVAL_S = original_poll_interval

        self.assertIn(("stop_axis", 2), positioner.calls)

    def test_stop_axis_by_name_uses_axis_config_and_swallows_driver_errors(self) -> None:
        positioner = _Positioner()
        positioner._config = _Config(x_axis=4, y_axis=5)

        MotionService(positioner).stop_axis_by_name_quietly("Y")

        self.assertEqual(positioner.calls, [("stop_axis", 5)])

    def test_stop_all_quietly_delegates_when_connected(self) -> None:
        positioner = _Positioner()

        MotionService(positioner).stop_all_quietly()

        self.assertEqual(positioner.calls, [("stop_all",)])


if __name__ == "__main__":
    unittest.main()
