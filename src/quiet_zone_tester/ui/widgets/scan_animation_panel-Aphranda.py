from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from quiet_zone_tester.models import ScanVolume
from quiet_zone_tester.presentation.modules.scan_runtime import ScanPointModel


DEFAULT_VOLUME = ScanVolume(0.0, 400.0, 0.0, 400.0, 2.5, 2.5)
PROBE_HOLDER_HALF_SIZE_PX = 24.0


class ScanAnimationPanel(QGroupBox):
    finished = Signal()
    progress_changed = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__("二维扫描动画", parent)
        self._point_model = ScanPointModel(parent=self)
        self._canvas = _ScanCanvas()
        self._canvas.set_volume(DEFAULT_VOLUME, scan_active=False)
        self._point_model.set_volume(DEFAULT_VOLUME)
        self._view_rotation = QComboBox()
        self._view_rotation.addItem("默认视角", 0)
        self._view_rotation.addItem("旋转90°", 90)
        self._view_rotation.addItem("旋转180°", 180)
        self._view_rotation.addItem("旋转270°", 270)
        self._view_rotation.currentIndexChanged.connect(self._on_view_rotation_changed)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("视角"))
        toolbar.addWidget(self._view_rotation)
        toolbar.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self._canvas)

        self._timer = QTimer(self)
        self._timer.setInterval(35)
        self._timer.timeout.connect(self._advance)

    def preview_volume(self, volume: ScanVolume) -> None:
        if self._timer.isActive():
            return
        self._canvas.set_volume(volume, scan_active=False)
        self._point_model.set_volume(volume)
        self.progress_changed.emit(0, self._canvas.point_count())

    def set_probe_position_from_settings(self, settings: dict) -> None:
        self._canvas.set_probe_offset(
            x_offset_mm=float(settings.get("probe_x_offset_mm", 0.0)),
            y_offset_mm=float(settings.get("probe_y_offset_mm", 0.0)),
            label=str(settings.get("probe_offset_preset", "")).strip(),
        )

    def start_scan(self, volume: ScanVolume) -> None:
        self._canvas.set_volume(volume, scan_active=True)
        self._point_model.set_volume(volume)
        self.progress_changed.emit(*self._canvas.progress())

    def stop_scan(self) -> None:
        self._timer.stop()
        self._canvas.reset_to_preview()
        self._point_model.set_completed_count(0)
        self.progress_changed.emit(0, self._canvas.point_count())

    def set_progress(self, completed_points: int, total_points: int | None = None) -> None:
        self._canvas.set_progress(completed_points, total_points)
        self._point_model.set_completed_count(completed_points)
        total = self._canvas.point_count() if total_points is None else total_points
        self.progress_changed.emit(completed_points, total)

    @property
    def point_model(self) -> ScanPointModel:
        return self._point_model

    def _on_view_rotation_changed(self) -> None:
        self._canvas.set_view_rotation(int(self._view_rotation.currentData()))

    def _advance(self) -> None:
        has_more_points = self._canvas.advance()
        completed, total = self._canvas.progress()
        self._point_model.set_completed_count(completed)
        self.progress_changed.emit(completed, total)
        if not has_more_points:
            self._timer.stop()
            self.finished.emit()


class _ScanCanvas(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.setMouseTracking(True)
        self._volume: ScanVolume | None = None
        self._points = np.empty((0, 2), dtype=float)
        self._measurements = np.empty((0, 2), dtype=float)
        self._scan_active = False
        self._current_index = -1
        self._display_completed = 0
        self._display_total: int | None = None
        self._selected_index: int | None = None
        self._view_rotation_degrees = 0
        self._probe_x_offset_mm = 0.0
        self._probe_y_offset_mm = 0.0
        self._probe_offset_label = "右上"

    def set_view_rotation(self, degrees: int) -> None:
        normalized_degrees = int(degrees) % 360
        if normalized_degrees not in {0, 90, 180, 270}:
            normalized_degrees = 0
        if self._view_rotation_degrees == normalized_degrees:
            return

        self._view_rotation_degrees = normalized_degrees
        self.update()

    def set_probe_offset(self, x_offset_mm: float, y_offset_mm: float, label: str = "") -> None:
        self._probe_x_offset_mm = float(x_offset_mm)
        self._probe_y_offset_mm = float(y_offset_mm)
        self._probe_offset_label = str(label or "").strip()
        self.update()

    def set_volume(self, volume: ScanVolume, scan_active: bool) -> None:
        self._volume = volume
        self._points = volume.scan_points()
        self._measurements = self._generate_measurements(self._points)
        self._scan_active = scan_active
        self._current_index = -1
        self._display_completed = 0
        self._display_total = None
        self._selected_index = None
        self.update()

    def reset_to_preview(self) -> None:
        self._scan_active = False
        self._current_index = -1
        self._display_completed = 0
        self._display_total = None
        self._selected_index = None
        self.update()

    def point_count(self) -> int:
        return int(self._points.shape[0])

    def advance(self) -> bool:
        if not self._scan_active or self._points.size == 0:
            return False

        last_index = self._points.shape[0] - 1
        if self._current_index < last_index:
            self._current_index += 1
        self._display_completed = self._current_index + 1
        self._display_total = self._points.shape[0]
        self.update()
        return self._current_index < last_index

    def set_progress(self, completed_points: int, total_points: int | None = None) -> None:
        if not self._scan_active or self._points.size == 0:
            return

        self._display_completed = max(int(completed_points), 0)
        self._display_total = None if total_points is None else max(int(total_points), 0)
        if self._uses_index_progress():
            if self._display_completed <= 0:
                self._current_index = -1
            else:
                self._current_index = int(np.clip(self._display_completed - 1, 0, self._points.shape[0] - 1))
        else:
            self._current_index = int(np.clip(self._continuous_fraction() * (self._points.shape[0] - 1), 0, self._points.shape[0] - 1))
        self.update()

    def progress(self) -> tuple[int, int]:
        total = self._points.shape[0]
        if not self._scan_active or total == 0:
            return 0, total
        if self._display_total is not None:
            return self._display_completed, self._display_total
        if self._current_index < 0:
            return 0, total
        completed = min(max(self._current_index, 0) + 1, total)
        return completed, total

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override.
        if event.button() == Qt.LeftButton and self._scan_active and self._points.size:
            self._select_nearest_point(event.position())

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f8fafc"))

        if self._volume is None:
            return

        self._draw_coordinate_system(painter)
        self._draw_planned_points(painter)
        if self._scan_active:
            self._draw_scan_path(painter)
            self._draw_current_point(painter)
            self._draw_selected_point(painter)
            self._draw_selected_measurement(painter)
        self._draw_probe_holder(painter)
        self._draw_status(painter)

    def _draw_coordinate_system(self, painter: QPainter) -> None:
        self._draw_scan_plane(painter)
        self._draw_base_grid(painter)
        self._draw_axes(painter)
        self._draw_tick_labels(painter)

    def _draw_scan_plane(self, painter: QPainter) -> None:
        rect = self._plot_rect()
        painter.setPen(QPen(QColor("#98a2b3"), 1.4))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(rect)

    def _draw_base_grid(self, painter: QPainter) -> None:
        assert self._volume is not None
        (x_min, x_max), (y_min, y_max) = self._view_bounds()
        x_ticks = self._axis_ticks(x_min, x_max, self._volume.step_x_mm)
        y_ticks = self._axis_ticks(y_min, y_max, self._volume.step_y_mm)

        painter.setPen(QPen(QColor("#d0d5dd"), 1.0, Qt.DashLine))
        for x_value in x_ticks:
            painter.drawLine(
                self._project_point(np.array([x_value, y_min], dtype=float)),
                self._project_point(np.array([x_value, y_max], dtype=float)),
            )

        for y_value in y_ticks:
            painter.drawLine(
                self._project_point(np.array([x_min, y_value], dtype=float)),
                self._project_point(np.array([x_max, y_value], dtype=float)),
            )

    def _draw_axes(self, painter: QPainter) -> None:
        assert self._volume is not None
        (x_min, x_max), (y_min, y_max) = self._view_bounds()
        origin = self._project_point_unclamped(np.array([x_min, y_min], dtype=float))
        x_stop = self._extended_axis_stop(
            origin,
            self._project_point_unclamped(np.array([x_max, y_min], dtype=float)),
            26.0,
        )
        y_stop = self._extended_axis_stop(
            origin,
            self._project_point_unclamped(np.array([x_min, y_max], dtype=float)),
            26.0,
        )

        painter.setFont(QFont("Arial", 11, QFont.Bold))

        painter.setPen(QPen(QColor("#d92d20"), 1.8))
        painter.drawLine(origin, x_stop)
        self._draw_arrow_head(painter, origin, x_stop, QColor("#d92d20"))
        painter.setPen(QColor("#d92d20"))
        painter.drawText(x_stop + self._rotate_offset(-4.0, 18.0), "X")

        painter.setPen(QPen(QColor("#027a48"), 1.8))
        painter.drawLine(origin, y_stop)
        self._draw_arrow_head(painter, origin, y_stop, QColor("#027a48"))
        painter.setPen(QColor("#027a48"))
        painter.drawText(y_stop + self._rotate_offset(-18.0, 4.0), "Y")

        painter.setPen(QColor("#101828"))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(origin + self._rotate_offset(8.0, -8.0), "0,0")

    @staticmethod
    def _extended_axis_stop(start: QPointF, stop: QPointF, extension: float) -> QPointF:
        dx = stop.x() - start.x()
        dy = stop.y() - start.y()
        length = float(np.hypot(dx, dy))
        if length <= 1e-9:
            return stop
        return QPointF(stop.x() + dx / length * extension, stop.y() + dy / length * extension)

    def _draw_tick_labels(self, painter: QPainter) -> None:
        assert self._volume is not None
        painter.setPen(QColor("#475467"))
        painter.setFont(QFont("Microsoft YaHei UI", 8))

        (x_min, x_max), (y_min, y_max) = self._view_bounds()
        x_ticks = self._axis_ticks(x_min, x_max, self._volume.step_x_mm)
        for x_value in x_ticks:
            point = self._project_point(np.array([x_value, y_min], dtype=float))
            label = self._axis_label(x_value)
            painter.drawText(point + self._rotate_offset(8.0, 4.0), label)

        y_ticks = self._axis_ticks(y_min, y_max, self._volume.step_y_mm)
        for y_value in y_ticks:
            point = self._project_point(np.array([x_min, y_value], dtype=float))
            label = self._axis_label(y_value)
            painter.drawText(point + self._rotate_offset(-10.0, -10.0), label)

    def _draw_planned_points(self, painter: QPainter) -> None:
        if self._points.size == 0:
            return

        self._draw_planned_path(painter)
        planned = self._downsample(self._points, 2500)
        projected = self._project_points(planned)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(152, 162, 179, 95))
        for point in projected:
            painter.drawEllipse(self._to_pointf(point), 2.0, 2.0)

    def _draw_planned_path(self, painter: QPainter) -> None:
        if self._points.shape[0] <= 1:
            return

        path_points = self._downsample(self._points, 1800)
        projected = self._project_points(path_points)
        painter.setPen(QPen(QColor(71, 84, 103, 140), 1.4, Qt.DashLine))
        for start, stop in zip(projected[:-1], projected[1:]):
            painter.drawLine(self._to_pointf(start), self._to_pointf(stop))

    def _draw_scan_path(self, painter: QPainter) -> None:
        visited = self._visited_path()
        if visited.shape[0] <= 1:
            return

        path_points = self._downsample(visited, 1800)
        projected = self._project_points(path_points)

        painter.setPen(QPen(QColor("#f79009"), 2.2))
        for start, stop in zip(projected[:-1], projected[1:]):
            painter.drawLine(self._to_pointf(start), self._to_pointf(stop))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2f80ed"))
        point_marks = self._downsample(visited, 1200)
        for point in self._project_points(point_marks):
            painter.drawEllipse(self._to_pointf(point), 2.6, 2.6)

    def _draw_current_point(self, painter: QPainter) -> None:
        if self._display_completed <= 0:
            return

        current = self._current_point()
        painter.setPen(QPen(QColor("#7a271a"), 2.0))
        painter.setBrush(QColor("#f04438"))
        painter.drawEllipse(self._project_point(current), 7.5, 7.5)

    def _draw_selected_point(self, painter: QPainter) -> None:
        if self._selected_index is None:
            return

        point = self._points[self._selected_index]
        painter.setPen(QPen(QColor("#53389e"), 2.4))
        painter.setBrush(QColor("#7f56d9"))
        painter.drawEllipse(self._project_point(point), 9.5, 9.5)

    def _draw_probe_holder(self, painter: QPainter) -> None:
        if self._volume is None:
            return

        center = self._probe_holder_center_point()
        center_screen = self._project_point(center)
        corner_points = self._probe_holder_corner_points(center_screen)
        order = ("右上", "左上", "左下", "右下", "右上")

        painter.setPen(QPen(QColor("#344054"), 1.8))
        painter.setBrush(Qt.NoBrush)
        for start_name, stop_name in zip(order[:-1], order[1:]):
            painter.drawLine(corner_points[start_name], corner_points[stop_name])

        painter.setPen(QPen(QColor("#101828"), 1.4))
        painter.drawLine(center_screen + QPointF(-5.0, 0.0), center_screen + QPointF(5.0, 0.0))
        painter.drawLine(center_screen + QPointF(0.0, -5.0), center_screen + QPointF(0.0, 5.0))

        selected_corner = self._selected_probe_corner_name()
        painter.setFont(QFont("Microsoft YaHei UI", 8))
        for name, screen_point in corner_points.items():
            selected = name == selected_corner
            painter.setPen(QPen(QColor("#7a271a" if selected else "#475467"), 2.0 if selected else 1.2))
            painter.setBrush(QColor("#f04438" if selected else "#e4e7ec"))
            radius = 7.0 if selected else 4.8
            painter.drawEllipse(screen_point, radius, radius)
            painter.setPen(QColor("#101828" if selected else "#667085"))
            painter.drawText(screen_point + self._probe_label_offset(name), name)

        if selected_corner is None:
            custom_screen = center_screen + self._probe_custom_screen_offset()
            painter.setPen(QPen(QColor("#7a271a"), 2.0))
            painter.setBrush(QColor("#f04438"))
            painter.drawEllipse(custom_screen, 7.0, 7.0)
            painter.setPen(QColor("#101828"))
            painter.drawText(custom_screen + QPointF(8.0, -8.0), self._probe_offset_label or "自定义")

    def _draw_status(self, painter: QPainter) -> None:
        assert self._volume is not None
        painter.setPen(QColor("#101828"))
        painter.setFont(QFont("Microsoft YaHei UI", 10))

        if self._scan_active and self._display_completed > 0:
            current = self._current_point()
            completed, total = self.progress()
            text = (
                f"扫描进度 {completed}/{total}    "
                f"X={current[0]:.1f} mm  Y={current[1]:.1f} mm"
            )
        else:
            text = (
                "扫描区间："
                f"X[{self._volume.x_min_mm:.1f}, {self._volume.x_max_mm:.1f}]  "
                f"Y[{self._volume.y_min_mm:.1f}, {self._volume.y_max_mm:.1f}] mm"
            )
        painter.drawText(14, 24, text)

        painter.setPen(QColor("#667085"))
        painter.setFont(QFont("Microsoft YaHei UI", 8))
        painter.drawText(
            14,
            44,
            f"坐标面固定 0..{self._view_limit():g} mm，X 正方向向下，Y 正方向向左；当前探头 {self._probe_display_name()}",
        )

    def _draw_selected_measurement(self, painter: QPainter) -> None:
        if self._selected_index is None:
            return

        point = self._points[self._selected_index]
        amplitude_db, phase_deg = self._measurements[self._selected_index]
        panel = QRectF(self.width() - 238.0, 14.0, 224.0, 116.0)

        painter.fillRect(panel, QColor(255, 255, 255, 232))
        painter.setPen(QPen(QColor("#d0d5dd"), 1.0))
        painter.drawRoundedRect(panel, 6.0, 6.0)

        painter.setPen(QColor("#101828"))
        painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
        painter.drawText(QRectF(panel.x() + 12.0, panel.y() + 10.0, panel.width() - 24.0, 18.0), "选中扫描点")

        painter.setFont(QFont("Microsoft YaHei UI", 9))
        lines = (
            f"序号：{self._selected_index + 1}/{self._points.shape[0]}",
            f"坐标：X={point[0]:.1f}, Y={point[1]:.1f} mm",
            f"幅度：{amplitude_db:.2f} dB",
            f"相位：{phase_deg:.2f} deg",
        )
        for row, text in enumerate(lines):
            painter.drawText(panel.x() + 12.0, panel.y() + 42.0 + row * 17.0, text)

    def _draw_arrow_head(
        self,
        painter: QPainter,
        start: QPointF,
        stop: QPointF,
        color: QColor,
    ) -> None:
        dx = stop.x() - start.x()
        dy = stop.y() - start.y()
        length = float(np.hypot(dx, dy))
        if length < 10.0:
            return

        ux = dx / length
        uy = dy / length
        size = 9.0
        left = QPointF(
            stop.x() - size * ux - size * 0.48 * (-uy),
            stop.y() - size * uy - size * 0.48 * ux,
        )
        right = QPointF(
            stop.x() - size * ux + size * 0.48 * (-uy),
            stop.y() - size * uy + size * 0.48 * ux,
        )

        painter.setPen(QPen(color, 2.0))
        painter.drawLine(stop, left)
        painter.drawLine(stop, right)

    def _select_nearest_point(self, position: QPointF) -> None:
        projected = self._project_points(self._points)
        target = np.array([position.x(), position.y()], dtype=float)
        distances = np.sum((projected - target) ** 2, axis=1)
        nearest_index = int(np.argmin(distances))
        if distances[nearest_index] <= 12.0**2:
            self._selected_index = nearest_index
        else:
            self._selected_index = None
        self.update()

    def _visited_path(self) -> np.ndarray:
        if self._points.size == 0 or self._display_completed <= 0:
            return np.empty((0, 2), dtype=float)

        if self._uses_index_progress():
            end_index = int(np.clip(self._current_index, 0, self._points.shape[0] - 1))
            return self._points[: end_index + 1]

        return self._path_until_fraction(self._continuous_fraction())

    def _current_point(self) -> np.ndarray:
        if self._points.size == 0:
            return np.zeros(2, dtype=float)
        if not self._uses_index_progress():
            return self._point_at_fraction(self._continuous_fraction())
        index = min(max(self._current_index, 0), self._points.shape[0] - 1)
        return self._points[index]

    def _point_at_fraction(self, fraction: float) -> np.ndarray:
        path = self._path_until_fraction(fraction)
        if path.size == 0:
            return self._points[0]
        return path[-1]

    def _path_until_fraction(self, fraction: float) -> np.ndarray:
        if self._points.shape[0] <= 1:
            return self._points.copy()

        fraction = float(np.clip(fraction, 0.0, 1.0))
        if fraction <= 0.0:
            return self._points[:1].copy()

        segments = self._points[1:] - self._points[:-1]
        lengths = np.linalg.norm(segments, axis=1)
        total_length = float(np.sum(lengths))
        if total_length <= 1e-9:
            return self._points[:1].copy()

        target_length = total_length * fraction
        cumulative = np.cumsum(lengths)
        segment_index = int(np.searchsorted(cumulative, target_length, side="right"))
        segment_index = min(segment_index, lengths.shape[0] - 1)
        previous_length = 0.0 if segment_index == 0 else float(cumulative[segment_index - 1])
        segment_length = float(lengths[segment_index])
        if segment_length <= 1e-9:
            interpolated = self._points[segment_index + 1]
        else:
            ratio = (target_length - previous_length) / segment_length
            interpolated = self._points[segment_index] + segments[segment_index] * ratio

        visited = self._points[: segment_index + 1]
        return np.vstack((visited, interpolated))

    def _continuous_fraction(self) -> float:
        total = max(int(self._display_total or 0), 1)
        return float(np.clip(self._display_completed / total, 0.0, 1.0))

    def _uses_index_progress(self) -> bool:
        return self._display_total is None or self._display_total == self._points.shape[0]

    def _project_point(self, point: np.ndarray) -> QPointF:
        projected = self._project_points(point.reshape(1, 2))
        return self._to_pointf(projected[0])

    def _project_point_unclamped(self, point: np.ndarray) -> QPointF:
        projected = self._project_points(point.reshape(1, 2), clamp=False)
        return self._to_pointf(projected[0])

    def _project_points(self, points: np.ndarray, clamp: bool = True) -> np.ndarray:
        assert self._volume is not None
        if points.size == 0:
            return np.empty((0, 2), dtype=float)

        rect = self._plot_rect()
        bounds = self._view_bounds()
        x_min, x_max = bounds[0]
        y_min, y_max = bounds[1]
        x_span = max(x_max - x_min, 1e-9)
        y_span = max(y_max - y_min, 1e-9)

        x_ratio = (points[:, 0] - x_min) / x_span
        y_ratio = (points[:, 1] - y_min) / y_span
        if clamp:
            x_ratio = np.clip(x_ratio, 0.0, 1.0)
            y_ratio = np.clip(y_ratio, 0.0, 1.0)
        projected = np.column_stack(
            (
                rect.right() - y_ratio * rect.width(),
                rect.top() + x_ratio * rect.height(),
            )
        )
        return self._rotate_points(projected)

    def _rotate_point(self, point: QPointF) -> QPointF:
        rotated = self._rotate_points(np.array([[point.x(), point.y()]], dtype=float))[0]
        return QPointF(float(rotated[0]), float(rotated[1]))

    def _rotate_offset(self, dx: float, dy: float) -> QPointF:
        angle = self._view_rotation_degrees
        if angle == 90:
            return QPointF(-dy, dx)
        if angle == 180:
            return QPointF(-dx, -dy)
        if angle == 270:
            return QPointF(dy, -dx)
        return QPointF(dx, dy)

    def _rotate_points(self, points: np.ndarray) -> np.ndarray:
        angle = self._view_rotation_degrees
        if angle == 0 or points.size == 0:
            return points

        rect = self._plot_rect()
        center_x = rect.center().x()
        center_y = rect.center().y()
        dx = points[:, 0] - center_x
        dy = points[:, 1] - center_y
        if angle == 90:
            rotated = np.column_stack((center_x - dy, center_y + dx))
        elif angle == 180:
            rotated = np.column_stack((center_x - dx, center_y - dy))
        elif angle == 270:
            rotated = np.column_stack((center_x + dy, center_y - dx))
        else:
            rotated = points
        return rotated

    def _plot_rect(self) -> QRectF:
        left_margin = 68.0
        right_margin = 66.0
        top_margin = 96.0
        bottom_margin = 52.0
        available_width = max(self.width() - left_margin - right_margin, 40.0)
        available_height = max(self.height() - top_margin - bottom_margin, 40.0)
        size = max(min(available_width, available_height), 40.0)
        x = left_margin + max(available_width - size, 0.0) * 0.5
        y = top_margin + max(available_height - size, 0.0) * 0.5
        return QRectF(x, y, size, size)

    def _view_bounds(self) -> tuple[tuple[float, float], tuple[float, float]]:
        maximum = self._view_limit()
        return (0.0, maximum), (0.0, maximum)

    def _view_limit(self) -> float:
        assert self._volume is not None
        return max(self._volume.x_max_mm, self._volume.y_max_mm, 1.0)

    def _generate_measurements(self, points: np.ndarray) -> np.ndarray:
        if points.size == 0:
            return np.empty((0, 2), dtype=float)

        assert self._volume is not None
        x = self._ratio(points[:, 0], self._volume.x_min_mm, self._volume.x_max_mm)
        y = self._ratio(points[:, 1], self._volume.y_min_mm, self._volume.y_max_mm)

        amplitude_db = (
            -18.0
            + 0.85 * np.sin(2.0 * np.pi * x)
            + 0.45 * np.cos(2.0 * np.pi * y)
            + 0.25 * np.sin(2.0 * np.pi * (x + y))
        )
        phase_deg = 75.0 * x - 58.0 * y + 12.0 * np.sin(2.0 * np.pi * x)
        return np.column_stack((amplitude_db, phase_deg))

    @staticmethod
    def _ratio(values: np.ndarray, start: float, stop: float) -> np.ndarray:
        span = stop - start
        if np.isclose(span, 0.0):
            return np.zeros_like(values, dtype=float)
        return (values - start) / span

    @staticmethod
    def _axis_ticks(start: float, stop: float, step: float) -> np.ndarray:
        minimum = min(start, stop)
        maximum = max(start, stop)
        span = maximum - minimum
        if np.isclose(span, 0.0):
            return np.array([start], dtype=float)

        raw_count = int(np.floor(span / step)) + 1
        count = max(2, min(raw_count, 6))
        ticks = np.linspace(minimum, maximum, count)
        return np.unique(np.round(ticks, decimals=3))

    @staticmethod
    def _downsample(points: np.ndarray, limit: int) -> np.ndarray:
        if points.shape[0] <= limit:
            return points

        indices = np.linspace(0, points.shape[0] - 1, limit, dtype=int)
        return points[indices]

    @staticmethod
    def _to_pointf(point: np.ndarray) -> QPointF:
        return QPointF(float(point[0]), float(point[1]))

    @staticmethod
    def _axis_label(value: float) -> str:
        if abs(value) < 1e-6:
            value = 0.0
        return f"{value:g}"

    def _probe_holder_center_point(self) -> np.ndarray:
        if self._scan_active and self._display_completed > 0 and self._points.size:
            return self._current_point()
        if self._points.size:
            return self._points[0]
        assert self._volume is not None
        return np.array([self._volume.x_min_mm, self._volume.y_min_mm], dtype=float)

    def _probe_holder_corner_points(self, center: QPointF) -> dict[str, QPointF]:
        half = PROBE_HOLDER_HALF_SIZE_PX
        return {
            "右上": center + self._probe_screen_offset(-half, -half),
            "左上": center + self._probe_screen_offset(-half, half),
            "右下": center + self._probe_screen_offset(half, -half),
            "左下": center + self._probe_screen_offset(half, half),
        }

    def _selected_probe_corner_name(self) -> str | None:
        if self._probe_offset_label in {"右上", "左上", "右下", "左下"}:
            return self._probe_offset_label
        return None

    def _probe_custom_screen_offset(self) -> QPointF:
        x_offset = self._probe_x_offset_mm
        y_offset = self._probe_y_offset_mm
        magnitude = max(abs(x_offset), abs(y_offset), 1.0)
        half = PROBE_HOLDER_HALF_SIZE_PX
        return self._probe_screen_offset(x_offset / magnitude * half, y_offset / magnitude * half)

    def _probe_screen_offset(self, logical_x_px: float, logical_y_px: float) -> QPointF:
        return self._rotate_offset(-logical_y_px, logical_x_px)

    @staticmethod
    def _probe_label_offset(name: str) -> QPointF:
        offsets = {
            "右上": QPointF(8.0, -8.0),
            "左上": QPointF(-30.0, -8.0),
            "右下": QPointF(8.0, 18.0),
            "左下": QPointF(-30.0, 18.0),
        }
        return offsets.get(name, QPointF(8.0, -8.0))

    def _probe_display_name(self) -> str:
        selected_corner = self._selected_probe_corner_name()
        if selected_corner is not None:
            return selected_corner
        return self._probe_offset_label or "自定义"
