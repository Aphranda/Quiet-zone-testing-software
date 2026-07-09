import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from quiet_zone_tester.models import ScanVolume
from quiet_zone_tester.presentation.modules.scan_runtime import ScanPointModel
from quiet_zone_tester.ui.widgets.scan_animation_panel import ScanAnimationPanel


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class ScanPointModelTest(unittest.TestCase):
    def test_set_volume_exposes_scan_points_and_status(self) -> None:
        model = ScanPointModel()
        model.set_volume(ScanVolume(0.0, 10.0, 0.0, 0.0, 5.0, 1.0))

        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(model.columnCount(), 4)
        self.assertEqual(model.data(model.index(0, 0), Qt.DisplayRole), 1)
        self.assertEqual(model.data(model.index(1, 1), Qt.DisplayRole), "5.000")
        self.assertEqual(model.data(model.index(2, 2), Qt.DisplayRole), "0.000")
        self.assertEqual(model.data(model.index(0, 3), Qt.DisplayRole), "当前")

    def test_completed_count_updates_status_roles(self) -> None:
        model = ScanPointModel()
        model.set_volume(ScanVolume(0.0, 10.0, 0.0, 0.0, 5.0, 1.0))

        model.set_completed_count(2)

        self.assertEqual(model.completed_count, 2)
        self.assertEqual(model.data(model.index(0, 3), Qt.DisplayRole), "已完成")
        self.assertEqual(model.data(model.index(1, 3), ScanPointModel.STATUS_ROLE), "已完成")
        self.assertEqual(model.data(model.index(2, 3), Qt.DisplayRole), "当前")

    def test_scan_animation_panel_keeps_point_model_in_sync(self) -> None:
        _app()
        panel = ScanAnimationPanel()
        volume = ScanVolume(0.0, 10.0, 0.0, 0.0, 5.0, 1.0)

        panel.preview_volume(volume)
        self.assertEqual(panel.point_model.total_count, 3)

        panel.start_scan(volume)
        panel.set_progress(2, 3)

        self.assertEqual(panel.point_model.completed_count, 2)
        self.assertEqual(panel.point_model.data(panel.point_model.index(2, 3), Qt.DisplayRole), "当前")

        panel.stop_scan()
        self.assertEqual(panel.point_model.completed_count, 0)


if __name__ == "__main__":
    unittest.main()
