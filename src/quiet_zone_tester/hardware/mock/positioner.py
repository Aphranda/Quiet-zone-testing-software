from __future__ import annotations

import logging
import time

from quiet_zone_tester.hardware.interfaces import InstrumentInfo, Position

logger = logging.getLogger(__name__)


class MockPositionerController:
    """Mock positioner for UI and workflow testing without chamber hardware."""

    def __init__(self, x_axis: int = 2, y_axis: int = 3) -> None:
        self._connected = False
        self._x_axis = x_axis
        self._y_axis = y_axis
        self._position = Position(x_mm=0.0, y_mm=0.0)
        self._jog_axis: int | None = None
        self._jog_speed_mm_s = 0.0
        self._jog_updated_at = time.monotonic()

    def connect(self) -> InstrumentInfo:
        logger.info("Connecting mock positioner.")
        time.sleep(0.25)
        self._connected = True
        return InstrumentInfo(
            resource_name="MOCK::POSITIONER::001",
            model="Mock X/Y Positioner",
            serial_number="POS-MOCK-001",
            is_mock=True,
        )

    def disconnect(self) -> None:
        logger.info("Disconnecting mock positioner.")
        time.sleep(0.1)
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def position(self) -> Position:
        self._advance_jog()
        return self._position

    def move_to(self, x_mm: float, y_mm: float, speed_mm_s: float | None = None) -> Position:
        self._ensure_connected()
        self._advance_jog()
        self._jog_axis = None
        self._jog_speed_mm_s = 0.0

        delta = abs(x_mm - self._position.x_mm) + abs(y_mm - self._position.y_mm)
        speed = max(abs(speed_mm_s or 100.0), 1.0)
        time.sleep(min(0.45, 0.02 + delta / speed / 20.0))
        self._position = Position(x_mm=x_mm, y_mm=y_mm)
        logger.info("Mock positioner moved to x=%.3f mm, y=%.3f mm.", x_mm, y_mm)
        return self._position

    def move_axis_to(self, axis: int, position_mm: float, speed_mm_s: float | None = None) -> Position:
        self._ensure_connected()
        x_mm = self._position.x_mm
        y_mm = self._position.y_mm
        if axis == self._y_axis:
            y_mm = position_mm
        elif axis == self._x_axis:
            x_mm = position_mm
        else:
            raise ValueError(f"Unknown mock positioner axis: {axis}")
        return self.move_to(x_mm, y_mm, speed_mm_s)

    def jog_axis(self, axis: int, speed_mm_s: float) -> None:
        self._ensure_connected()
        if axis not in {self._x_axis, self._y_axis}:
            raise ValueError(f"Unknown mock positioner axis: {axis}")
        self._advance_jog()
        self._jog_axis = axis
        self._jog_speed_mm_s = speed_mm_s
        self._jog_updated_at = time.monotonic()
        logger.info("Mock positioner axis %s jogging at %.3f mm/s.", axis, speed_mm_s)

    def stop_axis(self, axis: int) -> None:
        self._ensure_connected()
        self._advance_jog()
        if self._jog_axis == axis:
            self._jog_axis = None
            self._jog_speed_mm_s = 0.0
        logger.info("Mock positioner axis %s stopped.", axis)

    def stop_all(self) -> None:
        self._ensure_connected()
        self._advance_jog()
        self._jog_axis = None
        self._jog_speed_mm_s = 0.0
        logger.info("Mock positioner stopped all axes.")

    def _advance_jog(self) -> None:
        now = time.monotonic()
        elapsed_s = max(now - self._jog_updated_at, 0.0)
        self._jog_updated_at = now
        if self._jog_axis is None or elapsed_s <= 0.0:
            return

        distance_mm = self._jog_speed_mm_s * elapsed_s
        if self._jog_axis == self._x_axis:
            self._position = Position(
                x_mm=self._position.x_mm + distance_mm,
                y_mm=self._position.y_mm,
            )
        elif self._jog_axis == self._y_axis:
            self._position = Position(
                x_mm=self._position.x_mm,
                y_mm=self._position.y_mm + distance_mm,
            )

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Mock positioner is not connected.")
