from __future__ import annotations

import csv
import json
import logging
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Event, Lock

from quiet_zone_tester.drivers import (
    InstrumentInfo,
    MockPositionerController,
    MockSwitchBoxController,
    MockVnaController,
    Position,
    PositionerController,
    SwitchBoxController,
    VnaController,
)
from quiet_zone_tester.models import ScanVolume
from quiet_zone_tester.instruments import (
    IclPositionerConfig,
    IclPositionerController,
    Lcd74000fSwitchBoxConfig,
    Lcd74000fSwitchBoxController,
    ScpiVnaController,
    Tc500SwitchBoxConfig,
    Tc500SwitchBoxController,
    VnaScpiConfig,
)
from quiet_zone_tester.models import SParameterTrace

logger = logging.getLogger(__name__)

DEFAULT_STEP_SPEED_MM_S = 20.0
DEFAULT_SETTLE_DELAY_S = 0.3


class InstrumentServiceError(RuntimeError):
    pass


class InstrumentService:
    """Business workflow layer between UI and instrument drivers."""

    def __init__(
        self,
        vna: VnaController | None = None,
        positioner: PositionerController | None = None,
        switch_box: SwitchBoxController | None = None,
    ) -> None:
        self._vna = vna
        self._positioner = positioner
        self._switch_box = switch_box
        self._external_vna = vna is not None
        self._external_positioner = positioner is not None
        self._external_switch_box = switch_box is not None
        self._stop_event = Event()
        self._resume_event = Event()
        self._resume_event.set()
        self._scan_lock = Lock()
        self._last_scan_output_dir: Path | None = None

    @property
    def last_scan_output_dir(self) -> Path | None:
        return self._last_scan_output_dir

    def connect_all(self, config: dict | None = None) -> list[InstrumentInfo]:
        logger.info("Connecting instrument set with config: %s", config or {})
        try:
            vna_info = self.connect_vna(config or {})
            positioner_info = self.connect_positioner(config or {})
            switch_box_info = self.connect_switch_box(config or {})
        except Exception as exc:
            logger.exception("Instrument connection failed; cleaning up partial connections.")
            self._cleanup_after_failed_connect()
            if isinstance(exc, InstrumentServiceError):
                raise
            raise InstrumentServiceError(f"仪器连接失败：{exc}") from exc
        return [vna_info, positioner_info, switch_box_info]

    def connect_vna(self, config: dict | None = None) -> InstrumentInfo:
        logger.info("Connecting VNA with config: %s", config or {})
        try:
            self._configure_vna_backend((config or {}).get("vna", config or {}))
            if self._vna is None:
                raise InstrumentServiceError("VNA controller is not configured.")
            if self._vna.is_connected:
                self._vna.disconnect()
            return self._vna.connect()
        except Exception as exc:
            logger.exception("VNA connection failed.")
            self._cleanup_controller("vna")
            if isinstance(exc, InstrumentServiceError):
                raise
            raise InstrumentServiceError(f"VNA 连接失败：{exc}") from exc

    def connect_positioner(self, config: dict | None = None) -> InstrumentInfo:
        logger.info("Connecting positioner with config: %s", config or {})
        try:
            self._configure_positioner_backend((config or {}).get("positioner", config or {}))
            if self._positioner is None:
                raise InstrumentServiceError("Positioner controller is not configured.")
            if self._positioner.is_connected:
                self._positioner.disconnect()
            return self._positioner.connect()
        except Exception as exc:
            logger.exception("Positioner connection failed.")
            self._cleanup_controller("positioner")
            if isinstance(exc, InstrumentServiceError):
                raise
            raise InstrumentServiceError(f"扫描架连接失败：{exc}") from exc

    def connect_switch_box(self, config: dict | None = None) -> InstrumentInfo:
        logger.info("Connecting switch box with config: %s", config or {})
        try:
            self._configure_switch_box_backend((config or {}).get("switch_box", config or {}))
            if self._switch_box is None:
                raise InstrumentServiceError("Switch box controller is not configured.")
            if self._switch_box.is_connected:
                self._switch_box.disconnect()
            return self._switch_box.connect()
        except Exception as exc:
            logger.exception("Switch box connection failed.")
            self._cleanup_controller("switch_box")
            if isinstance(exc, InstrumentServiceError):
                raise
            raise InstrumentServiceError(f"开关箱连接失败：{exc}") from exc

    def disconnect_all(self) -> None:
        self.request_stop_and_stop_positioner()
        logger.info("Disconnecting instrument set.")
        errors: list[Exception] = []
        for controller in (self._switch_box, self._positioner, self._vna):
            if controller is None:
                continue
            try:
                if controller.is_connected:
                    controller.disconnect()
            except Exception as exc:  # noqa: BLE001 - service must collect driver failures.
                logger.exception("Failed to disconnect controller.")
                errors.append(exc)

        if errors:
            raise InstrumentServiceError(f"Failed to disconnect {len(errors)} instrument(s).")

    def disconnect_vna(self) -> None:
        self._disconnect_controller("vna")

    def disconnect_positioner(self) -> None:
        self.request_stop_and_stop_positioner()
        self._disconnect_controller("positioner")

    def disconnect_switch_box(self) -> None:
        self._disconnect_controller("switch_box")

    @property
    def is_connected(self) -> bool:
        return (
            self._vna is not None
            and self._positioner is not None
            and self._switch_box is not None
            and self._vna.is_connected
            and self._positioner.is_connected
            and self._switch_box.is_connected
        )

    @property
    def is_vna_connected(self) -> bool:
        return self._vna is not None and self._vna.is_connected

    @property
    def is_positioner_connected(self) -> bool:
        return self._positioner is not None and self._positioner.is_connected

    @property
    def is_switch_box_connected(self) -> bool:
        return self._switch_box is not None and self._switch_box.is_connected

    def verify_ready_for_test(self) -> None:
        if self.is_connected:
            return

        missing: list[str] = []
        if not self.is_vna_connected:
            missing.append("网分仪")
        if not self.is_positioner_connected:
            missing.append("扫描架")
        if not self.is_switch_box_connected:
            missing.append("开关箱")
        raise InstrumentServiceError("真实测试模式需要全部连接后才能开始测试：" + "、".join(missing))

    def jog_positioner_axis(self, axis: int, speed_mm_s: float, config: dict | None = None) -> None:
        if not self.is_positioner_connected or self._positioner is None:
            raise InstrumentServiceError("请先连接扫描架，再执行运动。")
        try:
            if config:
                self.update_positioner_runtime_config(config)
            self._positioner.jog_axis(axis, speed_mm_s)
        except Exception as exc:
            logger.exception("Positioner jog failed.")
            raise InstrumentServiceError(f"扫描架运动失败：{exc}") from exc

    def query_positioner_position(self, config: dict | None = None) -> Position:
        if not self.is_positioner_connected or self._positioner is None:
            raise InstrumentServiceError("请先连接扫描架，再查询位置。")
        try:
            if config:
                self.update_positioner_runtime_config(config)
            return self._positioner.position
        except Exception as exc:
            logger.exception("Positioner position query failed.")
            raise InstrumentServiceError(f"扫描架位置查询失败：{exc}") from exc

    def move_positioner_absolute(
        self,
        x_mm: float,
        y_mm: float,
        speed_mm_s: float,
        config: dict | None = None,
    ) -> Position:
        if not self.is_positioner_connected or self._positioner is None:
            raise InstrumentServiceError("请先连接扫描架，再执行绝对定位。")
        try:
            if config:
                self.update_positioner_runtime_config(config)
            return self._positioner.move_to(float(x_mm), float(y_mm), float(speed_mm_s))
        except Exception as exc:
            logger.exception("Positioner absolute move failed.")
            raise InstrumentServiceError(f"扫描架绝对定位失败：{exc}") from exc

    def move_positioner_relative(
        self,
        delta_x_mm: float,
        delta_y_mm: float,
        speed_mm_s: float,
        config: dict | None = None,
    ) -> Position:
        if not self.is_positioner_connected or self._positioner is None:
            raise InstrumentServiceError("请先连接扫描架，再执行相对定位。")
        try:
            if config:
                self.update_positioner_runtime_config(config)
            current = self._positioner.position
            return self._positioner.move_to(
                current.x_mm + float(delta_x_mm),
                current.y_mm + float(delta_y_mm),
                float(speed_mm_s),
            )
        except Exception as exc:
            logger.exception("Positioner relative move failed.")
            raise InstrumentServiceError(f"扫描架相对定位失败：{exc}") from exc

    def update_positioner_runtime_config(self, config: dict | None = None) -> None:
        if not self.is_positioner_connected or self._positioner is None:
            raise InstrumentServiceError("请先连接扫描架，再更新扫描架配置。")

        positioner_config = (config or {}).get("positioner", config or {})
        legacy_pulses_per_mm, x_pulses_per_mm, y_pulses_per_mm = self._positioner_scales_from_config(
            positioner_config
        )
        updater = getattr(self._positioner, "update_runtime_config", None)
        if not callable(updater):
            return

        try:
            updater(
                x_axis=self._axis_from_config(positioner_config, "x_axis", 2),
                y_axis=self._axis_from_config(positioner_config, "y_axis", 3),
                pulses_per_mm=legacy_pulses_per_mm,
                x_pulses_per_mm=x_pulses_per_mm,
                y_pulses_per_mm=y_pulses_per_mm,
                default_speed=float(positioner_config.get("default_speed", 100.0)),
            )
        except Exception as exc:
            logger.exception("Positioner runtime config update failed.")
            raise InstrumentServiceError(f"扫描架配置更新失败：{exc}") from exc

    def stop_positioner_axis(self, axis: int) -> None:
        if not self.is_positioner_connected or self._positioner is None:
            raise InstrumentServiceError("请先连接扫描架，再停止运动。")
        try:
            self._positioner.stop_axis(axis)
        except Exception as exc:
            logger.exception("Positioner stop failed.")
            raise InstrumentServiceError(f"扫描架停止失败：{exc}") from exc

    def stop_positioner(self) -> None:
        if not self.is_positioner_connected or self._positioner is None:
            return
        try:
            self._positioner.stop_all()
        except Exception as exc:
            logger.exception("Positioner stop all failed.")
            raise InstrumentServiceError(f"扫描架停止失败：{exc}") from exc

    def request_stop(self) -> None:
        self._stop_event.set()
        self._resume_event.set()
        if self._positioner is None:
            return
        cancel_motion = getattr(self._positioner, "cancel_motion", None)
        if callable(cancel_motion):
            cancel_motion()

    def request_stop_and_stop_positioner(self) -> None:
        self.request_stop()
        self._stop_positioner_quietly()

    def reset_stop_request(self) -> None:
        self._stop_event.clear()
        self._resume_event.set()

    def request_pause(self) -> None:
        self._resume_event.clear()
        logger.info("Scan pause requested.")

    def resume_scan(self) -> None:
        self._resume_event.set()
        logger.info("Scan resume requested.")

    def acquire_preview_trace(
        self,
        start_ghz: float,
        stop_ghz: float,
        points: int,
        parameter: str,
        vna_power_dbm: float = -10.0,
        if_bandwidth_hz: float = 1000.0,
        file_flag: str = "",
    ) -> SParameterTrace:
        self.verify_ready_for_test()

        start_hz = start_ghz * 1e9
        stop_hz = stop_ghz * 1e9
        self._select_switch_box_path(parameter)
        self._vna.configure_power(vna_power_dbm)
        self._configure_vna_if_bandwidth(if_bandwidth_hz)
        self._vna.configure_sweep(start_hz, stop_hz, points)
        trace = self._vna.measure_s_parameter(parameter)
        self._save_trace_csv(
            trace,
            position_mm=self._current_position_tuple(),
            scan_mode="preview",
            file_flag=file_flag,
        )
        return trace

    def acquire_vna_trace(
        self,
        start_ghz: float,
        stop_ghz: float,
        points: int,
        parameter: str,
        vna_power_dbm: float = -10.0,
        if_bandwidth_hz: float = 1000.0,
        file_flag: str = "",
    ) -> SParameterTrace:
        if not self.is_vna_connected or self._vna is None:
            raise InstrumentServiceError("请先连接网分仪，再执行采样。")

        try:
            self.configure_vna_trace(
                start_ghz=start_ghz,
                stop_ghz=stop_ghz,
                points=points,
                parameter=parameter,
                vna_power_dbm=vna_power_dbm,
                if_bandwidth_hz=if_bandwidth_hz,
            )
            return self.sample_vna_trace(parameter, file_flag=file_flag)
        except InstrumentServiceError:
            raise
        except Exception as exc:
            logger.exception("VNA standalone sample failed.")
            raise InstrumentServiceError(f"网分仪采样失败：{exc}") from exc

    def configure_vna_trace(
        self,
        start_ghz: float,
        stop_ghz: float,
        points: int,
        parameter: str,
        vna_power_dbm: float = -10.0,
        if_bandwidth_hz: float = 1000.0,
    ) -> None:
        if not self.is_vna_connected or self._vna is None:
            raise InstrumentServiceError("请先连接网分仪，再执行配置。")

        try:
            start_hz = float(start_ghz) * 1e9
            stop_hz = float(stop_ghz) * 1e9
            self._vna.configure_power(float(vna_power_dbm))
            self._configure_vna_if_bandwidth(float(if_bandwidth_hz))
            self._vna.configure_sweep(start_hz, stop_hz, int(points))
            configure_parameter = getattr(self._vna, "configure_measurement_parameter", None)
            if callable(configure_parameter):
                configure_parameter(str(parameter))
        except InstrumentServiceError:
            raise
        except Exception as exc:
            logger.exception("VNA standalone configuration failed.")
            raise InstrumentServiceError(f"网分仪配置失败：{exc}") from exc

    def sample_vna_trace(self, parameter: str, file_flag: str = "") -> SParameterTrace:
        if not self.is_vna_connected or self._vna is None:
            raise InstrumentServiceError("请先连接网分仪，再执行采样。")

        try:
            trace = self._vna.measure_s_parameter(str(parameter))
            self._save_trace_csv(
                trace,
                position_mm=self._current_position_tuple(),
                scan_mode="standalone",
                file_flag=file_flag,
            )
            return trace
        except InstrumentServiceError:
            raise
        except Exception as exc:
            logger.exception("VNA standalone sample failed.")
            raise InstrumentServiceError(f"网分仪采样失败：{exc}") from exc

    def run_scan(
        self,
        settings: dict,
        on_progress: Callable[[int, int, SParameterTrace | None], None] | None = None,
    ) -> list[SParameterTrace]:
        if not self._scan_lock.acquire(blocking=False):
            raise InstrumentServiceError("已有扫描流程正在运行，请等待当前流程结束后再开始。")

        try:
            self.reset_stop_request()
            connection_config = settings.get("connection_config")
            if connection_config is not None:
                self.update_positioner_runtime_config(connection_config)
            self.verify_ready_for_test()
            mode = str(settings.get("scan_mode", "step")).strip().lower()
            settings = dict(settings)
            settings["scan_output_dir"] = str(self._create_scan_output_dir(settings, mode))
            if mode == "continuous":
                return self._run_continuous_scan(settings, on_progress)
            return self._run_step_scan(settings, on_progress)
        finally:
            self._scan_lock.release()

    def _configure_backends(self, config: dict) -> None:
        self._configure_vna_backend(config.get("vna", {}))
        self._configure_positioner_backend(config.get("positioner", {}))
        self._configure_switch_box_backend(config.get("switch_box", {}))

    def _configure_vna_backend(self, config: dict) -> None:
        if not self._external_vna:
            self._vna = self._create_vna_controller(config)

    def _configure_positioner_backend(self, config: dict) -> None:
        if not self._external_positioner:
            self._positioner = self._create_positioner_controller(config)

    def _configure_switch_box_backend(self, config: dict) -> None:
        if not self._external_switch_box:
            self._switch_box = self._create_switch_box_controller(config)

    def _disconnect_controller(self, name: str) -> None:
        controller = self._controller_for_name(name)
        if controller is None:
            return
        try:
            if controller.is_connected:
                controller.disconnect()
        except Exception as exc:
            logger.exception("Failed to disconnect %s.", name)
            raise InstrumentServiceError(f"{name} 断开失败：{exc}") from exc

    def _cleanup_controller(self, name: str) -> None:
        controller = self._controller_for_name(name)
        if controller is not None:
            try:
                controller.disconnect()
            except Exception:
                logger.exception("Failed to clean up %s after connection failure.", name)

        if name == "vna" and not self._external_vna:
            self._vna = None
        elif name == "positioner" and not self._external_positioner:
            self._positioner = None
        elif name == "switch_box" and not self._external_switch_box:
            self._switch_box = None

    def _cleanup_after_failed_connect(self) -> None:
        for controller in (self._switch_box, self._positioner, self._vna):
            if controller is None:
                continue
            try:
                controller.disconnect()
            except Exception:
                logger.exception("Failed to clean up controller after connection failure.")

        if not self._external_vna:
            self._vna = None
        if not self._external_positioner:
            self._positioner = None
        if not self._external_switch_box:
            self._switch_box = None

    def _select_switch_box_path(self, parameter: str) -> None:
        self.verify_ready_for_test()
        self.select_switch_box_parameter(parameter)

    def select_switch_box_parameter(self, parameter: str) -> str:
        if not self.is_switch_box_connected or self._switch_box is None:
            raise InstrumentServiceError("请先连接开关箱，再切换链路。")

        parameter = str(parameter).strip().upper()
        if not parameter:
            raise InstrumentServiceError("S 参数不能为空。")

        try:
            command = self._switch_box.select_s_parameter(parameter)
            logger.info("Switch box routed %s with command %s.", parameter, command)
            return command
        except Exception as exc:
            logger.exception("Switch box route selection failed.")
            raise InstrumentServiceError(f"开关箱切换失败：{exc}") from exc

    def send_switch_box_command(self, command: str) -> str:
        if not self.is_switch_box_connected or self._switch_box is None:
            raise InstrumentServiceError("请先连接开关箱，再发送命令。")

        command = str(command).strip()
        if not command:
            raise InstrumentServiceError("开关箱命令不能为空。")

        send_command = getattr(self._switch_box, "send_command", None)
        if not callable(send_command):
            raise InstrumentServiceError("当前开关箱驱动不支持直接发送命令。")

        try:
            response = str(send_command(command))
            logger.info("Switch box command executed: %s -> %s.", command, response)
            return response
        except Exception as exc:
            logger.exception("Switch box command failed.")
            raise InstrumentServiceError(f"开关箱命令执行失败：{exc}") from exc

    def _run_step_scan(
        self,
        settings: dict,
        on_progress: Callable[[int, int, SParameterTrace | None], None] | None,
    ) -> list[SParameterTrace]:
        volume = self._build_scan_volume(settings)
        points = volume.scan_points()
        total = int(points.shape[0])
        settle_delay_s = max(float(settings.get("settle_delay_s", DEFAULT_SETTLE_DELAY_S)), 0.0)
        speed_mm_s = max(
            abs(float(settings.get("step_speed_mm_s", settings.get("default_speed", DEFAULT_STEP_SPEED_MM_S)))),
            0.001,
        )

        self._configure_vna_for_scan(settings)
        results: list[SParameterTrace] = []
        try:
            if total <= 0:
                return results

            assert self._positioner is not None
            self._scan_checkpoint()
            physical_origin = self._positioner.position
            logical_origin_x_mm = float(points[0][0])
            logical_origin_y_mm = float(points[0][1])
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
                self._scan_checkpoint()
                target_x_mm = float(point[0])
                target_y_mm = float(point[1])
                physical_target_x_mm = physical_origin.x_mm + target_x_mm - logical_origin_x_mm
                physical_target_y_mm = physical_origin.y_mm + target_y_mm - logical_origin_y_mm
                logger.info(
                    (
                        "Step scan point %s/%s: logical target x=%.3f mm, y=%.3f mm "
                        "(physical x=%.3f mm, y=%.3f mm) at %.3f mm/s."
                    ),
                    index,
                    total,
                    target_x_mm,
                    target_y_mm,
                    physical_target_x_mm,
                    physical_target_y_mm,
                    speed_mm_s,
                )

                for axis_name, logical_axis_target_mm in self._scan_axis_moves(
                    logical_x_mm,
                    logical_y_mm,
                    target_x_mm,
                    target_y_mm,
                ):
                    self._scan_checkpoint()
                    physical_axis_target_mm = (
                        physical_target_y_mm if axis_name.strip().upper() == "Y" else physical_target_x_mm
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
                    position = self._move_positioner_axis_to(axis_name, physical_axis_target_mm, speed_mm_s)
                    self._scan_checkpoint()
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
                self._scan_checkpoint()
                logger.info(
                    "Step scan point %s/%s: logical position settled at x=%.3f mm, y=%.3f mm.",
                    index,
                    total,
                    target_x_mm,
                    target_y_mm,
                )
                if on_progress is not None:
                    on_progress(index, total, None)
                self._sleep_interruptibly(settle_delay_s)
                self._scan_checkpoint()
                logger.info("Step scan point %s/%s: reading VNA trace.", index, total)
                trace = self._measure_scan_trace(settings)
                logger.info("Step scan point %s/%s: VNA trace received.", index, total)
                self._save_trace_csv(
                    trace,
                    position_mm=(target_x_mm, target_y_mm),
                    scan_mode="step",
                    file_flag=str(settings.get("file_flag", "")),
                    filename_tag=self._probe_offset_filename_tag(settings),
                    point_index=index,
                    output_dir=self._scan_output_dir(settings),
                )
                results.append(trace)
                if on_progress is not None:
                    on_progress(index, total, trace)
        except InstrumentServiceError:
            self._stop_positioner_quietly()
            if self._stop_event.is_set():
                logger.info("Step scan stopped by user request.")
                return results
            raise
        except Exception as exc:
            self._stop_positioner_quietly()
            if self._stop_event.is_set():
                logger.info("Step scan stopped by user request: %s", exc)
                return results
            raise InstrumentServiceError(f"步进扫描失败，扫描架已停机：{exc}") from exc

        return results

    def _run_continuous_scan(
        self,
        settings: dict,
        on_progress: Callable[[int, int, SParameterTrace | None], None] | None,
    ) -> list[SParameterTrace]:
        speed_mm_s = float(settings.get("continuous_speed_mm_s", settings.get("step_speed_mm_s", 100.0)))
        if abs(speed_mm_s) <= 1e-9:
            raise InstrumentServiceError("匀速测试速度不能为 0。")
        speed_mm_s = abs(speed_mm_s)
        volume = self._build_scan_volume(settings)
        points = volume.scan_points()
        total = int(points.shape[0])

        self._configure_vna_for_scan(settings)
        results: list[SParameterTrace] = []

        active_axis_name: str | None = None
        active_direction = 0
        try:
            if total <= 0:
                return results

            assert self._positioner is not None
            self._scan_checkpoint()
            physical_origin = self._positioner.position
            logical_origin_x_mm = float(points[0][0])
            logical_origin_y_mm = float(points[0][1])
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
            self._scan_checkpoint()
            trace = self._measure_scan_trace(settings)
            self._save_trace_csv(
                trace,
                position_mm=(logical_x_mm, logical_y_mm),
                scan_mode="continuous",
                file_flag=str(settings.get("file_flag", "")),
                filename_tag=self._probe_offset_filename_tag(settings),
                point_index=1,
                output_dir=self._scan_output_dir(settings),
            )
            results.append(trace)
            if on_progress is not None:
                on_progress(1, total, trace)

            point_list = [(float(point[0]), float(point[1])) for point in points]
            for index, (target_x_mm, target_y_mm) in enumerate(point_list[1:], start=2):
                self._scan_checkpoint()
                physical_target_x_mm = physical_origin.x_mm + target_x_mm - logical_origin_x_mm
                physical_target_y_mm = physical_origin.y_mm + target_y_mm - logical_origin_y_mm
                logger.info(
                    (
                        "Continuous scan point %s/%s: logical target x=%.3f mm, y=%.3f mm "
                        "(physical x=%.3f mm, y=%.3f mm) at %.3f mm/s."
                    ),
                    index,
                    total,
                    target_x_mm,
                    target_y_mm,
                    physical_target_x_mm,
                    physical_target_y_mm,
                    speed_mm_s,
                )

                for axis_name, logical_axis_target_mm in self._scan_axis_moves(
                    logical_x_mm,
                    logical_y_mm,
                    target_x_mm,
                    target_y_mm,
                ):
                    physical_axis_target_mm = (
                        physical_target_y_mm if axis_name.strip().upper() == "Y" else physical_target_x_mm
                    )
                    active_axis_name, active_direction = self._jog_positioner_axis_until(
                        axis_name=axis_name,
                        target_position_mm=physical_axis_target_mm,
                        speed_mm_s=speed_mm_s,
                        active_axis_name=active_axis_name,
                        active_direction=active_direction,
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

                next_motion = self._next_continuous_motion(point_list, index - 1, target_x_mm, target_y_mm)
                if self._should_stop_before_continuous_sample(active_axis_name, active_direction, next_motion):
                    self._stop_positioner_axis_by_name_quietly(active_axis_name)
                    active_axis_name = None
                    active_direction = 0

                if on_progress is not None:
                    on_progress(index, total, None)
                if not self._resume_event.is_set() and active_axis_name is not None:
                    self._stop_positioner_axis_by_name_quietly(active_axis_name)
                    active_axis_name = None
                    active_direction = 0
                self._scan_checkpoint()
                trace = self._measure_scan_trace(settings)
                if not self._resume_event.is_set() and active_axis_name is not None:
                    self._stop_positioner_axis_by_name_quietly(active_axis_name)
                    active_axis_name = None
                    active_direction = 0
                    self._scan_checkpoint()
                self._save_trace_csv(
                    trace,
                    position_mm=(target_x_mm, target_y_mm),
                    scan_mode="continuous",
                    file_flag=str(settings.get("file_flag", "")),
                    filename_tag=self._probe_offset_filename_tag(settings),
                    point_index=index,
                    output_dir=self._scan_output_dir(settings),
                )
                results.append(trace)
                if on_progress is not None:
                    on_progress(index, total, trace)
                logical_x_mm = target_x_mm
                logical_y_mm = target_y_mm
        except InstrumentServiceError:
            self._stop_positioner_quietly()
            if self._stop_event.is_set():
                logger.info("Continuous scan stopped by user request.")
                return results
            raise
        except Exception as exc:
            self._stop_positioner_quietly()
            if self._stop_event.is_set():
                logger.info("Continuous scan stopped by user request: %s", exc)
                return results
            raise InstrumentServiceError(f"匀速扫描失败，扫描架已停机：{exc}") from exc
        finally:
            if active_axis_name is not None:
                self._stop_positioner_axis_by_name_quietly(active_axis_name)

        return results

    def _configure_vna_for_scan(self, settings: dict) -> None:
        assert self._vna is not None
        start_hz = float(settings["start_ghz"]) * 1e9
        stop_hz = float(settings["stop_ghz"]) * 1e9
        self._select_switch_box_path(str(settings["parameter"]))
        self._vna.configure_power(float(settings["vna_power_dbm"]))
        self._configure_vna_if_bandwidth(float(settings.get("if_bandwidth_hz", 1000.0)))
        self._vna.configure_sweep(start_hz, stop_hz, int(settings["points"]))

    def _configure_vna_if_bandwidth(self, bandwidth_hz: float) -> None:
        assert self._vna is not None
        configure_if_bandwidth = getattr(self._vna, "configure_if_bandwidth", None)
        if callable(configure_if_bandwidth):
            configure_if_bandwidth(float(bandwidth_hz))

    def _measure_scan_trace(self, settings: dict) -> SParameterTrace:
        self._raise_if_stopped()
        assert self._vna is not None
        try:
            trace = self._vna.measure_s_parameter(str(settings["parameter"]))
        except Exception as exc:
            if self._stop_event.is_set():
                raise InstrumentServiceError("扫描流程已停止。") from exc
            raise InstrumentServiceError(f"网分读取失败，扫描架已停机：{exc}") from exc
        self._raise_if_stopped()
        if trace.frequency_hz.size == 0 or trace.complex_values.size == 0:
            raise InstrumentServiceError("网分未返回有效数据，扫描架已停机。")
        return trace

    def _save_trace_csv(
        self,
        trace: SParameterTrace,
        position_mm: tuple[float, float] | None,
        scan_mode: str,
        file_flag: str = "",
        filename_tag: str = "",
        point_index: int | None = None,
        output_dir: Path | None = None,
    ) -> Path:
        timestamp = datetime.now()
        timestamp_text = timestamp.strftime("%Y%m%d_%H%M%S_%f")
        x_text, y_text = self._position_filename_parts(position_mm)
        flag_text = self._safe_filename_part(file_flag) or "NOFLAG"
        tag_text = self._safe_filename_part(filename_tag)
        mode_text = self._safe_filename_part(scan_mode) or "test"
        parameter_text = self._safe_filename_part(trace.parameter) or "S"
        point_text = f"_P{point_index:04d}" if point_index is not None else ""
        tag_part = f"_{tag_text}" if tag_text else ""
        filename = (
            f"{flag_text}{tag_part}_{x_text}_{y_text}_{timestamp_text}_{mode_text}_{parameter_text}{point_text}.csv"
        )

        should_write_index = output_dir is not None
        output_dir = output_dir or Path.cwd() / "test_results"
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / filename
            x_mm = "" if position_mm is None else f"{position_mm[0]:.6f}"
            y_mm = "" if position_mm is None else f"{position_mm[1]:.6f}"
            with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(
                    [
                        "timestamp",
                        "flag",
                        "scan_mode",
                        "point_index",
                        "x_mm",
                        "y_mm",
                        "parameter",
                        "frequency_hz",
                        "real",
                        "imag",
                        "magnitude_db",
                        "phase_deg",
                    ]
                )
                for frequency_hz, value, magnitude_db, phase_deg in zip(
                    trace.frequency_hz,
                    trace.complex_values,
                    trace.magnitude_db,
                    trace.phase_deg,
                ):
                    writer.writerow(
                        [
                            timestamp.isoformat(timespec="microseconds"),
                            file_flag,
                            scan_mode,
                            "" if point_index is None else point_index,
                            x_mm,
                            y_mm,
                            trace.parameter,
                            f"{float(frequency_hz):.12g}",
                            f"{float(value.real):.12g}",
                            f"{float(value.imag):.12g}",
                            f"{float(magnitude_db):.12g}",
                            f"{float(phase_deg):.12g}",
                        ]
                    )
            if should_write_index:
                self._append_trace_index(
                    output_dir=output_dir,
                    trace_path=path,
                    timestamp=timestamp,
                    trace=trace,
                    position_mm=position_mm,
                    scan_mode=scan_mode,
                    file_flag=file_flag,
                    point_index=point_index,
                )
        except Exception as exc:
            logger.exception("Failed to save VNA trace CSV.")
            raise InstrumentServiceError(f"测试数据保存失败：{exc}") from exc

        logger.info("Saved VNA trace CSV: %s", path)
        return path

    def _create_scan_output_dir(self, settings: dict, scan_mode: str) -> Path:
        timestamp = datetime.now()
        timestamp_text = timestamp.strftime("%Y%m%d_%H%M%S")
        flag_text = self._safe_filename_part(str(settings.get("file_flag", ""))) or "NOFLAG"
        probe_text = self._safe_filename_part(self._probe_offset_filename_tag(settings))
        mode_text = self._safe_filename_part(scan_mode) or "scan"
        parameter_text = self._safe_filename_part(str(settings.get("parameter", ""))) or "S"
        probe_part = f"_{probe_text}" if probe_text else ""
        folder_name = f"{timestamp_text}_{flag_text}{probe_part}_{mode_text}_{parameter_text}"

        root_dir = Path.cwd() / "test_results"
        output_dir = root_dir / folder_name
        suffix = 1
        while output_dir.exists():
            suffix += 1
            output_dir = root_dir / f"{folder_name}_{suffix:02d}"

        output_dir.mkdir(parents=True, exist_ok=False)
        self._last_scan_output_dir = output_dir
        self._write_scan_metadata(output_dir, settings, scan_mode, timestamp)
        self._write_trace_index_header(output_dir)
        logger.info("Created scan output directory: %s", output_dir)
        return output_dir

    def _write_scan_metadata(
        self,
        output_dir: Path,
        settings: dict,
        scan_mode: str,
        timestamp: datetime,
    ) -> None:
        volume = self._build_scan_volume(settings)
        connection_config = settings.get("connection_config")
        metadata = {
            "created_at": timestamp.isoformat(timespec="seconds"),
            "scan_mode": scan_mode,
            "file_flag": str(settings.get("file_flag", "")),
            "parameter": str(settings.get("parameter", "")),
            "frequency": {
                "start_ghz": float(settings.get("start_ghz", 0.0)),
                "stop_ghz": float(settings.get("stop_ghz", 0.0)),
                "points": int(settings.get("points", 0)),
                "if_bandwidth_hz": float(settings.get("if_bandwidth_hz", 0.0)),
                "vna_power_dbm": float(settings.get("vna_power_dbm", 0.0)),
            },
            "scan_volume": {
                "x_start_mm": volume.x_start_mm,
                "x_stop_mm": volume.x_stop_mm,
                "y_start_mm": volume.y_start_mm,
                "y_stop_mm": volume.y_stop_mm,
                "step_x_mm": volume.step_x_mm,
                "step_y_mm": volume.step_y_mm,
                "point_count": volume.point_count,
            },
            "motion": {
                "step_speed_mm_s": float(settings.get("step_speed_mm_s", 0.0)),
                "continuous_speed_mm_s": float(settings.get("continuous_speed_mm_s", 0.0)),
                "settle_delay_s": float(settings.get("settle_delay_s", 0.0)),
            },
            "connection": self._metadata_safe_value(connection_config),
        }
        (output_dir / "scan_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_trace_index_header(self, output_dir: Path) -> None:
        with (output_dir / "trace_index.csv").open("w", newline="", encoding="utf-8-sig") as index_file:
            writer = csv.writer(index_file)
            writer.writerow(
                [
                    "saved_at",
                    "flag",
                    "scan_mode",
                    "point_index",
                    "x_mm",
                    "y_mm",
                    "parameter",
                    "frequency_start_hz",
                    "frequency_stop_hz",
                    "frequency_points",
                    "filename",
                ]
            )

    def _append_trace_index(
        self,
        output_dir: Path,
        trace_path: Path,
        timestamp: datetime,
        trace: SParameterTrace,
        position_mm: tuple[float, float] | None,
        scan_mode: str,
        file_flag: str,
        point_index: int | None,
    ) -> None:
        index_path = output_dir / "trace_index.csv"
        if not index_path.exists():
            self._write_trace_index_header(output_dir)

        x_mm = "" if position_mm is None else f"{position_mm[0]:.6f}"
        y_mm = "" if position_mm is None else f"{position_mm[1]:.6f}"
        with index_path.open("a", newline="", encoding="utf-8-sig") as index_file:
            writer = csv.writer(index_file)
            writer.writerow(
                [
                    timestamp.isoformat(timespec="microseconds"),
                    file_flag,
                    scan_mode,
                    "" if point_index is None else point_index,
                    x_mm,
                    y_mm,
                    trace.parameter,
                    f"{float(trace.frequency_hz[0]):.12g}",
                    f"{float(trace.frequency_hz[-1]):.12g}",
                    int(trace.frequency_hz.size),
                    trace_path.name,
                ]
            )

    @staticmethod
    def _scan_output_dir(settings: dict) -> Path | None:
        value = settings.get("scan_output_dir")
        if not value:
            return None
        return Path(str(value))

    @staticmethod
    def _probe_offset_filename_tag(settings: dict) -> str:
        if "probe_x_offset_mm" not in settings and "probe_y_offset_mm" not in settings:
            return ""

        preset = str(settings.get("probe_offset_preset", "")).strip() or "custom"
        x_offset_mm = float(settings.get("probe_x_offset_mm", 0.0))
        y_offset_mm = float(settings.get("probe_y_offset_mm", 0.0))
        return f"probe_{preset}_X{x_offset_mm:+.3f}_Y{y_offset_mm:+.3f}"

    @staticmethod
    def _metadata_safe_value(value):
        try:
            json.dumps(value)
        except TypeError:
            return str(value)
        return value

    def _current_position_tuple(self) -> tuple[float, float] | None:
        if not self.is_positioner_connected or self._positioner is None:
            return None
        try:
            position = self._positioner.position
        except Exception:
            logger.exception("Failed to query position for trace filename.")
            return None
        return position.x_mm, position.y_mm

    @staticmethod
    def _position_filename_parts(position_mm: tuple[float, float] | None) -> tuple[str, str]:
        if position_mm is None:
            return "Xunknown", "Yunknown"
        return f"X{position_mm[0]:.3f}", f"Y{position_mm[1]:.3f}"

    @staticmethod
    def _safe_filename_part(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        invalid = '<>:"/\\|?*'
        cleaned = "".join("_" if char in invalid or char.isspace() else char for char in text)
        cleaned = cleaned.strip("._")
        return cleaned[:80]

    @staticmethod
    def _build_scan_volume(settings: dict) -> ScanVolume:
        return ScanVolume(
            x_start_mm=float(settings["x_start_mm"]),
            x_stop_mm=float(settings["x_stop_mm"]),
            y_start_mm=float(settings["y_start_mm"]),
            y_stop_mm=float(settings["y_stop_mm"]),
            step_x_mm=float(settings["step_x_mm"]),
            step_y_mm=float(settings["step_y_mm"]),
        )

    def _scan_axis_moves(
        self,
        logical_x_mm: float | None,
        logical_y_mm: float | None,
        target_x_mm: float,
        target_y_mm: float,
    ) -> list[tuple[str, float]]:
        if logical_x_mm is None or logical_y_mm is None:
            return [("Y", target_y_mm), ("X", target_x_mm)]

        moves: list[tuple[str, float]] = []
        if not self._positions_match(logical_y_mm, target_y_mm):
            moves.append(("Y", target_y_mm))
        if not self._positions_match(logical_x_mm, target_x_mm):
            moves.append(("X", target_x_mm))
        return moves

    def _move_positioner_axis_to(self, axis_name: str, position_mm: float, speed_mm_s: float) -> Position:
        assert self._positioner is not None
        axis = self._axis_for_name(axis_name)
        move_axis_to = getattr(self._positioner, "move_axis_to", None)
        if callable(move_axis_to):
            return move_axis_to(axis, position_mm, speed_mm_s)

        current = self._positioner.position
        if axis_name.strip().upper() == "Y":
            return self._positioner.move_to(current.x_mm, position_mm, speed_mm_s)
        return self._positioner.move_to(position_mm, current.y_mm, speed_mm_s)

    def _jog_positioner_axis_until(
        self,
        axis_name: str,
        target_position_mm: float,
        speed_mm_s: float,
        active_axis_name: str | None,
        active_direction: int,
    ) -> tuple[str | None, int]:
        assert self._positioner is not None
        normalized_axis_name = self._normalize_axis_name(axis_name)
        axis = self._axis_for_name(normalized_axis_name)
        speed = max(abs(speed_mm_s), 0.001)
        tolerance_mm = self._position_tolerance_for_axis(axis)

        position = self._positioner.position
        current_position_mm = self._position_for_axis_name(position, normalized_axis_name)
        if (
            active_axis_name is not None
            and self._normalize_axis_name(active_axis_name) == normalized_axis_name
            and active_direction != 0
            and self._target_crossed(current_position_mm, target_position_mm, active_direction, tolerance_mm)
        ):
            return active_axis_name, active_direction

        distance_mm = target_position_mm - current_position_mm
        if abs(distance_mm) <= tolerance_mm:
            return active_axis_name, active_direction

        direction = 1 if distance_mm > 0 else -1
        if active_axis_name is not None and (
            self._normalize_axis_name(active_axis_name) != normalized_axis_name
            or active_direction != direction
        ):
            self._stop_positioner_axis_by_name_quietly(active_axis_name)
            active_axis_name = None
            active_direction = 0
            position = self._positioner.position
            current_position_mm = self._position_for_axis_name(position, normalized_axis_name)
            distance_mm = target_position_mm - current_position_mm
            if abs(distance_mm) <= tolerance_mm:
                return None, 0
            direction = 1 if distance_mm > 0 else -1

        if active_axis_name is None:
            self._positioner.jog_axis(axis, speed * direction)
            active_axis_name = normalized_axis_name
            active_direction = direction

        while True:
            if not self._resume_event.is_set():
                self._stop_positioner_axis_by_name_quietly(active_axis_name)
                active_axis_name = None
                active_direction = 0
                self._wait_if_paused()
                position = self._positioner.position
                current_position_mm = self._position_for_axis_name(position, normalized_axis_name)
                if self._target_crossed(current_position_mm, target_position_mm, direction, tolerance_mm):
                    return active_axis_name, active_direction
                if active_axis_name is None:
                    self._positioner.jog_axis(axis, speed * direction)
                    active_axis_name = normalized_axis_name
                    active_direction = direction

            self._raise_if_stopped()
            position = self._positioner.position
            current_position_mm = self._position_for_axis_name(position, normalized_axis_name)
            if self._target_crossed(current_position_mm, target_position_mm, direction, tolerance_mm):
                return active_axis_name, active_direction
            time.sleep(0.03)

    def _next_continuous_motion(
        self,
        point_list: list[tuple[float, float]],
        current_index: int,
        current_x_mm: float,
        current_y_mm: float,
    ) -> tuple[str, int] | None:
        if current_index + 1 >= len(point_list):
            return None

        next_x_mm, next_y_mm = point_list[current_index + 1]
        moves = self._scan_axis_moves(current_x_mm, current_y_mm, next_x_mm, next_y_mm)
        if not moves:
            return None

        axis_name, target_mm = moves[0]
        current_axis_mm = current_y_mm if axis_name.strip().upper() == "Y" else current_x_mm
        delta_mm = target_mm - current_axis_mm
        if abs(delta_mm) <= 1e-9:
            return None
        return self._normalize_axis_name(axis_name), 1 if delta_mm > 0 else -1

    def _should_stop_before_continuous_sample(
        self,
        active_axis_name: str | None,
        active_direction: int,
        next_motion: tuple[str, int] | None,
    ) -> bool:
        if active_axis_name is None:
            return False
        if next_motion is None:
            return True
        next_axis_name, next_direction = next_motion
        return self._normalize_axis_name(active_axis_name) != next_axis_name or active_direction != next_direction

    def _stop_positioner_axis_by_name_quietly(self, axis_name: str | None) -> None:
        if axis_name is None or not self.is_positioner_connected or self._positioner is None:
            return
        try:
            self._positioner.stop_axis(self._axis_for_name(axis_name))
        except Exception:
            logger.exception("Failed to stop positioner axis %s.", axis_name)

    def _positioner_timeout_ms(self) -> int:
        config = getattr(self._positioner, "_config", None)
        return max(int(getattr(config, "timeout_ms", 1000)), 1000)

    def _position_tolerance_for_axis(self, axis: int) -> float:
        tolerance = getattr(self._positioner, "_position_tolerance_mm", None)
        if callable(tolerance):
            try:
                return max(float(tolerance(axis)), 0.001)
            except Exception:
                logger.debug("Positioner-specific tolerance lookup failed.", exc_info=True)
        return 0.05

    @staticmethod
    def _position_for_axis_name(position: Position, axis_name: str) -> float:
        return position.y_mm if axis_name.strip().upper() == "Y" else position.x_mm

    @staticmethod
    def _target_crossed(
        current_position_mm: float,
        target_position_mm: float,
        direction: int,
        tolerance_mm: float,
    ) -> bool:
        if direction > 0:
            return current_position_mm >= target_position_mm - tolerance_mm
        return current_position_mm <= target_position_mm + tolerance_mm

    @staticmethod
    def _normalize_axis_name(axis_name: str) -> str:
        return "Y" if axis_name.strip().upper() == "Y" else "X"

    def _axis_for_name(self, axis_name: str) -> int:
        config = getattr(self._positioner, "_config", None)
        if axis_name.strip().upper() == "Y":
            return int(getattr(config, "y_axis", 3))
        return int(getattr(config, "x_axis", 2))

    @staticmethod
    def _positions_match(left_mm: float, right_mm: float) -> bool:
        return abs(left_mm - right_mm) <= 1e-9

    def _sleep_interruptibly(self, duration_s: float) -> None:
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            self._raise_if_stopped()
            self._wait_if_paused()
            time.sleep(min(0.05, max(deadline - time.monotonic(), 0.0)))

    def _scan_checkpoint(self) -> None:
        self._raise_if_stopped()
        self._wait_if_paused()
        self._raise_if_stopped()

    def _wait_if_paused(self) -> None:
        if self._resume_event.is_set():
            return

        logger.info("Scan paused; waiting for resume.")
        while not self._resume_event.wait(0.1):
            self._raise_if_stopped()
        logger.info("Scan resumed.")

    def _raise_if_stopped(self) -> None:
        if self._stop_event.is_set():
            raise InstrumentServiceError("扫描流程已停止。")

    def _controller_for_name(self, name: str):
        if name == "vna":
            return self._vna
        if name == "positioner":
            return self._positioner
        if name == "switch_box":
            return self._switch_box
        raise InstrumentServiceError(f"未知仪器类型：{name}")

    @staticmethod
    def _create_vna_controller(config: dict) -> VnaController:
        if InstrumentService._virtual_enabled(config):
            return MockVnaController(timeout_ms=int(config.get("timeout_ms", 5000)))

        ip_address = str(config.get("ip_address", "")).strip()
        port = int(config.get("port", 5025))
        if ip_address:
            resource_name = f"TCPIP0::{ip_address}::{port}::SOCKET"
        else:
            resource_name = str(config.get("resource_name", "")).strip()

        if not resource_name:
            raise InstrumentServiceError("VNA VISA 资源不能为空，真实测试模式需要填写仪器资源。")
        if resource_name.upper().startswith("MOCK"):
            raise InstrumentServiceError("当前为真实测试模式，VNA 不能使用 MOCK 资源。")

        return ScpiVnaController(
            VnaScpiConfig(
                resource_name=resource_name,
                timeout_ms=int(config.get("timeout_ms", 5000)),
                retries=int(config.get("retries", 2)),
                retry_delay_s=float(config.get("retry_delay_s", 0.2)),
            )
        )

    @staticmethod
    def _create_positioner_controller(config: dict) -> PositionerController:
        if InstrumentService._virtual_enabled(config):
            return MockPositionerController(
                x_axis=InstrumentService._axis_from_config(config, "x_axis", 2),
                y_axis=InstrumentService._axis_from_config(config, "y_axis", 3),
            )

        port_name = str(config.get("port_name") or config.get("resource_name") or "").strip()
        if not port_name:
            raise InstrumentServiceError("扫描架串口不能为空，真实测试模式需要填写 COM 口。")
        if port_name.upper().startswith("MOCK"):
            raise InstrumentServiceError("当前为真实测试模式，扫描架不能使用 MOCK 资源。")

        legacy_pulses_per_mm, x_pulses_per_mm, y_pulses_per_mm = (
            InstrumentService._positioner_scales_from_config(config)
        )

        return IclPositionerController(
            IclPositionerConfig(
                port=port_name,
                baudrate=int(config.get("baudrate", 115200)),
                bytesize=int(config.get("bytesize", 8)),
                parity=str(config.get("parity", "N")).strip().upper() or "N",
                stopbits=int(config.get("stopbits", 1)),
                timeout_ms=int(config.get("timeout_ms", 1000)),
                retries=int(config.get("retries", 2)),
                retry_delay_s=float(config.get("retry_delay_s", 0.05)),
                x_axis=InstrumentService._axis_from_config(config, "x_axis", 2),
                y_axis=InstrumentService._axis_from_config(config, "y_axis", 3),
                pulses_per_mm=legacy_pulses_per_mm,
                x_pulses_per_mm=x_pulses_per_mm,
                y_pulses_per_mm=y_pulses_per_mm,
                default_speed=float(config.get("default_speed", 100.0)),
            )
        )

    @staticmethod
    def _positioner_scales_from_config(config: dict) -> tuple[float, float, float]:
        legacy_pulses_per_mm = float(config.get("pulses_per_mm", config.get("pulses_per_degree", 1.0)))
        x_pulses_per_mm = InstrumentService._axis_scale_from_config(
            config,
            "x_pulses_per_mm",
            "x_units_per_turn",
            "x_mm_per_turn",
            legacy_pulses_per_mm,
        )
        y_pulses_per_mm = InstrumentService._axis_scale_from_config(
            config,
            "y_pulses_per_mm",
            "y_units_per_turn",
            "y_mm_per_turn",
            legacy_pulses_per_mm,
        )
        legacy_pulses_per_mm = x_pulses_per_mm
        if legacy_pulses_per_mm <= 0 or x_pulses_per_mm <= 0 or y_pulses_per_mm <= 0:
            raise InstrumentServiceError("扫描架每毫米电机单位必须大于 0。")
        return legacy_pulses_per_mm, x_pulses_per_mm, y_pulses_per_mm

    @staticmethod
    def _axis_scale_from_config(
        config: dict,
        direct_key: str,
        units_per_turn_key: str,
        mm_per_turn_key: str,
        fallback: float,
    ) -> float:
        if units_per_turn_key in config and mm_per_turn_key in config:
            units_per_turn = float(config[units_per_turn_key])
            mm_per_turn = float(config[mm_per_turn_key])
            if mm_per_turn <= 0:
                raise InstrumentServiceError("扫描架每圈距离必须大于 0。")
            return units_per_turn / mm_per_turn
        return float(config.get(direct_key, fallback))

    @staticmethod
    def _create_switch_box_controller(config: dict) -> SwitchBoxController:
        if InstrumentService._virtual_enabled(config):
            return MockSwitchBoxController()

        model = str(config.get("model", "LCD74000F")).strip().upper()
        connection_type = str(config.get("connection_type", "TCP/IP")).strip() or "TCP/IP"
        normalized_type = connection_type.upper()
        if normalized_type in {"SERIAL", "串口", "RS232", "RS485"}:
            serial_port = str(config.get("serial_port") or config.get("port_name") or "").strip()
            if not serial_port:
                raise InstrumentServiceError("开关箱串口不能为空，串口模式需要填写 COM 口。")
            if serial_port.upper().startswith("MOCK"):
                raise InstrumentServiceError("当前为真实测试模式，开关箱不能使用 MOCK 资源。")
        else:
            ip_address = str(config.get("ip_address", "")).strip()
            if not ip_address:
                raise InstrumentServiceError("开关箱 TCP/IP 地址不能为空。")
            serial_port = str(config.get("serial_port", "COM3")).strip()

        if model == "LCD74000F":
            return Lcd74000fSwitchBoxController(
                Lcd74000fSwitchBoxConfig(
                    connection_type=connection_type,
                    ip_address=str(config.get("ip_address", "192.168.1.113")).strip(),
                    tcp_port=int(config.get("tcp_port", config.get("port", 7))),
                    serial_port=serial_port,
                    baudrate=int(config.get("baudrate", 115200)),
                    timeout_ms=int(config.get("timeout_ms", 2000)),
                    command_terminator=str(config.get("command_terminator", "\n")),
                    identify_command=str(config.get("identify_command", "*IDN?")).strip(),
                    s11_command=str(config.get("s11_command", "CONFigure:LINK H,VNA1")).strip(),
                    s21_command=str(config.get("s21_command", "CONFigure:LINK H,VNA1")).strip(),
                    s12_command=str(config.get("s12_command", "CONFigure:LINK V,VNA1")).strip(),
                    s22_command=str(config.get("s22_command", "CONFigure:LINK V,VNA1")).strip(),
                    retries=int(config.get("retries", 1)),
                    retry_delay_s=float(config.get("retry_delay_s", 0.2)),
                )
            )

        return Tc500SwitchBoxController(
            Tc500SwitchBoxConfig(
                connection_type=connection_type,
                ip_address=str(config.get("ip_address", "192.168.1.120")).strip(),
                tcp_port=int(config.get("tcp_port", config.get("port", 35))),
                serial_port=serial_port,
                baudrate=int(config.get("baudrate", 115200)),
                timeout_ms=int(config.get("timeout_ms", 1500)),
                command_terminator=str(config.get("command_terminator", "\r\n")),
                identify_command=str(config.get("identify_command", "PASSIVE")).strip().upper(),
                s11_command=str(config.get("s11_command", "PASSIVE")).strip().upper(),
                s21_command=str(config.get("s21_command", "PASSIVE")).strip().upper(),
                s12_command=str(config.get("s12_command", "PASSIVE")).strip().upper(),
                s22_command=str(config.get("s22_command", "PASSIVE")).strip().upper(),
                retries=int(config.get("retries", 1)),
                retry_delay_s=float(config.get("retry_delay_s", 0.2)),
            )
        )

    @staticmethod
    def _axis_from_config(config: dict, key: str, default_axis_id: int) -> int:
        raw_value = int(config.get(key, default_axis_id))
        if 0 <= raw_value <= 247:
            return raw_value
        raise InstrumentServiceError(f"扫描架轴号超出范围：{key}={raw_value}，有效范围为 0-247。")

    @staticmethod
    def _virtual_enabled(config: dict) -> bool:
        value = config.get("virtual_enabled", False)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on", "虚拟连接", "虚拟"}
        return bool(value)

    def _stop_positioner_quietly(self) -> None:
        if not self.is_positioner_connected or self._positioner is None:
            return
        try:
            self._positioner.stop_all()
        except Exception:
            logger.exception("Failed to stop positioner.")
