from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

logger = logging.getLogger(__name__)


class Worker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    progressed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        task: Callable[..., Any],
        *args: Any,
        progress_keyword: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self._task = task
        self._args = args
        self._kwargs = dict(kwargs)
        if progress_keyword is not None:
            self._kwargs[progress_keyword] = self._emit_progress

    @Slot()
    def run(self) -> None:
        try:
            result = self._task(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - worker boundary reports all task failures.
            logger.exception("Background task failed.")
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()

    def _emit_progress(self, *values: Any) -> None:
        if len(values) == 1:
            self.progressed.emit(values[0])
        else:
            self.progressed.emit(values)


class TaskCallbacks(QObject):
    """Runs task callbacks in the QObject thread that owns this object."""

    def __init__(
        self,
        on_success: Callable[[Any], None] | None,
        on_error: Callable[[str], None] | None,
        on_finished: Callable[[], None] | None,
        on_progress: Callable[[Any], None] | None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_success = on_success
        self._on_error = on_error
        self._on_finished = on_finished
        self._on_progress = on_progress

    @Slot(object)
    def handle_success(self, result: Any) -> None:
        if self._on_success is None:
            return
        try:
            self._on_success(result)
        except Exception:
            logger.exception("Task success callback failed.")

    @Slot(str)
    def handle_error(self, message: str) -> None:
        if self._on_error is None:
            return
        try:
            self._on_error(message)
        except Exception:
            logger.exception("Task error callback failed.")

    @Slot(object)
    def handle_progress(self, payload: Any) -> None:
        if self._on_progress is None:
            return
        try:
            self._on_progress(payload)
        except Exception:
            logger.exception("Task progress callback failed.")

    @Slot()
    def handle_finished(self) -> None:
        try:
            if self._on_finished is not None:
                self._on_finished()
        except Exception:
            logger.exception("Task finished callback failed.")
        finally:
            self.deleteLater()


class TaskRunner(QObject):
    """Small QThread manager for non-blocking UI-triggered workflows."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running: list[tuple[QThread, Worker, TaskCallbacks]] = []

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
        thread = QThread(self)
        worker = Worker(
            task,
            *args,
            progress_keyword=progress_keyword or ("on_progress" if on_progress is not None else None),
            **kwargs,
        )
        callbacks = TaskCallbacks(on_success, on_error, on_finished, on_progress, self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.succeeded.connect(callbacks.handle_success)
        worker.failed.connect(callbacks.handle_error)
        worker.progressed.connect(callbacks.handle_progress)
        worker.finished.connect(callbacks.handle_finished)

        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._release_thread(thread))

        self._running.append((thread, worker, callbacks))
        thread.start()

    def _release_thread(self, thread: QThread) -> None:
        self._running = [
            (active_thread, worker, callbacks)
            for active_thread, worker, callbacks in self._running
            if active_thread is not thread
        ]
