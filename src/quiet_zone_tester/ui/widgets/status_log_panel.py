from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QGroupBox, QPlainTextEdit, QVBoxLayout


class StatusLogPanel(QGroupBox):
    def __init__(self, parent=None) -> None:
        super().__init__("运行日志", parent)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(1000)

        layout = QVBoxLayout(self)
        layout.addWidget(self._log_view)

    def append_info(self, message: str) -> None:
        self._append("INFO", message)

    def append_error(self, message: str) -> None:
        self._append("ERROR", message)

    def _append(self, level: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_view.appendPlainText(f"{timestamp} | {level:<5} | {message}")
