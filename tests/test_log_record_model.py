import os
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from quiet_zone_tester.presentation.modules.logs import LogRecord, LogRecordModel
from quiet_zone_tester.ui.widgets.status_log_panel import StatusLogPanel


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class LogRecordModelTest(unittest.TestCase):
    def test_append_exposes_structured_table_data(self) -> None:
        model = LogRecordModel()
        timestamp = datetime(2026, 7, 9, 12, 34, 56)

        record = model.append(level="info", source="unit", message="ready", timestamp=timestamp)

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.columnCount(), 4)
        self.assertEqual(model.data(model.index(0, 0), Qt.DisplayRole), "12:34:56")
        self.assertEqual(model.data(model.index(0, 1), Qt.DisplayRole), "INFO")
        self.assertEqual(model.data(model.index(0, 2), Qt.DisplayRole), "unit")
        self.assertEqual(model.data(model.index(0, 3), Qt.DisplayRole), "ready")
        self.assertEqual(model.data(model.index(0, 0), LogRecordModel.RECORD_ROLE), record)

    def test_model_trims_old_records_to_limit(self) -> None:
        model = LogRecordModel(max_records=2)

        model.append_record(LogRecord(datetime(2026, 7, 9, 12, 0, 0), "INFO", "test", "first"))
        model.append_record(LogRecord(datetime(2026, 7, 9, 12, 0, 1), "INFO", "test", "second"))
        model.append_record(LogRecord(datetime(2026, 7, 9, 12, 0, 2), "ERROR", "test", "third"))

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual([record.message for record in model.records], ["second", "third"])

    def test_status_log_panel_keeps_text_behavior_and_updates_model(self) -> None:
        _app()
        panel = StatusLogPanel()

        panel.append_info("started")
        panel.append_error("failed")

        self.assertEqual(panel.log_model.rowCount(), 2)
        self.assertEqual(panel.log_model.records[0].level, "INFO")
        self.assertEqual(panel.log_model.records[1].level, "ERROR")

        text_view = panel.findChild(QPlainTextEdit)
        self.assertIsNotNone(text_view)
        text = text_view.toPlainText()
        self.assertIn("INFO", text)
        self.assertIn("started", text)
        self.assertIn("ERROR", text)
        self.assertIn("failed", text)


if __name__ == "__main__":
    unittest.main()
