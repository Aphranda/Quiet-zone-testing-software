from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from quiet_zone_tester.logging_config import setup_logging
from quiet_zone_tester.resources import resource_path
from quiet_zone_tester.ui.main_window import MainWindow


def run_app(argv: list[str] | None = None) -> int:
    setup_logging()

    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("微波暗室静区测试系统")
    app.setOrganizationName("RF Test Lab")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(resource_path("gtslogo_icon.png"))))
    app.setStyleSheet(_application_style())

    window = MainWindow()
    window.resize(1280, 820)
    window.show()
    return app.exec()


def _application_style() -> str:
    return """
    QMainWindow {
        background: #f5f6f8;
    }
    QGroupBox {
        border: 1px solid #c9d1dc;
        border-radius: 6px;
        margin-top: 10px;
        padding: 10px;
        font-weight: 600;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }
    QPushButton {
        min-height: 28px;
        padding: 4px 10px;
    }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        min-height: 26px;
    }
    QStatusBar {
        background: #eef1f5;
    }
    """
