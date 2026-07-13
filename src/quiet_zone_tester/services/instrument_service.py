from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Event, Lock

from quiet_zone_tester.domains.acquisition import AcquisitionService, AcquisitionServiceError
from quiet_zone_tester.domains.data_management import TraceStorage
from quiet_zone_tester.domains.instrument_management import (
    InstrumentConnectionService,
    InstrumentConnectionServiceError,
    InstrumentControllerFactory,
    InstrumentControllerFactoryError,
    InstrumentConnectionConfig,
    PositionerConnectionConfig,
    SwitchBoxConnectionConfig,
    VnaConnectionConfig,
)
from quiet_zone_tester.domains.link_management import LinkService, LinkServiceError
from quiet_zone_tester.domains.motion_control import MotionService, MotionServiceError
from quiet_zone_tester.domains.scan_management import (
    ScanRuntimeService,
    ScanRuntimeServiceError,
    ScanSettings,
)
from quiet_zone_tester.hardware import (
    InstrumentInfo,
    Position,
    PositionerController,
    SwitchBoxController,
    VnaController,
)
from quiet_zone_tester.models import ScanVolume
from quiet_zone_tester.models import SParameterTrace

logger = logging.getLogger(__name__)


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
        self._trace_storage = TraceStorage()

    @property
    def last_scan_output_dir(self) -> Path | None:
        return self._last_scan_output_dir

    def connect_all(self, config: dict | InstrumentConnectionConfig | None = None) -> list[InstrumentInfo]:
        connection_config = self._connection_config_from(config)
        logger.info("Connecting instrument set with config: %s", connection_config.to_dict())
        try:
            vna_info = self.connect_vna(connection_config.vna)
            positioner_info = self.connect_positioner(connection_config.positioner)
            switch_box_info = self.connect_switch_box(connection_config.switch_box)
        except Exception as exc:
            logger.exception("Instrument connection failed; cleaning up partial connections.")
            self._cleanup_after_failed_connect()
            if isinstance(exc, InstrumentServiceError):
                raise
            raise InstrumentServiceError(f"仪器连接失败：{exc}") from exc
        return [vna_info, positioner_info, switch_box_info]

    def connect_vna(self, config: dict | InstrumentConnectionConfig | VnaConnectionConfig | None = None) -> InstrumentInfo:
        vna_config = self._vna_config_dict(config)
        logger.info("Connecting VNA with config: %s", vna_config)
        try:
            self._configure_vna_backend(vna_config)
            if self._vna is None:
                raise InstrumentServiceError("VNA controller is not configured.")
            return InstrumentConnectionService().connect_controller(self._vna, "VNA")
        except Exception as exc:
            logger.exception("VNA connection failed.")
            self._cleanup_controller("vna")
            if isinstance(exc, InstrumentServiceError):
                raise
            raise InstrumentServiceError(f"VNA 连接失败：{exc}") from exc

    def connect_positioner(
        self,
        config: dict | InstrumentConnectionConfig | PositionerConnectionConfig | None = None,
    ) -> InstrumentInfo:
        positioner_config = self._positioner_config_dict(config)
        logger.info("Connecting positioner with config: %s", positioner_config)
        try:
            self._configure_positioner_backend(positioner_config)
            if self._positioner is None:
                raise InstrumentServiceError("Positioner controller is not configured.")
            return InstrumentConnectionService().connect_controller(self._positioner, "Positioner")
        except Exception as exc:
            logger.exception("Positioner connection failed.")
            self._cleanup_controller("positioner")
            if isinstance(exc, InstrumentServiceError):
                raise
            raise InstrumentServiceError(f"扫描架连接失败：{exc}") from exc

    def connect_switch_box(
        self,
        config: dict | InstrumentConnectionConfig | SwitchBoxConnectionConfig | None = None,
    ) -> InstrumentInfo:
        switch_box_config = self._switch_box_config_dict(config)
        logger.info("Connecting switch box with config: %s", switch_box_config)
        try:
            self._configure_switch_box_backend(switch_box_config)
            if self._switch_box is None:
                raise InstrumentServiceError("Switch box controller is not configured.")
            return InstrumentConnectionService().connect_controller(self._switch_box, "Switch box")
        except Exception as exc:
            logger.exception("Switch box connection failed.")
            self._cleanup_controller("switch_box")
            if isinstance(exc, InstrumentServiceError):
                raise
            raise InstrumentServiceError(f"开关箱连接失败：{exc}") from exc

    def disconnect_all(self) -> None:
        self.request_stop_and_stop_positioner()
        logger.info("Disconnecting instrument set.")
        try:
            InstrumentConnectionService().disconnect_all([self._switch_box, self._positioner, self._vna])
        except InstrumentConnectionServiceError as exc:
            raise InstrumentServiceError(str(exc)) from exc

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
            self._motion_service().jog_axis(axis, speed_mm_s)
        except InstrumentServiceError:
            raise
        except MotionServiceError as exc:
            raise InstrumentServiceError(f"扫描架运动失败：{exc}") from exc
        except Exception as exc:
            logger.exception("Positioner jog failed.")
            raise InstrumentServiceError(f"扫描架运动失败：{exc}") from exc

    def query_positioner_position(self, config: dict | None = None) -> Position:
        if not self.is_positioner_connected or self._positioner is None:
            raise InstrumentServiceError("请先连接扫描架，再查询位置。")
        try:
            if config:
                self.update_positioner_runtime_config(config)
            return self._motion_service().query_position()
        except InstrumentServiceError:
            raise
        except MotionServiceError as exc:
            raise InstrumentServiceError(f"扫描架位置查询失败：{exc}") from exc
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
            return self._motion_service().move_absolute(x_mm, y_mm, speed_mm_s)
        except InstrumentServiceError:
            raise
        except MotionServiceError as exc:
            raise InstrumentServiceError(f"扫描架绝对定位失败：{exc}") from exc
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
            return self._motion_service().move_relative(delta_x_mm, delta_y_mm, speed_mm_s)
        except InstrumentServiceError:
            raise
        except MotionServiceError as exc:
            raise InstrumentServiceError(f"扫描架相对定位失败：{exc}") from exc
        except Exception as exc:
            logger.exception("Positioner relative move failed.")
            raise InstrumentServiceError(f"扫描架相对定位失败：{exc}") from exc

    def update_positioner_runtime_config(
        self,
        config: dict | InstrumentConnectionConfig | PositionerConnectionConfig | None = None,
    ) -> None:
        if not self.is_positioner_connected or self._positioner is None:
            raise InstrumentServiceError("请先连接扫描架，再更新扫描架配置。")

        positioner_config = self._positioner_config_dict(config)
        try:
            self._motion_service().update_runtime_config(positioner_config)
        except MotionServiceError as exc:
            raise InstrumentServiceError(f"扫描架配置更新失败：{exc}") from exc

    def stop_positioner_axis(self, axis: int) -> None:
        if not self.is_positioner_connected or self._positioner is None:
            raise InstrumentServiceError("请先连接扫描架，再停止运动。")
        try:
            self._motion_service().stop_axis(axis)
        except MotionServiceError as exc:
            raise InstrumentServiceError(f"扫描架停止失败：{exc}") from exc
        except Exception as exc:
            logger.exception("Positioner stop failed.")
            raise InstrumentServiceError(f"扫描架停止失败：{exc}") from exc

    def stop_positioner(self) -> None:
        if not self.is_positioner_connected or self._positioner is None:
            return
        try:
            self._motion_service().stop_all()
        except MotionServiceError as exc:
            raise InstrumentServiceError(f"扫描架停止失败：{exc}") from exc
        except Exception as exc:
            logger.exception("Positioner stop all failed.")
            raise InstrumentServiceError(f"扫描架停止失败：{exc}") from exc

    def request_stop(self) -> None:
        self._stop_event.set()
        self._resume_event.set()
        if self._positioner is None:
            return
        MotionService(self._positioner).cancel_motion_if_supported()

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
        polarization: str | None = None,
        vna_power_dbm: float = -10.0,
        if_bandwidth_hz: float = 1000.0,
        file_flag: str = "",
    ) -> SParameterTrace:
        self.verify_ready_for_test()

        try:
            self._select_switch_box_polarization_path(polarization)
            trace = self._acquisition_service().acquire_trace(
                start_ghz=start_ghz,
                stop_ghz=stop_ghz,
                points=points,
                parameter=parameter,
                power_dbm=vna_power_dbm,
                if_bandwidth_hz=if_bandwidth_hz,
            )
        except InstrumentServiceError:
            raise
        except AcquisitionServiceError as exc:
            raise InstrumentServiceError(f"网分采样失败：{exc}") from exc
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
            self._acquisition_service().configure_trace(
                start_ghz=start_ghz,
                stop_ghz=stop_ghz,
                points=points,
                parameter=parameter,
                power_dbm=vna_power_dbm,
                if_bandwidth_hz=if_bandwidth_hz,
            )
        except AcquisitionServiceError as exc:
            raise InstrumentServiceError(f"网分仪配置失败：{exc}") from exc
        except Exception as exc:
            logger.exception("VNA standalone configuration failed.")
            raise InstrumentServiceError(f"网分仪配置失败：{exc}") from exc

    def sample_vna_trace(self, parameter: str, file_flag: str = "") -> SParameterTrace:
        if not self.is_vna_connected or self._vna is None:
            raise InstrumentServiceError("请先连接网分仪，再执行采样。")

        try:
            trace = self._acquisition_service().sample_trace(parameter)
            self._save_trace_csv(
                trace,
                position_mm=self._current_position_tuple(),
                scan_mode="standalone",
                file_flag=file_flag,
            )
            return trace
        except InstrumentServiceError:
            raise
        except AcquisitionServiceError as exc:
            raise InstrumentServiceError(f"网分仪采样失败：{exc}") from exc
        except Exception as exc:
            logger.exception("VNA standalone sample failed.")
            raise InstrumentServiceError(f"网分仪采样失败：{exc}") from exc

    def run_scan(
        self,
        settings: dict | ScanSettings,
        on_progress: Callable[[int, int, SParameterTrace | None], None] | None = None,
    ) -> list[SParameterTrace]:
        if not self._scan_lock.acquire(blocking=False):
            raise InstrumentServiceError("已有扫描流程正在运行，请等待当前流程结束后再开始。")

        try:
            settings = self._scan_settings_dict(settings)
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
        try:
            InstrumentConnectionService().disconnect_controller(controller, name)
        except InstrumentConnectionServiceError as exc:
            raise InstrumentServiceError(f"{name} 断开失败：{exc}") from exc

    def _cleanup_controller(self, name: str) -> None:
        controller = self._controller_for_name(name)
        InstrumentConnectionService().cleanup_controller(controller, name)

        if name == "vna" and not self._external_vna:
            self._vna = None
        elif name == "positioner" and not self._external_positioner:
            self._positioner = None
        elif name == "switch_box" and not self._external_switch_box:
            self._switch_box = None

    def _cleanup_after_failed_connect(self) -> None:
        InstrumentConnectionService().cleanup_after_failed_connect([self._switch_box, self._positioner, self._vna])

        if not self._external_vna:
            self._vna = None
        if not self._external_positioner:
            self._positioner = None
        if not self._external_switch_box:
            self._switch_box = None

    def _select_switch_box_path(self, parameter: str) -> None:
        self.verify_ready_for_test()
        self.select_switch_box_parameter(parameter)

    def _select_switch_box_polarization_path(self, polarization: str | None) -> None:
        self.verify_ready_for_test()
        self.select_switch_box_polarization(polarization)

    def select_switch_box_parameter(self, parameter: str) -> str:
        """Deprecated compatibility route; S parameters should only drive VNA measurement."""
        if not self.is_switch_box_connected or self._switch_box is None:
            raise InstrumentServiceError("请先连接开关箱，再切换链路。")

        try:
            return LinkService(self._switch_box).select_s_parameter(parameter)
        except (LinkServiceError, ValueError) as exc:
            raise InstrumentServiceError(f"开关箱切换失败：{exc}") from exc

    def select_switch_box_polarization(self, polarization: str | None) -> str:
        if not self.is_switch_box_connected or self._switch_box is None:
            raise InstrumentServiceError("请先连接开关箱，再切换链路。")

        try:
            return LinkService(self._switch_box).select_polarization(polarization)
        except LinkServiceError as exc:
            raise InstrumentServiceError(f"开关箱切换失败：{exc}") from exc

    def select_switch_box_dut_path(self, target: str) -> str:
        if not self.is_switch_box_connected or self._switch_box is None:
            raise InstrumentServiceError("请先连接开关箱，再切换链路。")

        try:
            return LinkService(self._switch_box).select_dut_path(target)
        except LinkServiceError as exc:
            raise InstrumentServiceError(f"DUT 链路切换失败：{exc}") from exc

    def send_switch_box_command(self, command: str) -> str:
        if not self.is_switch_box_connected or self._switch_box is None:
            raise InstrumentServiceError("请先连接开关箱，再发送命令。")

        try:
            return LinkService(self._switch_box).send_command(command)
        except LinkServiceError as exc:
            raise InstrumentServiceError(f"开关箱命令执行失败：{exc}") from exc

    def _run_step_scan(
        self,
        settings: dict,
        on_progress: Callable[[int, int, SParameterTrace | None], None] | None,
    ) -> list[SParameterTrace]:
        try:
            return self._scan_runtime_service().run_step_scan(settings, on_progress)
        except InstrumentServiceError as exc:
            self._stop_positioner_quietly()
            if self._stop_event.is_set() and self._is_user_stop_exception(exc):
                logger.info("Step scan stopped by user request.")
                return []
            raise
        except ScanRuntimeServiceError as exc:
            raise InstrumentServiceError(str(exc)) from exc

    def _run_continuous_scan(
        self,
        settings: dict,
        on_progress: Callable[[int, int, SParameterTrace | None], None] | None,
    ) -> list[SParameterTrace]:
        try:
            return self._scan_runtime_service().run_continuous_scan(settings, on_progress)
        except InstrumentServiceError as exc:
            self._stop_positioner_quietly()
            if self._stop_event.is_set() and self._is_user_stop_exception(exc):
                logger.info("Continuous scan stopped by user request.")
                return []
            raise
        except ScanRuntimeServiceError as exc:
            raise InstrumentServiceError(str(exc)) from exc

    def _configure_vna_for_scan(self, settings: dict) -> None:
        self._select_switch_box_polarization_path(settings.get("polarization"))
        try:
            self._acquisition_service().configure_for_scan(settings)
        except AcquisitionServiceError as exc:
            raise InstrumentServiceError(f"网分配置失败：{exc}") from exc

    def _configure_vna_if_bandwidth(self, bandwidth_hz: float) -> None:
        try:
            self._acquisition_service().configure_if_bandwidth(bandwidth_hz)
        except AcquisitionServiceError as exc:
            raise InstrumentServiceError(f"网分中频带宽配置失败：{exc}") from exc

    def _measure_scan_trace(self, settings: dict) -> SParameterTrace:
        try:
            trace = self._acquisition_service().sample_scan_trace(
                str(settings["parameter"]),
                stop_requested=self._stop_event.is_set,
            )
        except AcquisitionServiceError as exc:
            if self._stop_event.is_set():
                raise InstrumentServiceError("扫描流程已停止。") from exc
            raise InstrumentServiceError(f"网分读取失败，扫描架已停机：{exc}") from exc
        return trace

    def _acquisition_service(self) -> AcquisitionService:
        if self._vna is None:
            raise InstrumentServiceError("VNA controller is not configured.")
        return AcquisitionService(self._vna)

    def _motion_service(self) -> MotionService:
        if self._positioner is None:
            raise InstrumentServiceError("Positioner controller is not configured.")
        return MotionService(self._positioner)

    def _scan_runtime_service(self) -> ScanRuntimeService:
        return ScanRuntimeService(
            motion=self._motion_service(),
            configure_vna_for_scan=self._configure_vna_for_scan,
            measure_trace=self._measure_scan_trace,
            save_trace=self._save_trace_csv,
            checkpoint=self._scan_checkpoint,
            sleep_interruptibly=self._sleep_interruptibly,
            wait_if_paused=self._wait_if_paused,
            raise_if_stopped=self._raise_if_stopped,
            is_paused=lambda: not self._resume_event.is_set(),
            stop_requested=self._stop_event.is_set,
            stop_positioner_quietly=self._stop_positioner_quietly,
            probe_offset_filename_tag=self._probe_offset_filename_tag,
            scan_output_dir=self._scan_output_dir,
        )

    def _save_trace_csv(
        self,
        trace: SParameterTrace,
        position_mm: tuple[float, float] | None,
        scan_mode: str,
        file_flag: str = "",
        filename_tag: str = "",
        point_index: int | None = None,
        output_dir: Path | None = None,
        logical_position_mm: tuple[float, float] | None = None,
        physical_target_mm: tuple[float, float] | None = None,
        actual_position_mm: tuple[float, float] | None = None,
        position_error_mm: tuple[float, float] | None = None,
    ) -> Path:
        try:
            path = self._trace_storage.save_trace_csv(
                trace,
                position_mm=position_mm,
                scan_mode=scan_mode,
                file_flag=file_flag,
                filename_tag=filename_tag,
                point_index=point_index,
                output_dir=output_dir,
                logical_position_mm=logical_position_mm,
                physical_target_mm=physical_target_mm,
                actual_position_mm=actual_position_mm,
                position_error_mm=position_error_mm,
            )
        except Exception as exc:
            logger.exception("Failed to save VNA trace CSV.")
            raise InstrumentServiceError(f"测试数据保存失败：{exc}") from exc

        logger.info("Saved VNA trace CSV: %s", path)
        return path

    def _create_scan_output_dir(self, settings: dict, scan_mode: str) -> Path:
        timestamp = datetime.now()
        output_dir = self._trace_storage.create_scan_output_dir(
            settings=settings,
            scan_mode=scan_mode,
            timestamp=timestamp,
        )
        self._last_scan_output_dir = output_dir
        logger.info("Created scan output directory: %s", output_dir)
        return output_dir

    def _write_scan_metadata(
        self,
        output_dir: Path,
        settings: dict,
        scan_mode: str,
        timestamp: datetime,
    ) -> None:
        self._trace_storage.write_scan_metadata(output_dir, settings, scan_mode, timestamp)

    def _write_trace_index_header(self, output_dir: Path) -> None:
        self._trace_storage.write_trace_index_header(output_dir)

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
        self._trace_storage.append_trace_index(
            output_dir=output_dir,
            trace_path=trace_path,
            timestamp=timestamp,
            trace=trace,
            position_mm=position_mm,
            scan_mode=scan_mode,
            file_flag=file_flag,
            point_index=point_index,
        )

    @staticmethod
    def _scan_output_dir(settings: dict) -> Path | None:
        value = settings.get("scan_output_dir")
        if not value:
            return None
        return Path(str(value))

    @staticmethod
    def _probe_offset_filename_tag(settings: dict) -> str:
        return TraceStorage().filename_policy.probe_offset_tag_from_settings(settings)

    @staticmethod
    def _metadata_safe_value(value):
        return TraceStorage.metadata_safe_value(value)

    def _current_position_tuple(self) -> tuple[float, float] | None:
        if not self.is_positioner_connected or self._positioner is None:
            return None
        try:
            position = self._motion_service().query_position()
        except Exception:
            logger.exception("Failed to query position for trace filename.")
            return None
        return position.x_mm, position.y_mm

    @staticmethod
    def _position_filename_parts(position_mm: tuple[float, float] | None) -> tuple[str, str]:
        return TraceStorage().filename_policy.position_parts(position_mm)

    @staticmethod
    def _safe_filename_part(value: str) -> str:
        return TraceStorage().filename_policy.safe_part(value)

    @staticmethod
    def _scan_settings_dict(settings: dict | ScanSettings) -> dict:
        return ScanSettings.from_mapping(settings).to_dict()

    @staticmethod
    def _build_scan_volume(settings: dict | ScanSettings) -> ScanVolume:
        return ScanSettings.from_mapping(settings).scan_volume

    def _jog_positioner_axis_until(
        self,
        axis_name: str,
        target_position_mm: float,
        speed_mm_s: float,
        active_axis_name: str | None,
        active_direction: int,
    ) -> tuple[str | None, int]:
        try:
            return self._motion_service().jog_axis_until(
                axis_name=axis_name,
                target_position_mm=target_position_mm,
                speed_mm_s=speed_mm_s,
                active_axis_name=active_axis_name,
                active_direction=active_direction,
                wait_if_paused=self._wait_if_paused,
                raise_if_stopped=self._raise_if_stopped,
                is_paused=lambda: not self._resume_event.is_set(),
            )
        except MotionServiceError as exc:
            raise InstrumentServiceError(f"扫描架连续运动失败：{exc}") from exc

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

    @staticmethod
    def _is_user_stop_exception(exc: Exception) -> bool:
        message = str(exc)
        return "扫描流程已停止" in message or "Acquisition stopped" in message

    def _controller_for_name(self, name: str):
        if name == "vna":
            return self._vna
        if name == "positioner":
            return self._positioner
        if name == "switch_box":
            return self._switch_box
        raise InstrumentServiceError(f"未知仪器类型：{name}")

    @staticmethod
    def _connection_config_from(config: dict | InstrumentConnectionConfig | None) -> InstrumentConnectionConfig:
        if isinstance(config, InstrumentConnectionConfig):
            return config
        return InstrumentConnectionConfig.from_dict(config)

    @staticmethod
    def _vna_config_dict(config: dict | InstrumentConnectionConfig | VnaConnectionConfig | None) -> dict:
        if isinstance(config, VnaConnectionConfig):
            return config.to_dict()
        if isinstance(config, InstrumentConnectionConfig):
            return config.vna.to_dict()
        config = config or {}
        return VnaConnectionConfig.from_dict(config.get("vna", config)).to_dict()

    @staticmethod
    def _positioner_config_dict(
        config: dict | InstrumentConnectionConfig | PositionerConnectionConfig | None,
    ) -> dict:
        if isinstance(config, PositionerConnectionConfig):
            return config.to_dict()
        if isinstance(config, InstrumentConnectionConfig):
            return config.positioner.to_dict()
        config = config or {}
        return PositionerConnectionConfig.from_dict(config.get("positioner", config)).to_dict()

    @staticmethod
    def _switch_box_config_dict(
        config: dict | InstrumentConnectionConfig | SwitchBoxConnectionConfig | None,
    ) -> dict:
        if isinstance(config, SwitchBoxConnectionConfig):
            return config.to_dict()
        if isinstance(config, InstrumentConnectionConfig):
            return config.switch_box.to_dict()
        config = config or {}
        return SwitchBoxConnectionConfig.from_dict(config.get("switch_box", config)).to_dict()

    @staticmethod
    def _create_vna_controller(config: dict) -> VnaController:
        try:
            return InstrumentControllerFactory().create_vna(config)
        except InstrumentControllerFactoryError as exc:
            raise InstrumentServiceError(str(exc)) from exc

    @staticmethod
    def _create_positioner_controller(config: dict) -> PositionerController:
        try:
            return InstrumentControllerFactory().create_positioner(config)
        except InstrumentControllerFactoryError as exc:
            raise InstrumentServiceError(str(exc)) from exc

    @staticmethod
    def _create_switch_box_controller(config: dict) -> SwitchBoxController:
        try:
            return InstrumentControllerFactory().create_switch_box(config)
        except InstrumentControllerFactoryError as exc:
            raise InstrumentServiceError(str(exc)) from exc

    def _stop_positioner_quietly(self) -> None:
        if not self.is_positioner_connected or self._positioner is None:
            return
        self._motion_service().stop_all_quietly()
