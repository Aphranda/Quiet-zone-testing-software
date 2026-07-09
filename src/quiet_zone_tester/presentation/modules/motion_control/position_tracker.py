from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from PySide6.QtCore import QObject, QTimer, Signal


class PositionTaskRunner(Protocol):
    def run(
        self,
        task: Callable[..., Any],
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_finished: Callable[[], None] | None = None,
        on_progress: Callable[[Any], None] | None = None,
        progress_keyword: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        ...


class PositionTracker(QObject):
    """Polls position while a positioner move is running."""

    position_ready = Signal(object)
    position_failed = Signal(str)

    def __init__(
        self,
        *,
        task_runner: PositionTaskRunner,
        is_connected: Callable[[], bool],
        query_position: Callable[[], Any],
        interval_ms: int = 1000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._task_runner = task_runner
        self._is_connected = is_connected
        self._query_position = query_position
        self._task_running = False
        self._timer = QTimer(self)
        self._timer.setInterval(int(interval_ms))
        self._timer.timeout.connect(self.poll_once)

    @property
    def task_running(self) -> bool:
        return self._task_running

    @property
    def is_active(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        self.poll_once()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        self.stop()
        self._task_running = False

    def poll_once(self) -> None:
        if self._task_running:
            return
        if not self._is_connected():
            return

        self._task_running = True
        self._task_runner.run(
            self._query_position,
            on_success=self.position_ready.emit,
            on_error=self.position_failed.emit,
            on_finished=self._finish_poll,
        )

    def _finish_poll(self) -> None:
        self._task_running = False
