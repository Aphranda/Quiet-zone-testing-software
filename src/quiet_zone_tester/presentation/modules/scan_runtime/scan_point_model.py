from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from quiet_zone_tester.domains.scan_management import ScanPoint, scan_points_from_volume
from quiet_zone_tester.models import ScanVolume


@dataclass(frozen=True)
class ScanPointDisplay:
    index: int
    x_mm: float
    y_mm: float
    status: str


class ScanPointModel(QAbstractTableModel):
    HEADERS = ("序号", "X/mm", "Y/mm", "状态")
    POINT_ROLE = int(Qt.UserRole) + 1
    STATUS_ROLE = int(Qt.UserRole) + 2

    def __init__(self, points: Sequence[ScanPoint] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._points = list(points or [])
        self._completed_count = 0

    @property
    def points(self) -> tuple[ScanPoint, ...]:
        return tuple(self._points)

    @property
    def completed_count(self) -> int:
        return self._completed_count

    @property
    def total_count(self) -> int:
        return len(self._points)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt override.
        if parent.isValid():
            return 0
        return len(self._points)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt override.
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # noqa: N802 - Qt override.
        if not index.isValid() or not 0 <= index.row() < len(self._points):
            return None

        point = self._points[index.row()]
        status = self.status_for_row(index.row())
        if role == self.POINT_ROLE:
            return point
        if role == self.STATUS_ROLE:
            return status
        if role not in {Qt.DisplayRole, Qt.EditRole}:
            return None

        values = (
            point.index,
            f"{point.x_mm:.3f}",
            f"{point.y_mm:.3f}",
            status,
        )
        if not 0 <= index.column() < len(values):
            return None
        return values[index.column()]

    def headerData(  # noqa: N802 - Qt override.
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        return int(section + 1) if orientation == Qt.Vertical else None

    def set_volume(self, volume: ScanVolume) -> None:
        self.set_points(scan_points_from_volume(volume))

    def set_points(self, points: Sequence[ScanPoint]) -> None:
        self.beginResetModel()
        self._points = list(points)
        self._completed_count = 0
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._points.clear()
        self._completed_count = 0
        self.endResetModel()

    def set_completed_count(self, completed_count: int) -> None:
        next_count = min(max(int(completed_count), 0), len(self._points))
        if next_count == self._completed_count:
            return

        self._completed_count = next_count
        if self._points:
            top_left = self.index(0, 3)
            bottom_right = self.index(len(self._points) - 1, 3)
            self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, self.STATUS_ROLE])

    def display_for_row(self, row: int) -> ScanPointDisplay:
        point = self._points[row]
        return ScanPointDisplay(
            index=point.index,
            x_mm=point.x_mm,
            y_mm=point.y_mm,
            status=self.status_for_row(row),
        )

    def status_for_row(self, row: int) -> str:
        if row < self._completed_count:
            return "已完成"
        if row == self._completed_count and self._completed_count < len(self._points):
            return "当前"
        return "待扫描"
