from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from quiet_zone_tester.application.app_context import create_app_context
from quiet_zone_tester.logging_config import setup_logging
from quiet_zone_tester.resources import resource_path


def run_app(argv: list[str] | None = None) -> int:
    setup_logging()

    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("微波暗室静区测试系统")
    app.setOrganizationName("RF Test Lab")
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    app.setWindowIcon(QIcon(str(resource_path("gtslogo_icon.png"))))
    app.setStyleSheet(_application_style())

    app_context = create_app_context()
    window = app_context.create_main_window()
    window.resize(1280, 820)
    window.show()
    return app.exec()


def _application_style() -> str:
    return resource_path("style/style.css").read_text(encoding="utf-8")
