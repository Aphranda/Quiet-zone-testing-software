from __future__ import annotations

from dataclasses import dataclass


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
        from quiet_zone_tester.domains.scan_management.scan_planner import point_count_from_volume

        return point_count_from_volume(self)

    def scan_points(self):
        from quiet_zone_tester.domains.scan_management.scan_planner import plan_points_array

        return plan_points_array(self)
