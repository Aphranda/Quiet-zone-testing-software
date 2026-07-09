from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from collections.abc import Callable
from typing import Protocol

from quiet_zone_tester.domains.instrument_management import (
    InstrumentControllerFactory,
    InstrumentControllerFactoryError,
)
from quiet_zone_tester.domains.scan_management import ScanRuntimeGeometry
from quiet_zone_tester.hardware import Position

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

    def move_axis_to(self, axis_name: str, position_mm: float, speed_mm_s: float) -> Position:
        self._ensure_connected()
        axis = self.axis_for_name(axis_name)
        move_axis_to = getattr(self.positioner, "move_axis_to", None)
        try:
            if callable(move_axis_to):
                return move_axis_to(axis, float(position_mm), float(speed_mm_s))

            current = self.positioner.position
            if ScanRuntimeGeometry.normalize_axis_name(axis_name) == "Y":
                return self.positioner.move_to(current.x_mm, float(position_mm), float(speed_mm_s))
            return self.positioner.move_to(float(position_mm), current.y_mm, float(speed_mm_s))
        except Exception as exc:
            logger.exception("Positioner axis move failed.")
            raise MotionServiceError(f"Positioner axis move failed: {exc}") from exc

    def jog_axis_until(
        self,
        *,
        axis_name: str,
        target_position_mm: float,
        speed_mm_s: float,
        active_axis_name: str | None,
        active_direction: int,
        wait_if_paused: Callable[[], None],
        raise_if_stopped: Callable[[], None],
        is_paused: Callable[[], bool],
    ) -> tuple[str | None, int]:
        self._ensure_connected()
        normalized_axis_name = ScanRuntimeGeometry.normalize_axis_name(axis_name)
        axis = self.axis_for_name(normalized_axis_name)
        speed = max(abs(float(speed_mm_s)), 0.001)
        tolerance_mm = self.position_tolerance_for_axis(axis)

        position = self.positioner.position
        current_position_mm = self.position_for_axis_name(position, normalized_axis_name)
        if (
            active_axis_name is not None
            and ScanRuntimeGeometry.normalize_axis_name(active_axis_name) == normalized_axis_name
            and active_direction != 0
            and self.target_crossed(current_position_mm, target_position_mm, active_direction, tolerance_mm)
        ):
            return active_axis_name, active_direction

        distance_mm = float(target_position_mm) - current_position_mm
        if abs(distance_mm) <= tolerance_mm:
            return active_axis_name, active_direction

        direction = 1 if distance_mm > 0 else -1
        if active_axis_name is not None and (
            ScanRuntimeGeometry.normalize_axis_name(active_axis_name) != normalized_axis_name
            or active_direction != direction
        ):
            self.stop_axis_by_name_quietly(active_axis_name)
            active_axis_name = None
            active_direction = 0
            position = self.positioner.position
            current_position_mm = self.position_for_axis_name(position, normalized_axis_name)
            distance_mm = float(target_position_mm) - current_position_mm
            if abs(distance_mm) <= tolerance_mm:
                return None, 0
            direction = 1 if distance_mm > 0 else -1

        if active_axis_name is None:
            self.positioner.jog_axis(axis, speed * direction)
            active_axis_name = normalized_axis_name
            active_direction = direction

        while True:
            if is_paused():
                self.stop_axis_by_name_quietly(active_axis_name)
                active_axis_name = None
                active_direction = 0
                wait_if_paused()
                position = self.positioner.position
                current_position_mm = self.position_for_axis_name(position, normalized_axis_name)
                if self.target_crossed(current_position_mm, target_position_mm, direction, tolerance_mm):
                    return active_axis_name, active_direction
                if active_axis_name is None:
                    self.positioner.jog_axis(axis, speed * direction)
                    active_axis_name = normalized_axis_name
                    active_direction = direction

            raise_if_stopped()
            position = self.positioner.position
            current_position_mm = self.position_for_axis_name(position, normalized_axis_name)
            if self.target_crossed(current_position_mm, target_position_mm, direction, tolerance_mm):
                return active_axis_name, active_direction
            time.sleep(0.03)

    def update_runtime_config(self, config: dict) -> None:
        self._ensure_connected()
        updater = getattr(self.positioner, "update_runtime_config", None)
        if not callable(updater):
            return

        try:
            factory = InstrumentControllerFactory()
            legacy_pulses_per_mm, x_pulses_per_mm, y_pulses_per_mm = factory.positioner_scales_from_config(config)
            updater(
                x_axis=factory.axis_from_config(config, "x_axis", 2),
                y_axis=factory.axis_from_config(config, "y_axis", 3),
                pulses_per_mm=legacy_pulses_per_mm,
                x_pulses_per_mm=x_pulses_per_mm,
                y_pulses_per_mm=y_pulses_per_mm,
                default_speed=float(config.get("default_speed", 100.0)),
            )
        except InstrumentControllerFactoryError as exc:
            raise MotionServiceError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Positioner runtime config update failed.")
            raise MotionServiceError(f"Positioner runtime config update failed: {exc}") from exc

    def cancel_motion_if_supported(self) -> None:
        cancel_motion = getattr(self.positioner, "cancel_motion", None)
        if callable(cancel_motion):
            cancel_motion()

    def stop_axis_by_name_quietly(self, axis_name: str | None) -> None:
        if axis_name is None:
            return
        try:
            self.positioner.stop_axis(self.axis_for_name(axis_name))
        except Exception:
            logger.exception("Failed to stop positioner axis %s.", axis_name)

    def stop_all_quietly(self) -> None:
        try:
            if self.positioner.is_connected:
                self.positioner.stop_all()
        except Exception:
            logger.exception("Failed to stop positioner.")

    def position_tolerance_for_axis(self, axis: int) -> float:
        tolerance = getattr(self.positioner, "_position_tolerance_mm", None)
        if callable(tolerance):
            try:
                return max(float(tolerance(axis)), 0.001)
            except Exception:
                logger.debug("Positioner-specific tolerance lookup failed.", exc_info=True)
        return 0.05

    def axis_for_name(self, axis_name: str) -> int:
        config = getattr(self.positioner, "_config", None)
        if ScanRuntimeGeometry.normalize_axis_name(axis_name) == "Y":
            return int(getattr(config, "y_axis", 3))
        return int(getattr(config, "x_axis", 2))

    @staticmethod
    def position_for_axis_name(position: Position, axis_name: str) -> float:
        return position.y_mm if ScanRuntimeGeometry.normalize_axis_name(axis_name) == "Y" else position.x_mm

    @staticmethod
    def target_crossed(
        current_position_mm: float,
        target_position_mm: float,
        direction: int,
        tolerance_mm: float,
    ) -> bool:
        if direction > 0:
            return current_position_mm >= target_position_mm - tolerance_mm
        return current_position_mm <= target_position_mm + tolerance_mm

    def _ensure_connected(self) -> None:
        if not self.positioner.is_connected:
            raise MotionServiceError("Positioner controller is not connected.")
