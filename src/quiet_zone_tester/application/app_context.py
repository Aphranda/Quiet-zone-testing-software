from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from quiet_zone_tester.application.task_runner import TaskRunner
from quiet_zone_tester.services import InstrumentService

if TYPE_CHECKING:
    from quiet_zone_tester.ui.main_window import MainWindow


TaskRunnerFactory = Callable[[QObject | None], TaskRunner]


@dataclass(slots=True)
class AppContext:
    """Composition root for application-level dependencies."""

    instrument_service: InstrumentService
    task_runner_factory: TaskRunnerFactory = TaskRunner

    def create_task_runner(self, parent: QObject | None = None) -> TaskRunner:
        return self.task_runner_factory(parent)

    def create_main_window(self) -> MainWindow:
        from quiet_zone_tester.ui.main_window import MainWindow

        return MainWindow(
            service=self.instrument_service,
            task_runner_factory=self.create_task_runner,
        )


def create_app_context() -> AppContext:
    return AppContext(instrument_service=InstrumentService())
