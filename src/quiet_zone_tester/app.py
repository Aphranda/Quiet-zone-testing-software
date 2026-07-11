from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from quiet_zone_tester.application.app_context import create_app_context
from quiet_zone_tester.logging_config import setup_logging
from quiet_zone_tester.resources import resource_path
from quiet_zone_tester.ui.logo_assets import logo_icon


def run_app(argv: list[str] | None = None) -> int:
    setup_logging()

    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("微波暗室静区测试系统")
    app.setOrganizationName("RF Test Lab")
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    app.setWindowIcon(logo_icon())
    app.setStyleSheet(_application_style())

    app_context = create_app_context()
    window = app_context.create_main_window()
    window.resize(1280, 820)
    window.show()
    return app.exec()


def _application_style() -> str:
    replacements = {
        "__COMBOBOX_ARROW_ICON__": resource_path("style/chevron-down.svg").as_posix(),
        "__SPINBOX_UP_ICON__": resource_path("style/chevron-up-small.svg").as_posix(),
        "__SPINBOX_DOWN_ICON__": resource_path("style/chevron-down-small.svg").as_posix(),
    }
    style = resource_path("style/style.css").read_text(encoding="utf-8")
    for placeholder, path in replacements.items():
        style = style.replace(placeholder, path)
    return style
