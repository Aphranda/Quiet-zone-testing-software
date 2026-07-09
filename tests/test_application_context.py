import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quiet_zone_tester.application import AppContext, TaskRunner, create_app_context
from quiet_zone_tester.services import InstrumentService
from quiet_zone_tester.ui.async_task import TaskRunner as LegacyTaskRunner


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class ApplicationContextTest(unittest.TestCase):
    def test_application_exports_task_runner_and_legacy_import_matches(self) -> None:
        self.assertIs(LegacyTaskRunner, TaskRunner)

    def test_create_app_context_builds_instrument_service(self) -> None:
        context = create_app_context()

        self.assertIsInstance(context.instrument_service, InstrumentService)

    def test_app_context_creates_main_window_with_injected_dependencies(self) -> None:
        _app()
        service = InstrumentService()
        context = AppContext(instrument_service=service)

        window = context.create_main_window()

        self.assertIs(window._service, service)
        self.assertIsInstance(window._tasks, TaskRunner)


if __name__ == "__main__":
    unittest.main()
