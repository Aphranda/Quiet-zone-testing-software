from __future__ import annotations

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QGroupBox, QPlainTextEdit, QVBoxLayout

from quiet_zone_tester.presentation.modules.logs.log_record_model import LogRecord, LogRecordModel


class StatusLogPanel(QGroupBox):
    def __init__(self, parent=None) -> None:
        super().__init__("运行日志", parent)

        self._log_model = LogRecordModel(max_records=1000, parent=self)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(1000)
        self._log_model.rowsInserted.connect(self._append_inserted_rows)

        layout = QVBoxLayout(self)
        layout.addWidget(self._log_view)

    def append(self, *, level: str, message: str, source: str = "ui") -> LogRecord:
        return self._log_model.append(level=level, message=message, source=source)

    def append_info(self, message: str) -> None:
        self.append(level="INFO", message=message)

    def append_warning(self, message: str) -> None:
        self.append(level="WARNING", message=message)

    def append_error(self, message: str) -> None:
        self.append(level="ERROR", message=message)

    @property
    def log_model(self) -> LogRecordModel:
        return self._log_model

    def _append_inserted_rows(self, parent: QModelIndex, first: int, last: int) -> None:
        del parent
        records = self._log_model.records
        for row in range(first, last + 1):
            if 0 <= row < len(records):
                self._log_view.appendPlainText(self._log_model.format_record(records[row]))
