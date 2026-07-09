from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicalOrigin:
    x_mm: float
    y_mm: float
    logical_x_mm: float
    logical_y_mm: float


@dataclass(frozen=True)
class PhysicalTarget:
    x_mm: float
    y_mm: float


class ScanRuntimeGeometry:
    @staticmethod
    def physical_target(origin: PhysicalOrigin, target_x_mm: float, target_y_mm: float) -> PhysicalTarget:
        return PhysicalTarget(
            x_mm=origin.x_mm + float(target_x_mm) - origin.logical_x_mm,
            y_mm=origin.y_mm + float(target_y_mm) - origin.logical_y_mm,
        )

    @staticmethod
    def axis_moves(
        logical_x_mm: float | None,
        logical_y_mm: float | None,
        target_x_mm: float,
        target_y_mm: float,
    ) -> list[tuple[str, float]]:
        if logical_x_mm is None or logical_y_mm is None:
            return [("Y", float(target_y_mm)), ("X", float(target_x_mm))]

        moves: list[tuple[str, float]] = []
        if not ScanRuntimeGeometry.positions_match(logical_y_mm, target_y_mm):
            moves.append(("Y", float(target_y_mm)))
        if not ScanRuntimeGeometry.positions_match(logical_x_mm, target_x_mm):
            moves.append(("X", float(target_x_mm)))
        return moves

    @staticmethod
    def next_continuous_motion(
        point_list: list[tuple[float, float]],
        current_index: int,
        current_x_mm: float,
        current_y_mm: float,
    ) -> tuple[str, int] | None:
        if current_index + 1 >= len(point_list):
            return None

        next_x_mm, next_y_mm = point_list[current_index + 1]
        moves = ScanRuntimeGeometry.axis_moves(current_x_mm, current_y_mm, next_x_mm, next_y_mm)
        if not moves:
            return None

        axis_name, target_mm = moves[0]
        current_axis_mm = current_y_mm if axis_name.strip().upper() == "Y" else current_x_mm
        delta_mm = target_mm - current_axis_mm
        if abs(delta_mm) <= 1e-9:
            return None
        return ScanRuntimeGeometry.normalize_axis_name(axis_name), 1 if delta_mm > 0 else -1

    @staticmethod
    def should_stop_before_continuous_sample(
        active_axis_name: str | None,
        active_direction: int,
        next_motion: tuple[str, int] | None,
    ) -> bool:
        if active_axis_name is None:
            return False
        if next_motion is None:
            return True
        next_axis_name, next_direction = next_motion
        return (
            ScanRuntimeGeometry.normalize_axis_name(active_axis_name) != next_axis_name
            or active_direction != next_direction
        )

    @staticmethod
    def normalize_axis_name(axis_name: str) -> str:
        return "Y" if axis_name.strip().upper() == "Y" else "X"

    @staticmethod
    def positions_match(left_mm: float, right_mm: float) -> bool:
        return abs(float(left_mm) - float(right_mm)) <= 1e-9
