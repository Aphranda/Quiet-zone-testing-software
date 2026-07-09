from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from quiet_zone_tester.domains.scan_management.models import ScanSettings
from quiet_zone_tester.domains.scan_management.scan_runtime_geometry import (
    PhysicalOrigin,
    ScanRuntimeGeometry,
)
from quiet_zone_tester.hardware import Position
from quiet_zone_tester.models import SParameterTrace

logger = logging.getLogger(__name__)

DEFAULT_STEP_SPEED_MM_S = 20.0
DEFAULT_SETTLE_DELAY_S = 0.3


class ScanRuntimeMotion(Protocol):
    def query_position(self) -> Position:
        ...

    def move_axis_to(self, axis_name: str, position_mm: float, speed_mm_s: float) -> Position:
        ...

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
        ...

    def stop_axis_by_name_quietly(self, axis_name: str | None) -> None:
        ...


class ScanRuntimeServiceError(RuntimeError):
    def __init__(self, message: str, partial_results: list[SParameterTrace] | None = None) -> None:
        super().__init__(message)
        self.partial_results = partial_results or []


@dataclass(frozen=True)
class ScanRuntimeService:
    motion: ScanRuntimeMotion
    configure_vna_for_scan: Callable[[dict], None]
    measure_trace: Callable[[dict], SParameterTrace]
    save_trace: Callable[..., Path]
    checkpoint: Callable[[], None]
    sleep_interruptibly: Callable[[float], None]
    wait_if_paused: Callable[[], None]
    raise_if_stopped: Callable[[], None]
    is_paused: Callable[[], bool]
    stop_requested: Callable[[], bool]
    stop_positioner_quietly: Callable[[], None]
    probe_offset_filename_tag: Callable[[dict], str]
    scan_output_dir: Callable[[dict], Path | None]

    def run_step_scan(
        self,
        settings: dict | ScanSettings,
        on_progress: Callable[[int, int, SParameterTrace | None], None] | None = None,
    ) -> list[SParameterTrace]:
        try:
            scan_settings = ScanSettings.from_mapping(settings)
        except ValueError as exc:
            raise ScanRuntimeServiceError(str(exc)) from exc
        settings = scan_settings.to_dict()
        volume = scan_settings.scan_volume
        points = volume.scan_points()
        total = int(points.shape[0])
        settle_delay_s = max(float(settings.get("settle_delay_s", DEFAULT_SETTLE_DELAY_S)), 0.0)
        speed_mm_s = max(
            abs(float(settings.get("step_speed_mm_s", settings.get("default_speed", DEFAULT_STEP_SPEED_MM_S)))),
            0.001,
        )

        self.configure_vna_for_scan(settings)
        results: list[SParameterTrace] = []
        try:
            if total <= 0:
                return results

            self.checkpoint()
            physical_origin = self.motion.query_position()
            logical_origin_x_mm = float(points[0][0])
            logical_origin_y_mm = float(points[0][1])
            physical_origin_map = PhysicalOrigin(
                x_mm=physical_origin.x_mm,
                y_mm=physical_origin.y_mm,
                logical_x_mm=logical_origin_x_mm,
                logical_y_mm=logical_origin_y_mm,
            )
            logger.info(
                (
                    "Step scan physical origin: logical x=%.3f mm, y=%.3f mm "
                    "maps to current position x=%.3f mm, y=%.3f mm."
                ),
                logical_origin_x_mm,
                logical_origin_y_mm,
                physical_origin.x_mm,
                physical_origin.y_mm,
            )

            logical_x_mm: float | None = None
            logical_y_mm: float | None = None
            for index, point in enumerate(points, start=1):
                self.checkpoint()
                target_x_mm = float(point[0])
                target_y_mm = float(point[1])
                physical_target = ScanRuntimeGeometry.physical_target(
                    physical_origin_map,
                    target_x_mm,
                    target_y_mm,
                )
                logger.info(
                    (
                        "Step scan point %s/%s: logical target x=%.3f mm, y=%.3f mm "
                        "(physical x=%.3f mm, y=%.3f mm) at %.3f mm/s."
                    ),
                    index,
                    total,
                    target_x_mm,
                    target_y_mm,
                    physical_target.x_mm,
                    physical_target.y_mm,
                    speed_mm_s,
                )

                for axis_name, logical_axis_target_mm in ScanRuntimeGeometry.axis_moves(
                    logical_x_mm,
                    logical_y_mm,
                    target_x_mm,
                    target_y_mm,
                ):
                    self.checkpoint()
                    physical_axis_target_mm = (
                        physical_target.y_mm if axis_name.strip().upper() == "Y" else physical_target.x_mm
                    )
                    logger.info(
                        (
                            "Step scan point %s/%s: moving %s axis to logical %.3f mm "
                            "(physical %.3f mm)."
                        ),
                        index,
                        total,
                        axis_name,
                        logical_axis_target_mm,
                        physical_axis_target_mm,
                    )
                    position = self.motion.move_axis_to(axis_name, physical_axis_target_mm, speed_mm_s)
                    self.checkpoint()
                    logger.info(
                        (
                            "Step scan point %s/%s: %s axis stopped; "
                            "physical actual x=%.3f mm, y=%.3f mm."
                        ),
                        index,
                        total,
                        axis_name,
                        position.x_mm,
                        position.y_mm,
                    )

                logical_x_mm = target_x_mm
                logical_y_mm = target_y_mm
                self.checkpoint()
                logger.info(
                    "Step scan point %s/%s: logical position settled at x=%.3f mm, y=%.3f mm.",
                    index,
                    total,
                    target_x_mm,
                    target_y_mm,
                )
                if on_progress is not None:
                    on_progress(index, total, None)
                self.sleep_interruptibly(settle_delay_s)
                self.checkpoint()
                logger.info("Step scan point %s/%s: reading VNA trace.", index, total)
                trace = self.measure_trace(settings)
                logger.info("Step scan point %s/%s: VNA trace received.", index, total)
                self.save_trace(
                    trace,
                    position_mm=(target_x_mm, target_y_mm),
                    scan_mode="step",
                    file_flag=str(settings.get("file_flag", "")),
                    filename_tag=self.probe_offset_filename_tag(settings),
                    point_index=index,
                    output_dir=self.scan_output_dir(settings),
                )
                results.append(trace)
                if on_progress is not None:
                    on_progress(index, total, trace)
        except Exception as exc:
            self.stop_positioner_quietly()
            if self.stop_requested():
                logger.info("Step scan stopped by user request.")
                return results
            raise ScanRuntimeServiceError(f"步进扫描失败，扫描架已停机：{exc}", results) from exc

        return results

    def run_continuous_scan(
        self,
        settings: dict | ScanSettings,
        on_progress: Callable[[int, int, SParameterTrace | None], None] | None = None,
    ) -> list[SParameterTrace]:
        try:
            scan_settings = ScanSettings.from_mapping(settings)
        except ValueError as exc:
            raise ScanRuntimeServiceError(str(exc)) from exc
        settings = scan_settings.to_dict()
        speed_mm_s = float(settings.get("continuous_speed_mm_s", settings.get("step_speed_mm_s", 100.0)))
        if abs(speed_mm_s) <= 1e-9:
            raise ScanRuntimeServiceError("匀速测试速度不能为 0。")
        speed_mm_s = abs(speed_mm_s)
        volume = scan_settings.scan_volume
        points = volume.scan_points()
        total = int(points.shape[0])

        self.configure_vna_for_scan(settings)
        results: list[SParameterTrace] = []

        active_axis_name: str | None = None
        active_direction = 0
        try:
            if total <= 0:
                return results

            self.checkpoint()
            physical_origin = self.motion.query_position()
            logical_origin_x_mm = float(points[0][0])
            logical_origin_y_mm = float(points[0][1])
            physical_origin_map = PhysicalOrigin(
                x_mm=physical_origin.x_mm,
                y_mm=physical_origin.y_mm,
                logical_x_mm=logical_origin_x_mm,
                logical_y_mm=logical_origin_y_mm,
            )
            logger.info(
                (
                    "Continuous scan physical origin: logical x=%.3f mm, y=%.3f mm "
                    "maps to current position x=%.3f mm, y=%.3f mm."
                ),
                logical_origin_x_mm,
                logical_origin_y_mm,
                physical_origin.x_mm,
                physical_origin.y_mm,
            )

            logical_x_mm = logical_origin_x_mm
            logical_y_mm = logical_origin_y_mm
            if on_progress is not None:
                on_progress(1, total, None)
            self.checkpoint()
            trace = self.measure_trace(settings)
            self.save_trace(
                trace,
                position_mm=(logical_x_mm, logical_y_mm),
                scan_mode="continuous",
                file_flag=str(settings.get("file_flag", "")),
                filename_tag=self.probe_offset_filename_tag(settings),
                point_index=1,
                output_dir=self.scan_output_dir(settings),
            )
            results.append(trace)
            if on_progress is not None:
                on_progress(1, total, trace)

            point_list = [(float(point[0]), float(point[1])) for point in points]
            for index, (target_x_mm, target_y_mm) in enumerate(point_list[1:], start=2):
                self.checkpoint()
                physical_target = ScanRuntimeGeometry.physical_target(
                    physical_origin_map,
                    target_x_mm,
                    target_y_mm,
                )
                logger.info(
                    (
                        "Continuous scan point %s/%s: logical target x=%.3f mm, y=%.3f mm "
                        "(physical x=%.3f mm, y=%.3f mm) at %.3f mm/s."
                    ),
                    index,
                    total,
                    target_x_mm,
                    target_y_mm,
                    physical_target.x_mm,
                    physical_target.y_mm,
                    speed_mm_s,
                )

                for axis_name, logical_axis_target_mm in ScanRuntimeGeometry.axis_moves(
                    logical_x_mm,
                    logical_y_mm,
                    target_x_mm,
                    target_y_mm,
                ):
                    physical_axis_target_mm = (
                        physical_target.y_mm if axis_name.strip().upper() == "Y" else physical_target.x_mm
                    )
                    active_axis_name, active_direction = self.motion.jog_axis_until(
                        axis_name=axis_name,
                        target_position_mm=physical_axis_target_mm,
                        speed_mm_s=speed_mm_s,
                        active_axis_name=active_axis_name,
                        active_direction=active_direction,
                        wait_if_paused=self.wait_if_paused,
                        raise_if_stopped=self.raise_if_stopped,
                        is_paused=self.is_paused,
                    )
                    logger.info(
                        (
                            "Continuous scan point %s/%s: %s axis crossed logical %.3f mm "
                            "(physical %.3f mm)."
                        ),
                        index,
                        total,
                        axis_name,
                        logical_axis_target_mm,
                        physical_axis_target_mm,
                    )

                next_motion = ScanRuntimeGeometry.next_continuous_motion(
                    point_list,
                    index - 1,
                    target_x_mm,
                    target_y_mm,
                )
                if ScanRuntimeGeometry.should_stop_before_continuous_sample(
                    active_axis_name,
                    active_direction,
                    next_motion,
                ):
                    self.motion.stop_axis_by_name_quietly(active_axis_name)
                    active_axis_name = None
                    active_direction = 0

                if on_progress is not None:
                    on_progress(index, total, None)
                if self.is_paused() and active_axis_name is not None:
                    self.motion.stop_axis_by_name_quietly(active_axis_name)
                    active_axis_name = None
                    active_direction = 0
                self.checkpoint()
                trace = self.measure_trace(settings)
                if self.is_paused() and active_axis_name is not None:
                    self.motion.stop_axis_by_name_quietly(active_axis_name)
                    active_axis_name = None
                    active_direction = 0
                    self.checkpoint()
                self.save_trace(
                    trace,
                    position_mm=(target_x_mm, target_y_mm),
                    scan_mode="continuous",
                    file_flag=str(settings.get("file_flag", "")),
                    filename_tag=self.probe_offset_filename_tag(settings),
                    point_index=index,
                    output_dir=self.scan_output_dir(settings),
                )
                results.append(trace)
                if on_progress is not None:
                    on_progress(index, total, trace)
                logical_x_mm = target_x_mm
                logical_y_mm = target_y_mm
        except Exception as exc:
            self.stop_positioner_quietly()
            if self.stop_requested():
                logger.info("Continuous scan stopped by user request.")
                return results
            raise ScanRuntimeServiceError(f"匀速扫描失败，扫描架已停机：{exc}", results) from exc
        finally:
            if active_axis_name is not None:
                self.motion.stop_axis_by_name_quietly(active_axis_name)

        return results
