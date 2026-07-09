from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


class ScanVolumeLike(Protocol):
    x_start_mm: float
    x_stop_mm: float
    y_start_mm: float
    y_stop_mm: float
    step_x_mm: float
    step_y_mm: float


@dataclass(frozen=True)
class PlannedScanPoint:
    index: int
    x_mm: float
    y_mm: float

    @property
    def position_mm(self) -> tuple[float, float]:
        return self.x_mm, self.y_mm


@dataclass(frozen=True)
class ScanPlan:
    points: tuple[PlannedScanPoint, ...]

    @property
    def point_count(self) -> int:
        return len(self.points)

    def as_array(self) -> np.ndarray:
        if not self.points:
            return np.empty((0, 2), dtype=float)
        return np.array([(point.x_mm, point.y_mm) for point in self.points], dtype=float)


class ScanPlanner:
    def plan(self, volume: ScanVolumeLike) -> ScanPlan:
        x_axis = self.axis_points(volume.x_start_mm, volume.x_stop_mm, volume.step_x_mm)
        y_axis = self.axis_points(volume.y_start_mm, volume.y_stop_mm, volume.step_y_mm)

        points: list[PlannedScanPoint] = []
        for y_index, y_value in enumerate(y_axis):
            x_scan = x_axis if y_index % 2 == 0 else x_axis[::-1]
            for x_value in x_scan:
                points.append(
                    PlannedScanPoint(
                        index=len(points) + 1,
                        x_mm=float(x_value),
                        y_mm=float(y_value),
                    )
                )
        return ScanPlan(points=tuple(points))

    def plan_array(self, volume: ScanVolumeLike) -> np.ndarray:
        return self.plan(volume).as_array()

    def point_count(self, volume: ScanVolumeLike) -> int:
        return int(
            self.axis_count(volume.x_start_mm, volume.x_stop_mm, volume.step_x_mm)
            * self.axis_count(volume.y_start_mm, volume.y_stop_mm, volume.step_y_mm)
        )

    @staticmethod
    def axis_points(start_mm: float, stop_mm: float, step_mm: float) -> np.ndarray:
        if step_mm <= 0.0:
            raise ValueError("Scan axis step must be positive.")

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
    def axis_count(start_mm: float, stop_mm: float, step_mm: float) -> int:
        if step_mm <= 0.0:
            raise ValueError("Scan axis step must be positive.")

        span = abs(stop_mm - start_mm)
        if np.isclose(span, 0.0):
            return 1
        full_steps = int(np.floor(span / step_mm))
        includes_stop = np.isclose(span % step_mm, 0.0)
        return full_steps + 1 + (0 if includes_stop else 1)


_DEFAULT_PLANNER = ScanPlanner()


def plan_scan(volume: ScanVolumeLike) -> ScanPlan:
    return _DEFAULT_PLANNER.plan(volume)


def plan_scan_points(volume: ScanVolumeLike) -> tuple[PlannedScanPoint, ...]:
    return plan_scan(volume).points


def plan_points_array(volume: ScanVolumeLike) -> np.ndarray:
    return _DEFAULT_PLANNER.plan_array(volume)


def point_count_from_volume(volume: ScanVolumeLike) -> int:
    return _DEFAULT_PLANNER.point_count(volume)
