from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from quiet_zone_tester.drivers import Position

logger = logging.getLogger(__name__)


class MotionPositionerController(Protocol):
    @property
    def is_connected(self) -> bool:
        ...

    @property
    def position(self) -> Position:
        ...

    def move_to(self, x_mm: float, y_mm: float, speed_mm_s: float | None = None) -> Position:
        ...

    def jog_axis(self, axis: int, speed_mm_s: float) -> None:
        ...

    def stop_axis(self, axis: int) -> None:
        ...

    def stop_all(self) -> None:
        ...


class MotionServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class MotionService:
    positioner: MotionPositionerController

    def jog_axis(self, axis: int, speed_mm_s: float) -> None:
        self._ensure_connected()
        try:
            self.positioner.jog_axis(int(axis), float(speed_mm_s))
        except Exception as exc:
            logger.exception("Positioner jog failed.")
            raise MotionServiceError(f"Positioner jog failed: {exc}") from exc

    def query_position(self) -> Position:
        self._ensure_connected()
        try:
            return self.positioner.position
        except Exception as exc:
            logger.exception("Positioner position query failed.")
            raise MotionServiceError(f"Positioner position query failed: {exc}") from exc

    def move_absolute(self, x_mm: float, y_mm: float, speed_mm_s: float) -> Position:
        self._ensure_connected()
        try:
            return self.positioner.move_to(float(x_mm), float(y_mm), float(speed_mm_s))
        except Exception as exc:
            logger.exception("Positioner absolute move failed.")
            raise MotionServiceError(f"Positioner absolute move failed: {exc}") from exc

    def move_relative(self, delta_x_mm: float, delta_y_mm: float, speed_mm_s: float) -> Position:
        current = self.query_position()
        return self.move_absolute(
            current.x_mm + float(delta_x_mm),
            current.y_mm + float(delta_y_mm),
            float(speed_mm_s),
        )

    def stop_axis(self, axis: int) -> None:
        self._ensure_connected()
        try:
            self.positioner.stop_axis(int(axis))
        except Exception as exc:
            logger.exception("Positioner axis stop failed.")
            raise MotionServiceError(f"Positioner axis stop failed: {exc}") from exc

    def stop_all(self) -> None:
        self._ensure_connected()
        try:
            self.positioner.stop_all()
        except Exception as exc:
            logger.exception("Positioner stop-all failed.")
            raise MotionServiceError(f"Positioner stop-all failed: {exc}") from exc

    def cancel_motion_if_supported(self) -> None:
        cancel_motion = getattr(self.positioner, "cancel_motion", None)
        if callable(cancel_motion):
            cancel_motion()

    def _ensure_connected(self) -> None:
        if not self.positioner.is_connected:
            raise MotionServiceError("Positioner controller is not connected.")
