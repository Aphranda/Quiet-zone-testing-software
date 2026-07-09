from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QPlainTextEdit, QVBoxLayout

from quiet_zone_tester.presentation.modules.logs.log_record_model import LogRecordModel


class StatusLogPanel(QGroupBox):
    def __init__(self, parent=None) -> None:
        super().__init__("运行日志", parent)

        self._log_model = LogRecordModel(max_records=1000, parent=self)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(1000)

        layout = QVBoxLayout(self)
        layout.addWidget(self._log_view)

    def append_info(self, message: str) -> None:
        self._append("INFO", message)

    def append_error(self, message: str) -> None:
        self._append("ERROR", message)

    @property
    def log_model(self) -> LogRecordModel:
        return self._log_model

    def _append(self, level: str, message: str) -> None:
        record = self._log_model.append(level=level, message=message, source="ui")
        self._log_view.appendPlainText(self._log_model.format_record(record))
