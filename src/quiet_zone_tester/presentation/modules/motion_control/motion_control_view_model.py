from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from quiet_zone_tester.shared.instrument_defaults import MAX_POSITIONER_SPEED_MM_S


class PositionLike(Protocol):
    x_mm: float
    y_mm: float


@dataclass(frozen=True)
class AbsoluteMoveCommand:
    x_mm: float
    y_mm: float
    speed_mm_s: float

    def to_dict(self) -> dict[str, float]:
        return {
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "speed_mm_s": self.speed_mm_s,
        }


@dataclass(frozen=True)
class RelativeMoveCommand:
    delta_x_mm: float
    delta_y_mm: float
    speed_mm_s: float

    def to_dict(self) -> dict[str, float]:
        return {
            "delta_x_mm": self.delta_x_mm,
            "delta_y_mm": self.delta_y_mm,
            "speed_mm_s": self.speed_mm_s,
        }


@dataclass(frozen=True)
class PositionDisplay:
    x_text: str
    y_text: str


@dataclass(frozen=True)
class MotionControlUiState:
    actions_enabled: bool
    stop_enabled: bool


class MotionControlViewModel:
    def absolute_move_command(self, *, x_mm: float, y_mm: float, speed_mm_s: float) -> dict[str, float]:
        return AbsoluteMoveCommand(
            x_mm=float(x_mm),
            y_mm=float(y_mm),
            speed_mm_s=self._positive_speed(speed_mm_s),
        ).to_dict()

    def relative_move_command(self, *, delta_x_mm: float, delta_y_mm: float, speed_mm_s: float) -> dict[str, float]:
        return RelativeMoveCommand(
            delta_x_mm=float(delta_x_mm),
            delta_y_mm=float(delta_y_mm),
            speed_mm_s=self._positive_speed(speed_mm_s),
        ).to_dict()

    @staticmethod
    def position_display(position: PositionLike | None) -> PositionDisplay:
        if position is None:
            return PositionDisplay(x_text="-", y_text="-")
        return PositionDisplay(
            x_text=f"{float(position.x_mm):.3f} mm",
            y_text=f"{float(position.y_mm):.3f} mm",
        )

    @staticmethod
    def ui_state(*, connected: bool, busy: bool) -> MotionControlUiState:
        actions_enabled = bool(connected) and not bool(busy)
        return MotionControlUiState(
            actions_enabled=actions_enabled,
            stop_enabled=bool(connected),
        )

    @staticmethod
    def _positive_speed(speed_mm_s: float) -> float:
        speed = float(speed_mm_s)
        if speed <= 0.0:
            raise ValueError("Motion speed must be greater than 0 mm/s.")
        if speed > MAX_POSITIONER_SPEED_MM_S:
            raise ValueError(f"Motion speed cannot exceed {MAX_POSITIONER_SPEED_MM_S:g} mm/s.")
        return speed
