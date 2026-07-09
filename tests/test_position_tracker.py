import os
import unittest
from dataclasses import dataclass
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quiet_zone_tester.presentation.modules.motion_control import PositionTracker


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@dataclass(frozen=True)
class _Position:
    x_mm: float
    y_mm: float


class _ImmediateTaskRunner:
    def __init__(self) -> None:
        self.calls = 0
        self.finish_immediately = True
        self.fail_with: str | None = None

    def run(
        self,
        task,
        on_success=None,
        on_error=None,
        on_finished=None,
        on_progress=None,
        progress_keyword=None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.calls += 1
        if self.fail_with is not None:
            if on_error is not None:
                on_error(self.fail_with)
        elif on_success is not None:
            on_success(task())
        if self.finish_immediately and on_finished is not None:
            on_finished()


class PositionTrackerTest(unittest.TestCase):
    def test_poll_once_ignores_disconnected_positioner(self) -> None:
        _app()
        runner = _ImmediateTaskRunner()
        tracker = PositionTracker(
            task_runner=runner,
            is_connected=lambda: False,
            query_position=lambda: _Position(1.0, 2.0),
        )

        tracker.poll_once()

        self.assertEqual(runner.calls, 0)
        self.assertFalse(tracker.task_running)

    def test_poll_once_emits_position_and_finishes(self) -> None:
        _app()
        runner = _ImmediateTaskRunner()
        positions: list[object] = []
        tracker = PositionTracker(
            task_runner=runner,
            is_connected=lambda: True,
            query_position=lambda: _Position(1.0, 2.0),
        )
        tracker.position_ready.connect(positions.append)

        tracker.poll_once()

        self.assertEqual(runner.calls, 1)
        self.assertEqual(positions, [_Position(1.0, 2.0)])
        self.assertFalse(tracker.task_running)

    def test_poll_once_does_not_start_duplicate_query(self) -> None:
        _app()
        runner = _ImmediateTaskRunner()
        runner.finish_immediately = False
        tracker = PositionTracker(
            task_runner=runner,
            is_connected=lambda: True,
            query_position=lambda: _Position(1.0, 2.0),
        )

        tracker.poll_once()
        tracker.poll_once()

        self.assertEqual(runner.calls, 1)
        self.assertTrue(tracker.task_running)
        tracker.reset()
        self.assertFalse(tracker.task_running)

    def test_poll_once_emits_failure_message(self) -> None:
        _app()
        runner = _ImmediateTaskRunner()
        runner.fail_with = "timeout"
        failures: list[str] = []
        tracker = PositionTracker(
            task_runner=runner,
            is_connected=lambda: True,
            query_position=lambda: _Position(1.0, 2.0),
        )
        tracker.position_failed.connect(failures.append)

        tracker.poll_once()

        self.assertEqual(failures, ["timeout"])
        self.assertFalse(tracker.task_running)

    def test_start_and_stop_control_timer(self) -> None:
        _app()
        runner = _ImmediateTaskRunner()
        tracker = PositionTracker(
            task_runner=runner,
            is_connected=lambda: False,
            query_position=lambda: _Position(1.0, 2.0),
        )

        tracker.start()
        self.assertTrue(tracker.is_active)

        tracker.stop()
        self.assertFalse(tracker.is_active)


if __name__ == "__main__":
    unittest.main()
