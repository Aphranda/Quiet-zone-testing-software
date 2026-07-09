from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from enum import IntEnum
from threading import Event, Lock

from quiet_zone_tester.hardware.interfaces import InstrumentInfo, Position
from quiet_zone_tester.hardware.transport.modbus_rtu import ModbusRtuConfig, ModbusRtuError, ModbusRtuSession

logger = logging.getLogger(__name__)


class Axis(IntEnum):
    AXIS_1 = 0
    AXIS_2 = 1
    AXIS_3 = 2
    AXIS_4 = 3
    AXIS_5 = 4


class MotionMode(IntEnum):
    HOME = 0
    JOG = 1
    RELATIVE = 2
    ABSOLUTE = 3
    STOP = 4
    ZERO = 5


class IclPositionerError(RuntimeError):
    pass


@dataclass(frozen=True)
class IclPositionerConfig:
    port: str
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    timeout_ms: int = 1000
    retries: int = 2
    retry_delay_s: float = 0.05
    x_axis: int = int(Axis.AXIS_3)
    y_axis: int = int(Axis.AXIS_4)
    pulses_per_mm: float = 1.0
    x_pulses_per_mm: float | None = None
    y_pulses_per_mm: float | None = None
    default_speed: float = 100.0
    default_acc: int = 100
    default_dec: int = 100


class IclPositionerController:
    STATUS_ERROR_MASK = 0x01
    STATUS_MOVING_MASK = 0x04
    STATUS_READY_MASK = 0x72
    STATUS_READY_VALUE = 0x72

    REG_MOTION_STATUS = 0x1003
    REG_MOTION_ALARM = 0x2203
    REG_ORDER_POSITION = 0x602A
    REG_CODER_POSITION = 0x602C
    REG_PR_MOTION_SETTING = 0x6200
    REG_PR_EXECUTION = 0x6002
    REG_PR_POSITION = 0x6201
    REG_PR_SPEED = 0x6203
    REG_PR_ACC = 0x6204
    REG_PR_DEC = 0x6205
    REG_ORIGIN_MODE = 0x600A
    REG_ORIGIN_HIGH_SPEED = 0x600F
    REG_ORIGIN_OFFSET = 0x600D
    STOP_CONFIRMATION_SAMPLES = 4
    STOP_POLL_INTERVAL_S = 0.1

    def __init__(self, config: IclPositionerConfig) -> None:
        self._config = config
        self._session = ModbusRtuSession(
            ModbusRtuConfig(
                port=config.port,
                baudrate=config.baudrate,
                bytesize=config.bytesize,
                parity=config.parity,
                stopbits=config.stopbits,
                timeout_s=max(config.timeout_ms / 1000.0, 0.1),
                retries=config.retries,
                retry_delay_s=config.retry_delay_s,
            )
        )
        self._connected = False
        self._io_lock = Lock()
        self._motion_cancelled = Event()

    def connect(self) -> InstrumentInfo:
        self._session.open()
        self._connected = True
        try:
            self._verify_axes()
        except Exception:
            self.disconnect()
            raise

        info = InstrumentInfo(
            resource_name=self._config.port,
            model=(
                "iCL-RS X/Y Positioner "
                f"(X={self._axis_label(self._config.x_axis)}, "
                f"Y={self._axis_label(self._config.y_axis)})"
            ),
            serial_number="UNKNOWN",
            is_mock=False,
        )
        logger.info("Connected positioner: %s", info)
        return info

    def disconnect(self) -> None:
        logger.info("Disconnecting positioner: %s", self._config.port)
        self._session.close()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._session.is_open

    @property
    def position(self) -> Position:
        self._ensure_connected()
        return self._actual_position()

    def update_runtime_config(
        self,
        *,
        x_axis: int | None = None,
        y_axis: int | None = None,
        pulses_per_mm: float | None = None,
        x_pulses_per_mm: float | None = None,
        y_pulses_per_mm: float | None = None,
        default_speed: float | None = None,
    ) -> None:
        updates: dict[str, float | int | None] = {}
        if x_axis is not None:
            self._validate_axis(x_axis)
            updates["x_axis"] = int(x_axis)
        if y_axis is not None:
            self._validate_axis(y_axis)
            updates["y_axis"] = int(y_axis)
        for key, value in (
            ("pulses_per_mm", pulses_per_mm),
            ("x_pulses_per_mm", x_pulses_per_mm),
            ("y_pulses_per_mm", y_pulses_per_mm),
            ("default_speed", default_speed),
        ):
            if value is None:
                continue
            numeric_value = float(value)
            if numeric_value <= 0.0:
                raise IclPositionerError(f"{key} must be greater than zero.")
            updates[key] = numeric_value

        if not updates:
            return

        self._config = replace(self._config, **updates)
        logger.info(
            (
                "Updated positioner runtime config: X=%s scale=%.6f unit/mm, "
                "Y=%s scale=%.6f unit/mm, default speed=%.3f."
            ),
            self._axis_label(self._config.x_axis),
            self._pulses_per_mm_for_axis(self._config.x_axis),
            self._axis_label(self._config.y_axis),
            self._pulses_per_mm_for_axis(self._config.y_axis),
            self._config.default_speed,
        )

    def move_to(self, x_mm: float, y_mm: float, speed_mm_s: float | None = None) -> Position:
        self._ensure_connected()
        self._motion_cancelled.clear()
        speed = self._config.default_speed if speed_mm_s is None else speed_mm_s
        if abs(speed) <= 1e-9:
            raise IclPositionerError("扫描架绝对运动速度不能为 0。")

        current = self._actual_position()
        axis_targets = {
            self._config.x_axis: x_mm,
            self._config.y_axis: y_mm,
        }
        moved_axes: list[int] = []
        logger.info(
            (
                "Moving positioner to x=%.3f mm y=%.3f mm speed=%.3f mm/s "
                "from x=%.3f mm y=%.3f mm"
            ),
            x_mm,
            y_mm,
            speed,
            current.x_mm,
            current.y_mm,
        )

        if not self._position_matches(self._config.x_axis, current.x_mm, x_mm):
            self._raise_if_motion_cancelled()
            self.prepare_axis_absolute(self._config.x_axis, x_mm, speed)
            moved_axes.append(self._config.x_axis)
        else:
            logger.info("Positioner X axis already at %.3f mm; skipping move.", x_mm)

        if not self._position_matches(self._config.y_axis, current.y_mm, y_mm):
            self._raise_if_motion_cancelled()
            self.prepare_axis_absolute(self._config.y_axis, y_mm, speed)
            moved_axes.append(self._config.y_axis)
        else:
            logger.info("Positioner Y axis already at %.3f mm; skipping move.", y_mm)

        for axis in moved_axes:
            self._raise_if_motion_cancelled()
            logger.info("Starting prepared positioner axis %s.", self._axis_label(axis))
            self._trigger_motion(axis, MotionMode.ABSOLUTE)

        timeout_ms = self._movement_timeout_ms(current, Position(x_mm=x_mm, y_mm=y_mm), speed)
        axes_to_confirm = list(dict.fromkeys((self._config.x_axis, self._config.y_axis)))
        self.wait_axes(axes_to_confirm, timeout_ms, axis_targets)
        self._stop_axes_after_absolute_move(axes_to_confirm)
        self.wait_axes(axes_to_confirm, max(self._config.timeout_ms, 1000), axis_targets)
        return self._actual_position()

    def self_test(self, distance_mm: float = 5.0) -> Position:
        self._ensure_connected()
        if distance_mm <= 0.0:
            raise IclPositionerError("扫描架自检距离必须大于 0。")

        origin = self.position
        logger.info(
            "Starting positioner self-test from x=%.3f mm y=%.3f mm with distance %.3f mm.",
            origin.x_mm,
            origin.y_mm,
            distance_mm,
        )
        try:
            self.move_to(origin.x_mm + distance_mm, origin.y_mm)
            self.move_to(origin.x_mm + distance_mm, origin.y_mm + distance_mm)
            return self.move_to(origin.x_mm, origin.y_mm)
        except Exception:
            logger.exception("Positioner self-test failed; attempting to return to original position.")
            try:
                self.move_to(origin.x_mm, origin.y_mm)
            except Exception:
                logger.exception("Failed to return positioner after self-test failure.")
            raise

    def move_axis_absolute(self, axis: int, position_mm: float, speed: float) -> None:
        self.prepare_axis_absolute(axis, position_mm, speed)
        self._trigger_motion(axis, MotionMode.ABSOLUTE)

    def move_axis_to(self, axis: int, position_mm: float, speed_mm_s: float | None = None) -> Position:
        self._ensure_connected()
        self._validate_axis(axis)
        self._motion_cancelled.clear()
        speed = self._config.default_speed if speed_mm_s is None else speed_mm_s
        if abs(speed) <= 1e-9:
            raise IclPositionerError("扫描架绝对运动速度不能为 0。")

        current = self._actual_position()
        current_axis_position_mm = self._position_for_axis(axis, current)
        if self._position_matches(axis, current_axis_position_mm, position_mm):
            logger.info("Positioner axis %s already at %.3f mm; skipping move.", self._axis_label(axis), position_mm)
            return current

        logger.info(
            "Moving positioner axis %s to %.3f mm at %.3f mm/s from %.3f mm.",
            self._axis_label(axis),
            position_mm,
            speed,
            current_axis_position_mm,
        )
        self.prepare_axis_absolute(axis, position_mm, speed)
        self._raise_if_motion_cancelled()
        self._trigger_motion(axis, MotionMode.ABSOLUTE)

        distance_mm = abs(position_mm - current_axis_position_mm)
        timeout_ms = max(self._config.timeout_ms, int((distance_mm / max(abs(speed), 0.001) + 10.0) * 1000.0))
        axis_targets = {axis: position_mm}
        self.wait_axes([axis], timeout_ms, axis_targets)
        self._stop_axes_after_absolute_move([axis])
        self.wait_axes([axis], max(self._config.timeout_ms, 1000), axis_targets)
        return self._actual_position()

    def prepare_axis_absolute(self, axis: int, position_mm: float, speed: float) -> None:
        pulses = self._mm_to_pulse(axis, position_mm)
        speed_pulses = self._speed_to_pulse(axis, speed)
        logger.info(
            (
                "Preparing positioner axis %s absolute target %.3f mm "
                "(raw=%s) at %.3f mm/s (raw speed=%s)."
            ),
            self._axis_label(axis),
            position_mm,
            pulses,
            speed,
            speed_pulses,
        )
        self._write_register_32(axis, self.REG_PR_POSITION, pulses)
        self._write_register(axis, self.REG_PR_SPEED, speed_pulses)
        self._write_register(axis, self.REG_PR_ACC, self._config.default_acc)
        self._write_register(axis, self.REG_PR_DEC, self._config.default_dec)
        self._prepare_motion_mode(axis, MotionMode.ABSOLUTE)

    def jog_axis(self, axis: int, speed_mm_s: float) -> None:
        self._ensure_connected()
        self._motion_cancelled.clear()
        speed_pulses = self._speed_to_pulse(axis, speed_mm_s)
        if speed_pulses == 0:
            raise IclPositionerError("扫描架点动速度不能为 0。")

        logger.info(
            "Jogging positioner axis %s at %.3f mm/s.",
            self._axis_label(axis),
            speed_mm_s,
        )
        self._write_register(axis, self.REG_PR_SPEED, speed_pulses)
        self._write_register(axis, self.REG_PR_ACC, self._config.default_acc)
        self._write_register(axis, self.REG_PR_DEC, self._config.default_dec)
        self._execute_motion(axis, MotionMode.JOG)

    def stop_axis(self, axis: int) -> None:
        self._ensure_connected()
        self._motion_cancelled.set()
        logger.info("Stopping positioner axis %s.", self._axis_label(axis))
        self._execute_motion(axis, MotionMode.STOP)

    def stop_all(self) -> None:
        self._ensure_connected()
        self._motion_cancelled.set()
        errors: list[str] = []
        for axis in (self._config.x_axis, self._config.y_axis):
            try:
                self.stop_axis(axis)
            except Exception as exc:
                logger.exception("Failed to stop positioner axis %s.", self._axis_label(axis))
                errors.append(f"{self._axis_label(axis)}: {exc}")
        if errors:
            raise IclPositionerError("扫描架停止失败：" + "；".join(errors))

    def cancel_motion(self) -> None:
        self._motion_cancelled.set()

    def wait_axes(
        self,
        axes: list[int],
        timeout_ms: int,
        target_positions_mm: dict[int, float] | None = None,
    ) -> None:
        del timeout_ms
        last_positions: dict[int, float] = {}
        previous_positions: dict[int, float] = {}
        stable_counts: dict[int, int] = {axis: 0 for axis in axes}
        while True:
            self._raise_if_motion_cancelled()
            for axis in axes:
                target_position_mm = None if target_positions_mm is None else target_positions_mm.get(axis)
                stopped, _status, actual_position_mm = self._axis_has_stopped(axis, target_position_mm)
                if actual_position_mm is not None:
                    last_positions[axis] = actual_position_mm
                    previous_position_mm = previous_positions.get(axis)
                    if stopped and self._axis_position_is_stable(axis, actual_position_mm, previous_positions):
                        stable_counts[axis] += 1
                    elif stopped:
                        stable_counts[axis] = 1
                    else:
                        stable_counts[axis] = 0
                    previous_positions[axis] = actual_position_mm
                elif stopped:
                    stable_counts[axis] = self.STOP_CONFIRMATION_SAMPLES
                else:
                    stable_counts[axis] = 0

            if all(stable_counts.get(axis, 0) >= self.STOP_CONFIRMATION_SAMPLES for axis in axes):
                self._log_target_offsets(last_positions, target_positions_mm)
                return
            time.sleep(self.STOP_POLL_INTERVAL_S)

    def _execute_motion(self, axis: int, mode: MotionMode) -> None:
        self._prepare_motion_mode(axis, mode)
        self._trigger_motion(axis, mode)

    def _stop_axes_after_absolute_move(self, axes: list[int]) -> None:
        errors: list[str] = []
        for axis in axes:
            try:
                logger.info("Sending final stop to positioner axis %s after absolute move.", self._axis_label(axis))
                self._execute_motion(axis, MotionMode.STOP)
            except Exception as exc:
                logger.exception("Failed to send final stop to positioner axis %s.", self._axis_label(axis))
                errors.append(f"{self._axis_label(axis)}: {exc}")

        if errors:
            raise IclPositionerError("扫描架步进停止失败：" + "；".join(errors))

    def _prepare_motion_mode(self, axis: int, mode: MotionMode) -> None:
        if mode is MotionMode.JOG:
            self._write_register(axis, self.REG_PR_MOTION_SETTING, 2)
        elif mode is MotionMode.ABSOLUTE:
            self._write_register(axis, self.REG_PR_MOTION_SETTING, 1)
        elif mode is MotionMode.RELATIVE:
            self._write_register(axis, self.REG_PR_MOTION_SETTING, 0x41)
        elif mode is MotionMode.HOME:
            self._write_register(axis, self.REG_ORIGIN_MODE, 6)

    def _trigger_motion(self, axis: int, mode: MotionMode) -> None:
        motion_mode = {
            MotionMode.HOME: 0x20,
            MotionMode.JOG: 0x10,
            MotionMode.RELATIVE: 0x10,
            MotionMode.ABSOLUTE: 0x10,
            MotionMode.STOP: 0x40,
            MotionMode.ZERO: 0x21,
        }[mode]

        self._write_register(axis, self.REG_PR_EXECUTION, motion_mode)

    def _axis_has_stopped(
        self,
        axis: int,
        target_position_mm: float | None = None,
    ) -> tuple[bool, int, float | None]:
        status = self._read_register(axis, self.REG_MOTION_STATUS)
        if (
            target_position_mm is None
            and (status & self.STATUS_READY_MASK) == self.STATUS_READY_VALUE
            and status < 0xFF
        ):
            return True, status, None

        if target_position_mm is None:
            return False, status, None

        if status >= 0xFF or status & self.STATUS_ERROR_MASK:
            return False, status, None

        actual_position_mm = self._read_actual_position_mm(axis)
        if status & self.STATUS_MOVING_MASK:
            return False, status, actual_position_mm

        return True, status, actual_position_mm

    def _read_position_mm(self, axis: int) -> float:
        pulses = self._read_register_32(axis, self.REG_ORDER_POSITION)
        return self._pulse_to_mm(axis, pulses)

    def _read_actual_position_mm(self, axis: int) -> float:
        pulses = self._read_register_32(axis, self.REG_CODER_POSITION)
        return self._pulse_to_mm(axis, pulses)

    def _actual_position(self) -> Position:
        return Position(
            x_mm=self._read_actual_position_mm(self._config.x_axis),
            y_mm=self._read_actual_position_mm(self._config.y_axis),
        )

    def _position_for_axis(self, axis: int, position: Position) -> float:
        if axis == self._config.x_axis:
            return position.x_mm
        if axis == self._config.y_axis:
            return position.y_mm
        return self._read_actual_position_mm(axis)

    def _movement_timeout_ms(self, current: Position, target: Position, speed_mm_s: float) -> int:
        distance_mm = max(abs(target.x_mm - current.x_mm), abs(target.y_mm - current.y_mm))
        estimated_ms = int((distance_mm / max(abs(speed_mm_s), 0.001) + 10.0) * 1000.0)
        return max(self._config.timeout_ms, estimated_ms)

    def _position_matches(self, axis: int, actual_mm: float, target_mm: float) -> bool:
        return abs(actual_mm - target_mm) <= self._position_tolerance_mm(axis)

    def _position_tolerance_mm(self, axis: int) -> float:
        return max(1.0 / self._pulses_per_mm_for_axis(axis), 0.001)

    def _axis_position_is_stable(
        self,
        axis: int,
        actual_position_mm: float,
        previous_positions: dict[int, float],
    ) -> bool:
        previous_position_mm = previous_positions.get(axis)
        if previous_position_mm is None:
            return False
        return abs(actual_position_mm - previous_position_mm) <= self._stable_position_tolerance_mm(axis)

    def _stable_position_tolerance_mm(self, axis: int) -> float:
        return max(0.5 / self._pulses_per_mm_for_axis(axis), 0.0005)

    def _log_target_offsets(
        self,
        last_positions: dict[int, float],
        target_positions_mm: dict[int, float] | None,
    ) -> None:
        if target_positions_mm is None:
            return

        for axis, target_position_mm in target_positions_mm.items():
            actual_position_mm = last_positions.get(axis)
            if actual_position_mm is None or self._position_matches(axis, actual_position_mm, target_position_mm):
                continue
            logger.warning(
                (
                    "Positioner axis %s stopped at %.3f mm while target was %.3f mm. "
                    "Continuing scan because the axis is no longer moving."
                ),
                self._axis_label(axis),
                actual_position_mm,
                target_position_mm,
            )

    def _read_register(self, axis: int, address: int) -> int:
        self._validate_axis(axis)
        response = self._transact(bytes([axis, 0x03, address >> 8, address & 0xFF, 0x00, 0x01]), 7)
        return int.from_bytes(response[3:5], byteorder="big", signed=False)

    def _read_register_32(self, axis: int, address: int) -> int:
        self._validate_axis(axis)
        response = self._transact(bytes([axis, 0x03, address >> 8, address & 0xFF, 0x00, 0x02]), 9)
        data = response[3:7]
        return int.from_bytes(data, byteorder="big", signed=True)

    def _write_register(self, axis: int, address: int, value: int) -> None:
        self._validate_axis(axis)
        value &= 0xFFFF
        self._transact(
            bytes([axis, 0x06, address >> 8, address & 0xFF, value >> 8, value & 0xFF]),
            8,
        )

    def _write_register_32(self, axis: int, address: int, value: int) -> None:
        self._validate_axis(axis)
        data = int(value).to_bytes(4, byteorder="big", signed=True)
        payload = bytes([axis, 0x10, address >> 8, address & 0xFF, 0x00, 0x02, 0x04]) + data
        self._transact(payload, 8)

    def _transact(self, payload: bytes, expected_min_length: int) -> bytes:
        try:
            with self._io_lock:
                return self._session.transact(payload, expected_min_length)
        except ModbusRtuError as exc:
            raise IclPositionerError(str(exc)) from exc

    def _verify_axes(self) -> None:
        for axis in (self._config.x_axis, self._config.y_axis):
            self._validate_axis(axis)
            alarm = self._read_register(axis, self.REG_MOTION_ALARM)
            self._read_register(axis, self.REG_MOTION_STATUS)
            if alarm:
                raise IclPositionerError(f"扫描架轴 {self._axis_label(axis)} 报警：0x{alarm:04X}")

    def _mm_to_pulse(self, axis: int, distance_mm: float) -> int:
        return int(round(distance_mm * self._pulses_per_mm_for_axis(axis)))

    def _pulse_to_mm(self, axis: int, pulse: int) -> float:
        return pulse / self._pulses_per_mm_for_axis(axis)

    def _speed_to_pulse(self, axis: int, speed: float) -> int:
        del axis
        return int(round(speed))

    def _pulses_per_mm_for_axis(self, axis: int) -> float:
        if axis == self._config.x_axis and self._config.x_pulses_per_mm is not None:
            value = self._config.x_pulses_per_mm
        elif axis == self._config.y_axis and self._config.y_pulses_per_mm is not None:
            value = self._config.y_pulses_per_mm
        else:
            value = self._config.pulses_per_mm

        if value <= 0:
            raise IclPositionerError("pulses_per_mm cannot be zero or negative.")
        return float(value)

    def _raise_if_motion_cancelled(self) -> None:
        if self._motion_cancelled.is_set():
            raise IclPositionerError("扫描架运动已停止。")

    @staticmethod
    def _validate_axis(axis: int) -> None:
        if not 0 <= int(axis) <= 247:
            raise IclPositionerError(f"RS485 轴地址超出范围：{axis}，有效范围为 0-247。")

    @staticmethod
    def _axis_label(axis: int) -> str:
        axis_value = int(axis)
        return f"Axis{axis_value + 1:02d}/ID={axis_value}"

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError("Positioner is not connected.")
