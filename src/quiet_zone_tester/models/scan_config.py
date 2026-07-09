from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ScanVolume:
    x_start_mm: float
    x_stop_mm: float
    y_start_mm: float
    y_stop_mm: float
    step_x_mm: float
    step_y_mm: float

    def __post_init__(self) -> None:
        steps = {
            "step_x_mm": self.step_x_mm,
            "step_y_mm": self.step_y_mm,
        }
        invalid_steps = [name for name, value in steps.items() if value <= 0.0]
        if invalid_steps:
            raise ValueError(f"Scan steps must be positive: {', '.join(invalid_steps)}")

    @property
    def x_min_mm(self) -> float:
        return min(self.x_start_mm, self.x_stop_mm)

    @property
    def x_max_mm(self) -> float:
        return max(self.x_start_mm, self.x_stop_mm)

    @property
    def y_min_mm(self) -> float:
        return min(self.y_start_mm, self.y_stop_mm)

    @property
    def y_max_mm(self) -> float:
        return max(self.y_start_mm, self.y_stop_mm)

    @property
    def point_count(self) -> int:
        return int(
            self._axis_count(self.x_start_mm, self.x_stop_mm, self.step_x_mm)
            * self._axis_count(self.y_start_mm, self.y_stop_mm, self.step_y_mm)
        )

    def scan_points(self) -> np.ndarray:
        x_axis = self._axis(self.x_start_mm, self.x_stop_mm, self.step_x_mm)
        y_axis = self._axis(self.y_start_mm, self.y_stop_mm, self.step_y_mm)

        rows: list[np.ndarray] = []
        for y_index, y_value in enumerate(y_axis):
            x_scan = x_axis if y_index % 2 == 0 else x_axis[::-1]
            rows.append(
                np.column_stack(
                    (
                        x_scan,
                        np.full(x_scan.shape, y_value, dtype=float),
                    )
                )
            )

        if not rows:
            return np.empty((0, 2), dtype=float)
        return np.vstack(rows)

    @staticmethod
    def _axis(start_mm: float, stop_mm: float, step_mm: float) -> np.ndarray:
        span = stop_mm - start_mm
        if np.isclose(span, 0.0):
            return np.array([start_mm], dtype=float)

        direction = 1.0 if span > 0.0 else -1.0
        distances = np.arange(0.0, abs(span) + step_mm * 0.5, step_mm, dtype=float)
        distances = distances[distances <= abs(span)]
        axis = start_mm + direction * distances
        if axis.size == 0 or not np.isclose(axis[-1], stop_mm):
            axis = np.append(axis, stop_mm)
        return axis

    @staticmethod
    def _axis_count(start_mm: float, stop_mm: float, step_mm: float) -> int:
        span = abs(stop_mm - start_mm)
        if np.isclose(span, 0.0):
            return 1
        return int(np.floor(span / step_mm) + 1 + (0 if np.isclose(span % step_mm, 0.0) else 1))
