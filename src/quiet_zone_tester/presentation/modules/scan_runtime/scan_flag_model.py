from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any


@dataclass(frozen=True)
class ScanFlagState:
    main_line: str | None
    position_mark: str


class ScanFlagModel:
    @classmethod
    def from_scan_settings(cls, settings: Mapping[str, Any]) -> ScanFlagState | None:
        try:
            x_start = float(settings["x_start_mm"])
            x_stop = float(settings["x_stop_mm"])
            y_start = float(settings["y_start_mm"])
            y_stop = float(settings["y_stop_mm"])
        except (KeyError, TypeError, ValueError):
            return None

        x_moving = cls._is_moving(x_start, x_stop)
        y_moving = cls._is_moving(y_start, y_stop)
        lower, upper = cls._view_bounds(x_start, x_stop, y_start, y_stop)

        if x_moving:
            if y_moving:
                return ScanFlagState(main_line="X", position_mark="M")
            return ScanFlagState(
                main_line="X",
                position_mark=cls._position_mark_by_quarter(y_start, lower, upper, low_mark="R", high_mark="L"),
            )
        if y_moving:
            return ScanFlagState(
                main_line="Y",
                position_mark=cls._position_mark_by_quarter(x_start, lower, upper, low_mark="U", high_mark="D"),
            )
        return ScanFlagState(main_line=None, position_mark="M")

    @staticmethod
    def _is_moving(start_mm: float, stop_mm: float) -> bool:
        return abs(start_mm - stop_mm) > 1e-9

    @staticmethod
    def _view_bounds(x_start_mm: float, x_stop_mm: float, y_start_mm: float, y_stop_mm: float) -> tuple[float, float]:
        return (
            min(x_start_mm, x_stop_mm, y_start_mm, y_stop_mm),
            max(x_start_mm, x_stop_mm, y_start_mm, y_stop_mm),
        )

    @classmethod
    def _position_mark_by_quarter(
        cls,
        value_mm: float,
        lower_mm: float,
        upper_mm: float,
        *,
        low_mark: str,
        high_mark: str,
    ) -> str:
        span_mm = upper_mm - lower_mm
        if span_mm <= 1e-9:
            return "M"
        low_boundary = lower_mm + span_mm * 0.25
        high_boundary = lower_mm + span_mm * 0.75
        if value_mm <= low_boundary:
            return low_mark
        if value_mm >= high_boundary:
            return high_mark
        return "M"
