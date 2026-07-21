from __future__ import annotations

import threading
import csv
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from catr_loss_calibrator.calibration.config_loader import load_calibration_catalog
from catr_loss_calibrator.calibration.models import CalibrationCatalog, CalibrationStep, CalibrationSubStep
from catr_loss_calibrator.calibration.calibration_runner import CalibrationRunner
from catr_loss_calibrator.calibration.state_machine import CalibrationState
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockScpiInstrument, MockVna
from catr_loss_calibrator.hardware.link_box.lcd74000f import Lcd74000fLinkBox
from catr_loss_calibrator.hardware.scpi import PyVisaScpiInstrument
from catr_loss_calibrator.hardware.vna.pyvisa_vna import PyVisaVna
from catr_loss_calibrator.instrument_management.models import InstrumentConnectionConfig
from catr_loss_calibrator.link_management.link_templates import link_command
from catr_loss_calibrator.runtime_resources import initialize_runtime_files, runtime_default_config_path
from catr_loss_calibrator.storage.loss_file_policy import LossFilePolicy
from catr_loss_calibrator.storage.workspace import (
    CalibrationRunContext,
    DEFAULT_OUTPUT_ROOT,
    create_session_context,
    write_latest_index,
    write_session_manifest,
    write_workspace_manifest,
    workspace_for_catalog,
)
from catr_loss_calibrator.storage.models import TraceRecord


@dataclass(frozen=True)
class StepViewData:
    item_id: str
    item_name: str
    step_id: str
    step_name: str
    step_index: int
    step_total: int
    status: str
    manual_instruction: str
    route_ids: tuple[str, ...]
    link_commands: tuple[str, ...]
    input_port: str
    output_port: str
    raw_outputs: tuple[str, ...]
    final_outputs: tuple[str, ...]
    required_inputs: tuple[str, ...]
    notes: str
    substep_id: str = ""
    substep_name: str = ""
    substep_index: int = 0
    substep_total: int = 0
    confirm_phase: str = ""
    item_total_substeps: int = 0
    item_completed_substeps: int = 0
    path_template: str = ""
    path: dict[str, Any] | None = None
    saved_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    level: str
    source: str
    name: str
    message: str


@dataclass(frozen=True)
class DeviceConnectionViewData:
    key: str
    display_name: str
    resource: str
    model: str
    use_mock: bool
    timeout_ms: int
    is_connected: bool


@dataclass(frozen=True)
class SubStepViewData:
    id: str
    name: str
    input_port: str
    output_port: str
    manual_instruction: str
    route_ids: tuple[str, ...]
    link_commands: tuple[str, ...]
    raw_output: str
    final_output: str
    required_inputs: tuple[str, ...]
    notes: str
    path_template: str = ""
    path: dict[str, Any] | None = None


class CalibrationRunWorker(QThread):
    prompt_ready = Signal(object)
    log_message = Signal(str, str, str, str)
    state_changed = Signal(str)
    finished_summary = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, runner: CalibrationRunner) -> None:
        super().__init__()
        self._runner = runner
        self._action_lock = threading.Condition()
        self._pending_action: str | None = None
        self._active_prompt: StepViewData | None = None

    def run(self) -> None:  # pragma: no cover - Qt thread
        try:
            self._runner.event_callback = self._handle_runner_event
            self.state_changed.emit(self._runner.state_machine.state.value)
            self._runner.run()
            self.log_message.emit("INFO", "runner", self._runner.item.name, f"执行完成: {self._runner.item.id}")
            self.finished_summary.emit(self._runner.overview())
        except Exception as exc:  # pragma: no cover - Qt thread
            self.error_occurred.emit(str(exc))
        finally:
            self._runner.event_callback = None

    def confirm_step(self, step, substep, phase: str, index: int, total: int, substep_index: int, substep_total: int) -> str:
        status = "等待开始确认" if phase == "start" else "等待保存完成确认"
        item_total_substeps = sum(len(self._runner._substeps_for(item_step)) for item_step in self._runner.item.steps)
        item_completed_substeps = self._item_completed_substeps(index, substep_index, phase)
        prompt = StepViewData(
            item_id=self._runner.item.id,
            item_name=self._runner.item.name,
            step_id=step.id,
            step_name=step.name,
            step_index=index,
            step_total=total,
            status=status,
            manual_instruction=substep.manual_instruction or step.manual_instruction,
            route_ids=substep.route_ids or step.route_ids,
            link_commands=substep.link_commands or step.link_commands,
            input_port=substep.input_port or step.input_port,
            output_port=substep.output_port or step.output_port,
            raw_outputs=((substep.raw_output,) if substep.raw_output else step.raw_outputs),
            final_outputs=((substep.final_output,) if substep.final_output else step.final_outputs),
            required_inputs=substep.required_inputs or step.required_inputs,
            notes=substep.notes or step.notes,
            substep_id=substep.id,
            substep_name=substep.name,
            substep_index=substep_index,
            substep_total=substep_total,
            confirm_phase=phase,
            item_total_substeps=item_total_substeps,
            item_completed_substeps=item_completed_substeps,
            path_template=substep.path_template or step.path_template,
            path=substep.path or step.path,
            saved_files=self._saved_files_for_prompt(step, substep, phase),
        )
        self._active_prompt = prompt
        self.prompt_ready.emit(prompt)
        self.state_changed.emit(status)
        with self._action_lock:
            while self._pending_action is None:
                self._action_lock.wait()
            action = self._pending_action
            self._pending_action = None
        self.state_changed.emit(self._runner.state_machine.state.value)
        return action or "continue"

    def submit_action(self, action: str) -> None:
        with self._action_lock:
            self._pending_action = action
            self._action_lock.notify_all()

    @property
    def active_prompt(self) -> StepViewData | None:
        return self._active_prompt

    def _saved_files_for_prompt(self, step: CalibrationStep, substep: CalibrationSubStep, phase: str) -> tuple[str, ...]:
        if phase != "saved":
            return ()
        files: list[str] = []
        output_paths = getattr(self._runner, "_output_paths", {})
        for parameter in ((substep.final_output,) if substep.final_output else step.final_outputs):
            path = output_paths.get(parameter) if isinstance(output_paths, dict) else None
            if path is not None:
                files.append(str(path))
        source_step = f"{step.id}_{self._runner._safe_token(substep.id)}"
        raw_name = f"{self._runner.item.id}_{source_step}.csv"
        for path in getattr(self._runner, "_raw_paths", ()):
            if Path(path).name == raw_name:
                files.append(str(path))
        seen: set[str] = set()
        unique: list[str] = []
        for path in files:
            key = path.lower()
            if key not in seen:
                seen.add(key)
                unique.append(path)
        return tuple(unique)

    def _handle_runner_event(self, event: str) -> None:
        level, source, name, message = self._log_fields_for_event(event, self._runner.item.name)
        self.log_message.emit(level, source, name, message)

    @staticmethod
    def _log_fields_for_event(event: str, item_name: str) -> tuple[str, str, str, str]:
        if event.startswith("failure:"):
            parts = event.split(":", 6)
            if len(parts) == 7:
                _, kind, step_id, substep_id, state, action, message = parts
                return (
                    "ERROR",
                    "runner",
                    item_name,
                    f"失败: {kind}; 步骤={step_id}/{substep_id}; 状态={state}; 建议={action}; {message}",
                )
        parts = event.split(":", 3)
        kind = parts[0] if parts else ""
        if kind == "link" and len(parts) == 4:
            return ("INFO", "link_box", item_name, f"下发链路箱命令: {parts[3]}")
        if kind == "raw" and len(parts) >= 2:
            return ("INFO", "storage", item_name, f"保存原始曲线: {parts[1]}")
        if kind == "loss" and len(parts) >= 2:
            return ("INFO", "storage", item_name, f"保存路损文件: {parts[1]}")
        if kind == "metadata" and len(parts) >= 2:
            return ("INFO", "storage", item_name, f"保存元数据: {parts[1]}")
        if kind == "start" and len(parts) >= 2:
            return ("INFO", "runner", item_name, f"开始执行: {parts[1]}")
        if kind == "done" and len(parts) >= 2:
            return ("INFO", "runner", item_name, f"流程结束: {parts[1]}")
        if kind in {"skip", "retry", "cancel"}:
            messages = {"skip": "跳过步骤", "retry": "重试步骤", "cancel": "取消流程"}
            return ("WARNING" if kind == "cancel" else "INFO", "runner", item_name, f"{messages[kind]}: {event}")
        return ("INFO", "runner", item_name, event)

    def _item_completed_substeps(self, step_index: int, substep_index: int, phase: str) -> int:
        completed = 0
        for item_step in self._runner.item.steps[: max(step_index - 1, 0)]:
            completed += len(self._runner._substeps_for(item_step))
        if phase == "saved":
            completed += substep_index
        else:
            completed += max(0, substep_index - 1)
        return completed


class CalibrationViewModel(QObject):
    catalog_changed = Signal()
    selected_item_changed = Signal()
    selected_step_changed = Signal()
    step_view_changed = Signal(object)
    logs_changed = Signal()
    status_changed = Signal(str)
    overview_changed = Signal(object)
    run_state_changed = Signal(str)
    command_response_changed = Signal(str)
    run_finished = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.catalog = CalibrationCatalog(display_name="未加载链路配置")
        self._selected_index = 0
        self._selected_step_index = 0
        self._logs: list[LogEntry] = []
        self._overview: dict[str, object] = {}
        self._run_summaries_by_item: dict[str, dict[str, object]] = {}
        self._run_status_by_item: dict[str, str] = {}
        self._active_run_item_id = ""
        self._status_text = "Ready"
        self._command_response = ""
        self._worker: CalibrationRunWorker | None = None
        self._device_configs = {
            "vna": InstrumentConnectionConfig(resource="MOCK::VNA::001", model="E5080B", use_mock=True, timeout_ms=5000),
            "signal_generator": InstrumentConnectionConfig(resource="MOCK::SG", model="MOCK-SG", use_mock=True),
            "link_box": InstrumentConnectionConfig(resource="MOCK::LINKBOX", model="LCD74000F-MOCK", use_mock=True),
            "spectrum_analyzer": InstrumentConnectionConfig(resource="MOCK::SA", model="MOCK-SA", use_mock=True),
        }
        self._mock_vna = self._create_device("vna")
        self._mock_signal_generator = self._create_device("signal_generator")
        self._mock_link_box = self._create_device("link_box")
        self._mock_spectrum_analyzer = self._create_device("spectrum_analyzer")
        self._append_log(
            "INFO",
            "config",
            "链路配置",
            "未加载链路配置，请导入链路配置或导入默认配置。",
        )

    @property
    def selected_item(self):
        if not self.catalog.items:
            return None
        return self.catalog.items[self._selected_index]

    @property
    def selected_step(self):
        item = self.selected_item
        if item is None:
            return None
        steps = item.steps
        if not steps:
            return None
        index = max(0, min(self._selected_step_index, len(steps) - 1))
        return steps[index]

    @property
    def selected_step_index(self) -> int:
        return self._selected_step_index

    @property
    def logs(self) -> list[LogEntry]:
        return list(self._logs)

    @property
    def overview(self) -> dict[str, object]:
        return dict(self._overview)

    @property
    def status_text(self) -> str:
        return self._status_text

    @property
    def command_response(self) -> str:
        return self._command_response

    def load_default_catalog(self) -> None:
        initialize_runtime_files()
        self._replace_catalog(load_calibration_catalog(runtime_default_config_path()), "已导入默认链路配置")

    def load_catalog(self, path: str | Path) -> None:
        self._replace_catalog(load_calibration_catalog(path), "已导入链路配置")

    def _replace_catalog(self, catalog: CalibrationCatalog, log_prefix: str) -> None:
        if self._worker and self._worker.isRunning():
            raise RuntimeError("校准运行中，不能导入新的链路配置。")
        if not catalog.items:
            raise RuntimeError("链路配置中没有 calibration_items，无法生成校准项。")
        self.catalog = catalog
        self._selected_index = 0
        self._selected_step_index = 0
        self._run_summaries_by_item.clear()
        self._run_status_by_item.clear()
        self._active_run_item_id = ""
        self._status_text = "Ready"
        self._append_log(
            "INFO",
            "config",
            catalog.display_name or catalog.name,
            self._catalog_log_message(catalog, log_prefix),
        )
        self.catalog_changed.emit()
        self.status_changed.emit(self._status_text)
        self.selected_item_changed.emit()
        self.selected_step_changed.emit()
        self.refresh_overview()

    @staticmethod
    def _catalog_log_message(catalog, prefix: str) -> str:
        config_name = catalog.display_name or catalog.name or "未命名链路配置"
        schema_version = catalog.schema_version or "未知"
        source_path = catalog.source_path or "内置配置"
        return f"{prefix}: {config_name}; schema={schema_version}; source={source_path}"

    def run_summary_for_item(self, item_id: str) -> dict[str, object]:
        return dict(self._run_summaries_by_item.get(item_id, {}))

    def item_progress_state(self, item_id: str) -> str:
        summary = self._run_summaries_by_item.get(item_id, {})
        if item_id == self._active_run_item_id:
            if not summary or summary.get("item_id") != item_id:
                return "running"
        if not summary or summary.get("item_id") != item_id:
            return "pending"
        state = str(summary.get("state", "")).strip().upper()
        completed_substeps = {
            str(substep_id)
            for substep_id in summary.get("completed_substep_ids", ())
        }
        total_substeps = self._total_substeps_for_item(item_id)
        if total_substeps and len(completed_substeps) >= total_substeps:
            return "done"
        if state in {"DONE", "CALIBRATION COMPLETED"} or "COMPLETE" in state:
            return "done"
        if completed_substeps or state not in {"READY", "IDLE"}:
            return "running"
        return "pending"

    def step_progress_state(self, item_id: str, step_id: str) -> str:
        summary = self._run_summaries_by_item.get(item_id, {})
        if not summary or summary.get("item_id") != item_id:
            return "pending"
        completed_step_ids = {
            str(step_id_value)
            for step_id_value in summary.get("completed_step_ids", ())
        }
        if step_id in completed_step_ids:
            return "done"
        active_step_id = str(summary.get("active_step_id", "")).strip()
        state = str(summary.get("state", "")).strip().upper()
        if active_step_id == step_id and (
            item_id == self._active_run_item_id or state not in {"READY", "IDLE"} or completed_step_ids
        ):
            return "running"
        return "pending"

    def substep_progress_state(self, item_id: str, step_id: str, substep_id: str) -> str:
        summary = self._run_summaries_by_item.get(item_id, {})
        if not summary or summary.get("item_id") != item_id:
            return "pending"
        completed_substep_ids = {
            str(substep_id_value)
            for substep_id_value in summary.get("completed_substep_ids", ())
        }
        if f"{step_id}:{substep_id}" in completed_substep_ids:
            return "done"
        completed_step_ids = {
            str(step_id_value)
            for step_id_value in summary.get("completed_step_ids", ())
        }
        if step_id in completed_step_ids:
            return "done"
        active_step_id = str(summary.get("active_step_id", "")).strip()
        active_substep_id = str(summary.get("active_substep_id", "")).strip()
        state = str(summary.get("state", "")).strip().upper()
        if active_step_id == step_id and active_substep_id == substep_id and (
            item_id == self._active_run_item_id or state not in {"READY", "IDLE"} or completed_substep_ids
        ):
            return "running"
        return "pending"

    def select_item(self, index: int) -> None:
        if not self.catalog.items:
            self._selected_index = 0
            self._selected_step_index = 0
            self.refresh_overview()
            self.selected_item_changed.emit()
            self.selected_step_changed.emit()
            return
        if 0 <= index < len(self.catalog.items):
            self._selected_index = index
            self.refresh_overview()
            self.selected_item_changed.emit()
            self.select_step(0)

    def select_step(self, index: int) -> None:
        item = self.selected_item
        if item is None:
            self._selected_step_index = 0
            self.selected_step_changed.emit()
            return
        steps = item.steps
        if not steps:
            self._selected_step_index = 0
            self.selected_step_changed.emit()
            return
        if 0 <= index < len(steps):
            self._selected_step_index = index
            self.selected_step_changed.emit()
            self._append_log("INFO", "ui", item.name, f"切换到步骤 {steps[index].id}")
            self.step_view_changed.emit(self._step_view_data(steps[index], index + 1, len(steps)))

    def connect_mock_devices(self) -> None:
        for device in ("vna", "signal_generator", "link_box", "spectrum_analyzer"):
            self.connect_device(device)
        self._status_text = "Devices connected"
        self.status_changed.emit(self._status_text)
        self._append_log("INFO", "device", "all", "全部设备已连接")
        self.refresh_overview()

    def disconnect_mock_devices(self) -> None:
        for device in ("vna", "signal_generator", "link_box", "spectrum_analyzer"):
            self.disconnect_device(device)
        self._status_text = "Devices disconnected"
        self.status_changed.emit(self._status_text)
        self._append_log("INFO", "device", "all", "全部设备已断开")
        self.refresh_overview()

    def update_device_config(
        self,
        device: str,
        *,
        resource: str,
        model: str,
        use_mock: bool,
        timeout_ms: int,
    ) -> DeviceConnectionViewData:
        current = self._device_configs[device]
        config = InstrumentConnectionConfig(
            resource=resource.strip() or current.resource,
            model=model.strip() or current.model,
            use_mock=use_mock,
            timeout_ms=max(1, int(timeout_ms)),
        )
        if not config.use_mock and config.resource.upper().startswith("MOCK"):
            raise RuntimeError("真实连接模式下不能使用 MOCK 资源，请先搜索并选择 VISA 资源。")
        instrument, _ = self._command_device(device)
        if instrument.is_connected:
            raise RuntimeError("请先断开设备，再修改连接配置。")
        self._device_configs[device] = config
        self._set_device(device, self._create_device(device))
        self._append_log("INFO", "device", self._device_display_name(device), f"更新连接配置: {config.resource}")
        self.refresh_overview()
        return self.device_connection_state(device)

    def connect_device(self, device: str) -> DeviceConnectionViewData:
        instrument, display_name = self._command_device(device)
        if not instrument.is_connected:
            info = instrument.connect()
            self._append_log("INFO", "device", display_name, f"已连接 {info.resource} ({info.model})")
        self.refresh_overview()
        return self.device_connection_state(device)

    def disconnect_device(self, device: str) -> DeviceConnectionViewData:
        instrument, display_name = self._command_device(device)
        if instrument.is_connected:
            instrument.disconnect()
            self._append_log("INFO", "device", display_name, "已断开")
        self.refresh_overview()
        return self.device_connection_state(device)

    def device_connection_state(self, device: str) -> DeviceConnectionViewData:
        config = self._device_configs[device]
        instrument, display_name = self._command_device(device)
        return DeviceConnectionViewData(
            key=device,
            display_name=display_name,
            resource=config.resource,
            model=config.model,
            use_mock=config.use_mock,
            timeout_ms=config.timeout_ms,
            is_connected=instrument.is_connected,
        )

    def device_model_options(self, device: str) -> tuple[str, ...]:
        options = {
            "vna": ("E5080B", "N5245B", "MOCK-VNA"),
            "signal_generator": ("N5183B", "E8257D", "SMB100A", "MOCK-SG"),
            "link_box": ("LCD74000F", "LCD74000F-MOCK"),
            "spectrum_analyzer": ("N9020B", "FSW", "MOCK-SA"),
        }
        config = self._device_configs[device]
        values = options[device]
        return self._unique_texts((config.model, *values))

    def device_mock_resource_options(self, device: str) -> tuple[str, ...]:
        options = {
            "vna": ("MOCK::VNA::001", "MOCK::VNA"),
            "signal_generator": ("MOCK::SG", "MOCK::SIGNAL_GENERATOR"),
            "link_box": ("MOCK::LINKBOX",),
            "spectrum_analyzer": ("MOCK::SA", "MOCK::SPECTRUM_ANALYZER"),
        }
        config = self._device_configs[device]
        return self._unique_texts((config.resource, *options[device]))

    def list_visa_resources(self) -> tuple[str, ...]:
        try:
            import pyvisa
        except ImportError as exc:
            raise RuntimeError("未安装 pyvisa，无法搜索 VISA 资源。") from exc
        try:
            return tuple(str(resource) for resource in pyvisa.ResourceManager().list_resources())
        except Exception as exc:
            raise RuntimeError(f"搜索 VISA 资源失败: {exc}") from exc

    def start_selected(self, vna_settings: dict[str, Any] | None = None) -> None:
        settings = dict(vna_settings or {})
        if self._worker and self._worker.isRunning():
            self._append_log("WARN", "runner", self._active_run_item_id or "unknown", "runner already running")
            return
        item = self.selected_item
        if item is None:
            raise RuntimeError("请先导入链路配置或导入默认配置。")
        self._run_summaries_by_item.pop(item.id, None)
        self._run_status_by_item[item.id] = f"Running {item.id}"
        self._active_run_item_id = item.id
        workspace = workspace_for_catalog(self.catalog, DEFAULT_OUTPUT_ROOT)
        write_workspace_manifest(workspace, self.catalog)
        run_context = CalibrationRunContext(
            project_code=str(settings.get("project_code") or "DEFAULT_PROJECT"),
            calibration_stage=str(settings.get("calibration_stage") or "initial"),
            run_label=str(settings.get("run_label") or "R01"),
            operator=str(settings.get("operator") or ""),
            operator_note=str(settings.get("operator_note") or ""),
        )
        session_context = create_session_context(workspace=workspace, run=run_context, item_id=item.id)
        runner = CalibrationRunner(
            item=item,
            vna=self._mock_vna,
            link_box=self._mock_link_box,
            output_root=session_context.session_root,
            vna_settings=settings,
            feed=str(settings.get("feed") or "F10_17G"),
            horn=str(settings.get("horn") or "H10_15G"),
            loss_file_policy=LossFilePolicy.from_band_config(self.catalog.band_config),
            session_context=session_context,
        )
        worker = CalibrationRunWorker(runner)
        worker.prompt_ready.connect(self._on_prompt_ready)
        worker.log_message.connect(
            lambda level, source, name, message: self._append_log(level, source, name, message)
        )
        worker.state_changed.connect(self.run_state_changed.emit)
        worker.finished_summary.connect(self._on_finished_summary)
        worker.error_occurred.connect(self._on_worker_error)
        worker.finished.connect(self._cleanup_worker)
        runner.confirm_step = worker.confirm_step
        self._worker = worker
        self._status_text = f"Running {item.id}"
        self.status_changed.emit(self._status_text)
        self._append_log("INFO", "runner", item.name, f"开始执行 {item.id}")
        self.refresh_overview()
        worker.start()

    def run_single_substep(self, step_id: str, substep_id: str, vna_settings: dict[str, Any] | None = None) -> dict[str, object]:
        settings = dict(vna_settings or {})
        if self._worker and self._worker.isRunning():
            raise RuntimeError("校准运行中，不能单独重测细分步骤。")
        item = self.selected_item
        if item is None:
            raise RuntimeError("请先导入链路配置或导入默认配置。")
        step = next((candidate for candidate in item.steps if candidate.id == step_id), None)
        if step is None:
            raise RuntimeError(f"未找到步骤: {step_id}")
        substep = next((candidate for candidate in self._substeps_for_step(step) if candidate.id == substep_id), None)
        if substep is None:
            raise RuntimeError(f"未找到细分步骤: {step_id}/{substep_id}")
        workspace = workspace_for_catalog(self.catalog, DEFAULT_OUTPUT_ROOT)
        write_workspace_manifest(workspace, self.catalog)
        run_context = CalibrationRunContext(
            project_code=str(settings.get("project_code") or "DEFAULT_PROJECT"),
            calibration_stage=str(settings.get("calibration_stage") or "initial"),
            run_label=f"{settings.get('run_label') or 'R01'}_RETEST",
            operator=str(settings.get("operator") or ""),
            operator_note=f"single-substep-retest:{step_id}:{substep_id}",
        )
        session_context = create_session_context(workspace=workspace, run=run_context, item_id=item.id)
        runner = CalibrationRunner(
            item=item,
            vna=self._mock_vna,
            link_box=self._mock_link_box,
            output_root=session_context.session_root,
            vna_settings=settings,
            feed=str(settings.get("feed") or "F10_17G"),
            horn=str(settings.get("horn") or "H10_15G"),
            loss_file_policy=LossFilePolicy.from_band_config(self.catalog.band_config),
            session_context=session_context,
        )
        runner._ensure_ready()
        runner.state_machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM)
        self._append_log("INFO", "runner", item.name, f"单独重测细分步骤: {step_id}/{substep_id}")
        runner._run_substep(step, substep)
        runner.state_machine.transition(CalibrationState.DONE)
        runner._record_event(f"single_done:{step_id}:{substep_id}")
        runner._write_session_manifest()
        summary = runner.overview()
        existing = dict(self._run_summaries_by_item.get(item.id, {}))
        completed = set(str(value) for value in existing.get("completed_substep_ids", ()) or ())
        completed.add(f"{step_id}:{substep_id}")
        completed_steps = set(str(value) for value in existing.get("completed_step_ids", ()) or ())
        if all(f"{step.id}:{candidate.id}" in completed for candidate in self._substeps_for_step(step)):
            completed_steps.add(step_id)
        summary["completed_substep_ids"] = tuple(sorted(completed))
        summary["completed_step_ids"] = tuple(sorted(completed_steps))
        summary["completed_steps"] = len(completed)
        summary["completed_big_steps"] = len(completed_steps)
        summary["active_step_id"] = step_id
        summary["active_substep_id"] = substep_id
        self._run_summaries_by_item[item.id] = summary
        self._run_status_by_item[item.id] = "Single substep retested"
        self.status_text_update(f"已重测 {step_id}/{substep_id}")
        self._append_log("INFO", "runner", item.name, f"单独重测完成: {step_id}/{substep_id}")
        self.refresh_overview()
        return summary

    def generate_resume_results(
        self,
        history_summary: dict[str, object],
        manual_judgments: dict[str, str],
        vna_settings: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        settings = dict(vna_settings or {})
        if self._worker and self._worker.isRunning():
            raise RuntimeError("校准运行中，不能生成续测结果。")
        item = self.selected_item
        if item is None:
            raise RuntimeError("请先导入链路配置或导入默认配置。")
        workspace = workspace_for_catalog(self.catalog, DEFAULT_OUTPUT_ROOT)
        write_workspace_manifest(workspace, self.catalog)
        run_context = CalibrationRunContext(
            project_code=str(settings.get("project_code") or "DEFAULT_PROJECT"),
            calibration_stage=str(settings.get("calibration_stage") or "initial"),
            run_label=f"{settings.get('run_label') or 'R01'}_RESUME",
            operator=str(settings.get("operator") or ""),
            operator_note="resume-generate-results",
        )
        session_context = create_session_context(workspace=workspace, run=run_context, item_id=item.id)
        runner = CalibrationRunner(
            item=item,
            vna=self._mock_vna,
            link_box=self._mock_link_box,
            output_root=session_context.session_root,
            vna_settings=settings,
            feed=str(settings.get("feed") or "F10_17G"),
            horn=str(settings.get("horn") or "H10_15G"),
            loss_file_policy=LossFilePolicy.from_band_config(self.catalog.band_config),
            session_context=session_context,
        )
        raw_by_key = self._resume_raw_paths_by_substep(item, history_summary)
        current_retested = {str(key) for key in history_summary.get("current_retested_substep_ids", ()) or ()}
        accepted_keys = {
            str(key)
            for key, judgment in manual_judgments.items()
            if str(judgment) == "accept"
        } | current_retested
        required_keys = self._required_substep_keys(item)
        compatibility_warnings = self._resume_compatibility_warnings(history_summary, runner)
        loaded_keys: set[str] = set()
        loaded_records: list[TraceRecord] = []
        reused_files: list[str] = []
        new_files: list[str] = []
        invalid_files: list[str] = []
        substep_status: dict[str, dict[str, object]] = {}
        for key in sorted(required_keys & accepted_keys):
            path = raw_by_key.get(key)
            if path is None:
                substep_status[key] = {"status": "MISSING", "reason": "未找到 raw CSV"}
                continue
            step_id, substep_id = key.split(":", 1)
            step = next(step for step in item.steps if step.id == step_id)
            substep = next(substep for substep in self._substeps_for_step(step) if substep.id == substep_id)
            try:
                record = self._trace_record_from_csv(path, fallback_parameter=substep.raw_output or step.id, source_step=f"{step_id}_{self._safe_token(substep_id)}")
            except Exception as exc:
                invalid_files.append(str(path))
                substep_status[key] = {"status": "BROKEN_FILE", "reason": str(exc), "raw_file": str(path)}
                continue
            record_warnings = self._record_sweep_warnings(record, runner)
            if key not in current_retested:
                record_warnings = tuple(compatibility_warnings) + record_warnings
            runner._records[record.parameter] = record
            runner._track_path(runner._raw_paths, path)
            loaded_keys.add(key)
            loaded_records.append(record)
            if key in current_retested:
                new_files.append(str(path))
                status = "VALID_CURRENT"
                reason = "本次重测数据"
            else:
                reused_files.append(str(path))
                status = "VALID_HISTORY"
                reason = "人工判定沿用历史数据"
            substep_status[key] = {
                "status": status,
                "reason": reason,
                "raw_file": str(path),
                "parameter": record.parameter,
                **({"warnings": record_warnings} if record_warnings else {}),
            }
        for key in sorted(required_keys - set(substep_status)):
            if key in raw_by_key:
                judgment = str(manual_judgments.get(key) or "")
                substep_status[key] = {
                    "status": "REJECTED_BY_OPERATOR" if judgment == "retest" else "MISSING",
                    "reason": "人工判定需重测" if judgment == "retest" else "未人工判定沿用",
                    "raw_file": str(raw_by_key[key]),
                }
            else:
                substep_status[key] = {"status": "MISSING", "reason": "未找到 raw CSV"}
        for record in loaded_records:
            runner._compute_available_outputs("RESUME_RECOMPUTE", record.frequency_hz)
        state = "RESUMED_DONE" if required_keys and required_keys <= loaded_keys else "PARTIAL"
        manifest_path = write_session_manifest(
            session_context,
            state=state,
            raw_files=tuple(str(path) for path in runner._raw_paths),
            loss_files=tuple(str(path) for path in runner._output_paths.values()),
            metadata_files=tuple(str(path) for path in history_summary.get("metadata_files", ()) or ()),
            last_event=f"resume_generate:{state}",
            extra_fields={
                "resume_source": {
                    "workspace_root": str(history_summary.get("workspace_root") or ""),
                    "session_id": str(history_summary.get("session_id") or ""),
                    "manifest_file": str(history_summary.get("manifest_file") or ""),
                    "item_id": str(history_summary.get("item_id") or ""),
                },
                "substep_status": substep_status,
                "reused_files": tuple(reused_files),
                "new_files": tuple(new_files),
                "invalid_files": tuple(invalid_files),
                "resume_compatibility_blockers": (),
                "resume_compatibility_warnings": compatibility_warnings,
            },
        )
        latest_path = write_latest_index(session_context, manifest_path) if state == "RESUMED_DONE" else None
        summary = runner.overview()
        summary.update(
            {
                "state": state,
                "raw_files": tuple(str(path) for path in runner._raw_paths),
                "loss_files": tuple(str(path) for path in runner._output_paths.values()),
                "metadata_files": tuple(str(path) for path in history_summary.get("metadata_files", ()) or ()),
                "manifest_file": str(manifest_path),
                "latest_index_file": str(latest_path) if latest_path else "",
                "completed_substep_ids": tuple(sorted(loaded_keys)),
                "completed_step_ids": tuple(
                    step.id
                    for step in item.steps
                    if all(f"{step.id}:{substep.id}" in loaded_keys for substep in self._substeps_for_step(step))
                ),
                "completed_steps": len(loaded_keys),
                "completed_big_steps": sum(
                    1
                    for step in item.steps
                    if all(f"{step.id}:{substep.id}" in loaded_keys for substep in self._substeps_for_step(step))
                ),
                "resume_source_session_id": str(history_summary.get("session_id") or ""),
                "resume_source": {
                    "workspace_root": str(history_summary.get("workspace_root") or ""),
                    "session_id": str(history_summary.get("session_id") or ""),
                    "manifest_file": str(history_summary.get("manifest_file") or ""),
                    "item_id": str(history_summary.get("item_id") or ""),
                },
                "substep_status": substep_status,
                "reused_files": tuple(reused_files),
                "new_files": tuple(new_files),
                "invalid_files": tuple(invalid_files),
                "resume_compatibility_blockers": (),
                "resume_compatibility_warnings": compatibility_warnings,
            }
        )
        self._run_summaries_by_item[item.id] = summary
        self._run_status_by_item[item.id] = state
        self.status_text_update(f"续测结果已生成: {state}")
        self._append_log("INFO", "runner", item.name, f"续测结果已生成: {state}")
        self.refresh_overview()
        return summary

    def _required_substep_keys(self, item) -> set[str]:
        return {
            f"{step.id}:{substep.id}"
            for step in item.steps
            for substep in self._substeps_for_step(step)
        }

    @staticmethod
    def _resume_compatibility_warnings(history_summary: dict[str, object], runner: CalibrationRunner) -> tuple[str, ...]:
        warnings: list[str] = []
        current_config_hash = str(runner.session_context.workspace.config_hash if runner.session_context else "").strip()
        history_config_hash = str(history_summary.get("config_hash") or "").strip()
        if current_config_hash and history_config_hash and current_config_hash != history_config_hash:
            warnings.append("config_hash mismatch")

        history_settings = history_summary.get("measurement_settings")
        if isinstance(history_settings, dict):
            current_settings = runner._measurement_settings_summary()
            for key in ("start_hz", "stop_hz", "power_dbm", "if_bandwidth_hz"):
                if key not in history_settings:
                    warnings.append(f"{key} missing")
                    continue
                if not np.isclose(float(history_settings[key]), float(current_settings[key])):
                    warnings.append(f"{key} mismatch")
            for key in ("points", "parameter", "feed", "horn"):
                if key not in history_settings:
                    warnings.append(f"{key} missing")
                    continue
                if str(history_settings[key]).strip().upper() != str(current_settings[key]).strip().upper():
                    warnings.append(f"{key} mismatch")
            history_hash = str(history_settings.get("horn_gain_sha256") or "").strip()
            current_hash = str(current_settings.get("horn_gain_sha256") or "").strip()
            history_file = str(history_settings.get("horn_gain_file") or "").strip()
            current_file = str(current_settings.get("horn_gain_file") or "").strip()
            if history_hash and current_hash and history_hash != current_hash:
                warnings.append("horn_gain_sha256 changed")
            elif (history_file or current_file) and not (history_hash and current_hash):
                warnings.append("horn_gain_sha256 missing")
            if history_file and current_file and Path(history_file).name != Path(current_file).name:
                warnings.append("horn_gain_file changed")
        else:
            warnings.append("measurement_settings missing")
        return tuple(warnings)

    @staticmethod
    def _record_sweep_warnings(record: TraceRecord, runner: CalibrationRunner) -> tuple[str, ...]:
        settings = runner._measurement_settings_summary()
        points = int(settings["points"])
        target = np.linspace(float(settings["start_hz"]), float(settings["stop_hz"]), points)
        frequency = np.asarray(record.frequency_hz, dtype=float)
        warnings: list[str] = []
        if len(frequency) != points:
            warnings.append("points mismatch")
        elif not np.allclose(frequency, target):
            warnings.append("frequency axis mismatch")
        if len(frequency) >= 2 and np.any(np.diff(frequency) <= 0):
            warnings.append("frequency axis is not strictly increasing")
        return tuple(warnings)

    def _resume_raw_paths_by_substep(self, item, history_summary: dict[str, object]) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for step in item.steps:
            for substep in self._substeps_for_step(step):
                expected_name = f"{item.id}_{step.id}_{self._safe_token(substep.id)}.csv"
                key = f"{step.id}:{substep.id}"
                for path in self._summary_paths(history_summary, "raw_files"):
                    if path.name == expected_name:
                        paths[key] = path
                        break
        return paths

    @staticmethod
    def _summary_paths(summary: dict[str, object], key: str) -> tuple[Path, ...]:
        session_root = Path(str(summary.get("session_root") or ""))
        workspace_root = Path(str(summary.get("workspace_root") or ""))
        result: list[Path] = []
        for raw_path in summary.get(key, ()) or ():
            path = Path(str(raw_path))
            if not path.is_absolute():
                candidates = [path]
                if session_root:
                    candidates.append(session_root / path)
                if workspace_root:
                    candidates.append(workspace_root / path)
                path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
            if path.exists():
                result.append(path)
        return tuple(result)

    @staticmethod
    def _trace_record_from_csv(path: Path, *, fallback_parameter: str, source_step: str) -> TraceRecord:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = tuple(reader.fieldnames or ())
        if not fieldnames:
            raise ValueError(f"{path.name} 没有表头。")
        lower_to_name = {name.strip().lower(): name for name in fieldnames}
        freq_column = lower_to_name.get("freq_hz") or lower_to_name.get("frequency_hz") or next(
            (name for name in fieldnames if "freq" in name.strip().lower()),
            "",
        )
        if not freq_column:
            raise ValueError(f"{path.name} 未找到频率列。")
        value_column = lower_to_name.get("value_db") or lower_to_name.get("raw_s21_db") or next(
            (name for name in fieldnames if name != freq_column and (name.strip().lower().endswith("_db") or "s21" in name.strip().lower())),
            "",
        )
        if not value_column:
            raise ValueError(f"{path.name} 未找到 dB 曲线列。")
        frequency_hz = np.asarray([float(str(row.get(freq_column)).strip()) for row in rows], dtype=float)
        value_db = np.asarray([float(str(row.get(value_column)).strip()) for row in rows], dtype=float)
        parameter = str(rows[0].get("param") or fallback_parameter).strip() if rows else fallback_parameter
        output_role = str(rows[0].get("output_role") or "raw_s21").strip() if rows else "raw_s21"
        return TraceRecord(
            frequency_hz=frequency_hz,
            value_db=value_db,
            parameter=parameter or fallback_parameter,
            source_cal="resume",
            source_step=source_step,
            output_role=output_role,
        )

    def submit_action(self, action: str) -> bool:
        item_name = self.selected_item.name if self.selected_item is not None else "未加载链路配置"
        normalized_action = action.strip().lower()
        if normalized_action not in {"continue", "skip", "retry", "cancel"}:
            message = f"非法操作: {action}"
            self._append_log("ERROR", "ui", item_name, message)
            self.status_text_update(message)
            return False
        if self._worker and self._worker.isRunning():
            self._append_log("INFO", "ui", item_name, f"用户操作: {normalized_action}")
            self._worker.submit_action(normalized_action)
            return True
        else:
            message = f"非法操作: 当前没有等待确认的校准步骤，已忽略 {normalized_action}"
            self._append_log("WARNING", "ui", item_name, message)
            self.status_text_update(message)
            return False

    def send_command(self, command: str) -> str:
        return self.send_device_command("link_box", command)

    def send_device_command(self, device: str, command: str) -> str:
        command = command.strip()
        if not command:
            raise ValueError("Command is empty.")
        instrument, display_name = self._command_device(device)
        response = instrument.send_command(command)
        self._command_response = response
        self.command_response_changed.emit(response)
        self._append_log("INFO", "command", display_name, f"发送命令: {command}")
        self._append_log("INFO", "command", display_name, f"返回响应: {response}")
        return response

    def _send_device_command_sequence(self, device: str, log_source: str, commands: tuple[str, ...]) -> tuple[str, ...]:
        instrument, display_name = self._command_device(device)
        responses: list[str] = []
        for command in commands:
            response = instrument.send_command(command)
            responses.append(response)
            self._append_log("INFO", log_source, display_name, f"发送命令: {command}")
            self._append_log("INFO", log_source, display_name, f"返回响应: {response}")
        return tuple(responses)

    def configure_vna(self, settings: dict[str, Any]) -> str:
        vna, display_name = self._command_device("vna")
        start_hz = float(settings["start_ghz"]) * 1e9
        stop_hz = float(settings["stop_ghz"]) * 1e9
        points = int(settings["points"])
        power_dbm = float(settings["vna_power_dbm"])
        if_bandwidth_hz = float(settings["if_bandwidth_hz"])
        parameter = str(settings["parameter"]).strip().upper()
        continuous = bool(settings.get("continuous_sweep", False))
        vna.configure_power(power_dbm)
        vna.configure_if_bandwidth(if_bandwidth_hz)
        vna.configure_sweep(start_hz, stop_hz, points)
        configure_parameter = getattr(vna, "configure_measurement_parameter", None)
        if callable(configure_parameter):
            configure_parameter(parameter)
        configure_continuous = getattr(vna, "configure_continuous_sweep", None)
        if callable(configure_continuous):
            configure_continuous(continuous)
        response = (
            f"OK: {parameter}, {start_hz:.12g}-{stop_hz:.12g} Hz, "
            f"{points} pts, {power_dbm:.1f} dBm, IFBW {if_bandwidth_hz:.0f} Hz"
        )
        self._command_response = response
        self.command_response_changed.emit(response)
        self._append_log("INFO", "vna", display_name, response)
        return response

    def trigger_vna(self, settings: dict[str, Any]) -> str:
        vna, display_name = self._command_device("vna")
        parameter = str(settings["parameter"]).strip().upper()
        vna.trigger_sweep(parameter)
        response = f"OK: triggered {parameter}"
        self._command_response = response
        self.command_response_changed.emit(response)
        self._append_log("INFO", "vna", display_name, response)
        return response

    def sample_vna(self, settings: dict[str, Any]) -> str:
        vna, display_name = self._command_device("vna")
        parameter = str(settings["parameter"]).strip().upper()
        measure = getattr(vna, "measure_s_parameter", None)
        trace = measure(parameter) if callable(measure) else vna.read_s_parameter(parameter)
        points = len(trace.frequency_hz)
        start_ghz = float(trace.frequency_hz[0]) / 1e9 if points else 0.0
        stop_ghz = float(trace.frequency_hz[-1]) / 1e9 if points else 0.0
        response = f"OK: sampled {trace.parameter}, {points} pts, {start_ghz:.3f}-{stop_ghz:.3f} GHz"
        self._command_response = response
        self.command_response_changed.emit(response)
        self._append_log("INFO", "vna", display_name, response)
        return response

    def configure_signal_generator(self, settings: dict[str, Any]) -> str:
        frequency_hz = float(settings["frequency_ghz"]) * 1e9
        power_dbm = float(settings["power_dbm"])
        output_enabled = bool(settings.get("output_enabled", False))
        output_state = "ON" if output_enabled else "OFF"
        commands = (
            f"FREQuency:CW {frequency_hz:.12g}",
            f"POWer:LEVel {power_dbm:.12g}",
            f"OUTPut:STATe {output_state}",
        )
        self._send_device_command_sequence("signal_generator", "signal_generator", commands)
        response = f"OK: SG {frequency_hz:.12g} Hz, {power_dbm:.1f} dBm, output {output_state}"
        self._command_response = response
        self.command_response_changed.emit(response)
        self._append_log("INFO", "signal_generator", "信号源", response)
        return response

    def configure_spectrum_analyzer(self, settings: dict[str, Any]) -> str:
        center_hz = float(settings["center_ghz"]) * 1e9
        span_hz = float(settings["span_mhz"]) * 1e6
        points = int(settings["points"])
        rbw_hz = float(settings["rbw_hz"])
        vbw_hz = float(settings["vbw_hz"])
        reference_level_dbm = float(settings["reference_level_dbm"])
        attenuation_db = float(settings["attenuation_db"])
        commands = (
            "INSTrument:SELect SA",
            "CONFigure:SANalyzer",
            f"FREQuency:CENTer {center_hz:.12g}",
            f"FREQuency:SPAN {span_hz:.12g}",
            f"SWEep:POINts {points}",
            f"BANDwidth:RESolution {rbw_hz:.12g}",
            f"BANDwidth:VIDeo {vbw_hz:.12g}",
            f"DISPlay:WINDow:TRACe:Y:RLEVel {reference_level_dbm:.12g}",
            f"POWer:ATTenuation {attenuation_db:.12g}",
        )
        self._send_device_command_sequence("spectrum_analyzer", "spectrum_analyzer", commands)
        response = (
            f"OK: SA center {center_hz:.12g} Hz, span {span_hz:.12g} Hz, "
            f"{points} pts, RBW {rbw_hz:.12g} Hz, VBW {vbw_hz:.12g} Hz"
        )
        self._command_response = response
        self.command_response_changed.emit(response)
        self._append_log("INFO", "spectrum_analyzer", "频谱仪", response)
        return response

    def preset_command(self, preset: str) -> str:
        return self.device_preset_command("link_box", preset)

    def device_preset_command(self, device: str, preset: str) -> str:
        presets = self.device_command_presets()[device]
        return presets[preset]

    def device_command_presets(self) -> dict[str, dict[str, str]]:
        presets = {
            "vna": {
                "*IDN?": "*IDN?",
                "清状态": "*CLS",
                "停止扫描": "ABOR",
                "查询错误": "SYST:ERR?",
                "设置起频": "SENS:FREQ:STAR 10GHz",
                "设置止频": "SENS:FREQ:STOP 17GHz",
                "设置点数": "SENS:SWE:POIN 71",
                "设置功率": "SOUR:POW -10",
                "N5245B 端口1功率": "SOUR1:POW1:LEV:IMM:AMPL -10",
                "N5245B 端口2功率": "SOUR1:POW2:LEV:IMM:AMPL -10",
                "设置 IFBW": "SENS:BAND:RES 1000",
                "配置 S21": "CALC1:PAR:DEF:EXT 'CH1_SPARAM','S21'",
                "选择轨迹": "CALC1:PAR:SEL 'CH1_SPARAM'",
                "关闭连续扫描": "SENS1:SWE:MODE HOLD",
                "立即触发": "SENS1:SWE:MODE SING",
                "N5245B 关闭连续扫描": "INIT1:CONT OFF",
                "N5245B INIT 触发": "INIT1:IMM",
                "单次扫描": "SENS1:SWE:MODE SING",
                "保持扫描": "SENS1:SWE:MODE HOLD",
                "连续扫描": "SENS1:SWE:MODE CONT",
                "触发源 IMM": "TRIG:SOUR IMM",
                "等待完成": "*OPC?",
                "查询扫时": "SENS1:SWE:TIME?",
                "二进制 REAL64": "FORM:DATA REAL,64",
                "字节序 SWAP": "FORM:BORD SWAP",
                "ASCII 数据": "FORM:DATA ASC,0",
                "读取 SDATA": "CALC1:DATA? SDATA",
                "读取 FDATA": "CALC1:DATA? FDATA",
            },
            "signal_generator": {
                "*IDN?": "*IDN?",
                "清状态": "*CLS",
                "查询错误": "SYSTem:ERRor?",
                "设置频率": "FREQuency:CW 10GHz",
                "查询频率": "FREQuency:CW?",
                "设置功率": "POWer:LEVel -10dBm",
                "查询功率": "POWer:LEVel?",
                "打开输出": "OUTPut:STATe ON",
                "关闭输出": "OUTPut:STATe OFF",
                "查询输出": "OUTPut:STATe?",
            },
            "link_box": {
                **self._link_box_command_presets(),
            },
            "spectrum_analyzer": {
                "*IDN?": "*IDN?",
                "清状态": "*CLS",
                "查询错误": "SYSTem:ERRor?",
                "选择频谱模式": "INSTrument:SELect SA",
                "配置频谱测量": "CONFigure:SANalyzer",
                "设置中心频率": "FREQuency:CENTer 10GHz",
                "查询中心频率": "FREQuency:CENTer?",
                "设置 Span": "FREQuency:SPAN 100MHz",
                "查询 Span": "FREQuency:SPAN?",
                "设置起频": "FREQuency:STARt 9.95GHz",
                "设置止频": "FREQuency:STOP 10.05GHz",
                "设置点数": "SWEep:POINts 1001",
                "设置 RBW": "BANDwidth:RESolution 1MHz",
                "查询 RBW": "BANDwidth:RESolution?",
                "设置 VBW": "BANDwidth:VIDeo 1MHz",
                "查询 VBW": "BANDwidth:VIDeo?",
                "设置参考电平": "DISPlay:WINDow:TRACe:Y:RLEVel 0dBm",
                "设置衰减": "POWer:ATTenuation 10",
                "立即测量": "INITiate:IMMediate",
                "读取频谱数据": "READ:SANalyzer?",
                "峰值搜索": "CALCulate:MARKer1:MAXimum",
                "读取 Marker 频率": "CALCulate:MARKer1:X?",
                "读取 Marker 幅度": "CALCulate:MARKer1:Y?",
            },
        }
        return presets

    def _link_box_command_presets(self) -> dict[str, str]:
        quiet_zone_commands = (
            "CONFigure:LINK DUT, AMP1, SA",
            "CONFigure:LINK DUT, VNA2",
            "CONFigure:LINK DUT, AMP1, VNA2",
            "CONFigure:LINK H, SG",
            "CONFigure:LINK H, VNA1",
            "CONFigure:LINK H, SA",
            "CONFigure:LINK H, AMP2, SG",
            "CONFigure:LINK H, AMP2, VNA1",
            "CONFigure:LINK H, AMP2, SA",
            "CONFigure:LINK V, SG",
            "CONFigure:LINK V, VNA1",
            "CONFigure:LINK V, SA",
            "CONFigure:LINK V, AMP2, SG",
            "CONFigure:LINK V, AMP2, VNA1",
            "CONFigure:LINK V, AMP2, SA",
        )
        calibration_commands = tuple(
            command
            for item in self.catalog.items
            for step in item.steps
            for command in step.link_commands
        )
        utility_commands = (
            "*IDN?",
            "*OPC?",
            "SYSTem:ERRor:COUNt?",
            "SYSTem:ERRor:NEXT?",
        )
        commands = self._unique_commands((*quiet_zone_commands, *calibration_commands, *utility_commands))
        return {self._link_box_command_label(command): command for command in commands}

    @staticmethod
    def _unique_commands(commands: tuple[str, ...]) -> tuple[str, ...]:
        seen: set[str] = set()
        unique: list[str] = []
        for command in commands:
            normalized = command.strip()
            key = normalized.upper().replace(" ", "")
            if normalized and key not in seen:
                seen.add(key)
                unique.append(normalized)
        return tuple(unique)

    @staticmethod
    def _unique_texts(values: tuple[str, ...]) -> tuple[str, ...]:
        seen: set[str] = set()
        unique: list[str] = []
        for value in values:
            text = str(value).strip()
            key = text.upper()
            if text and key not in seen:
                seen.add(key)
                unique.append(text)
        return tuple(unique)

    @staticmethod
    def _link_box_command_label(command: str) -> str:
        normalized = command.strip()
        if not normalized.upper().startswith("CONFIGURE:LINK"):
            return normalized
        route = normalized.split(" ", 1)[1] if " " in normalized else normalized
        return route.replace(",", " ->").replace("  ", " ").strip()

    def refresh_overview(self) -> None:
        item = self.selected_item
        if item is None:
            self._overview = {
                "item_id": "",
                "item_name": "未加载链路配置",
                "purpose": "请先导入链路配置或导入默认配置。",
                "steps": 0,
                "selected_step_id": "",
                "link_box_connected": self._mock_link_box.is_connected,
                "vna_connected": self._mock_vna.is_connected,
                "signal_generator_connected": self._mock_signal_generator.is_connected,
                "spectrum_analyzer_connected": self._mock_spectrum_analyzer.is_connected,
                "status": "Ready",
            }
            self.overview_changed.emit(self._overview)
            return
        run_summary = self._run_summaries_by_item.get(item.id, {})
        self._overview = {
            "item_id": item.id,
            "item_name": item.name,
            "purpose": item.purpose,
            "steps": len(item.steps),
            "selected_step_id": self.selected_step.id if self.selected_step else "",
            "link_box_connected": self._mock_link_box.is_connected,
            "vna_connected": self._mock_vna.is_connected,
            "signal_generator_connected": self._mock_signal_generator.is_connected,
            "spectrum_analyzer_connected": self._mock_spectrum_analyzer.is_connected,
            "status": self._overview_status_for(item.id),
            **({"run_summary": run_summary} if run_summary else {}),
        }
        self.overview_changed.emit(self._overview)

    def _overview_status_for(self, item_id: str) -> str:
        if item_id in self._run_status_by_item:
            return self._run_status_by_item[item_id]
        if self._active_run_item_id == item_id:
            return self._status_text
        return "Ready"

    def _command_device(self, device: str) -> tuple[Any, str]:
        devices = {
            "vna": (self._mock_vna, "网分"),
            "signal_generator": (self._mock_signal_generator, "信号源"),
            "link_box": (self._mock_link_box, "链路箱"),
            "spectrum_analyzer": (self._mock_spectrum_analyzer, "频谱仪"),
        }
        try:
            return devices[device]
        except KeyError as exc:
            raise ValueError(f"Unknown command device: {device}") from exc

    def _device_display_name(self, device: str) -> str:
        return self._command_device(device)[1]

    def _set_device(self, device: str, instrument: Any) -> None:
        if device == "vna":
            self._mock_vna = instrument
        elif device == "signal_generator":
            self._mock_signal_generator = instrument
        elif device == "link_box":
            self._mock_link_box = instrument
        elif device == "spectrum_analyzer":
            self._mock_spectrum_analyzer = instrument
        else:
            raise ValueError(f"Unknown command device: {device}")

    def _create_device(self, device: str) -> Any:
        config = self._device_configs[device]
        if device == "vna":
            return (
                MockVna(resource=config.resource, model=config.model)
                if config.use_mock
                else PyVisaVna(resource=config.resource, model=config.model, timeout_ms=config.timeout_ms)
            )
        if device == "link_box":
            return (
                MockLinkBox(resource=config.resource, model=config.model)
                if config.use_mock
                else Lcd74000fLinkBox(resource=config.resource, model=config.model, timeout_ms=config.timeout_ms)
            )
        if device == "signal_generator":
            return (
                MockScpiInstrument("SG", config.model, resource=config.resource)
                if config.use_mock
                else PyVisaScpiInstrument(resource=config.resource, model=config.model, timeout_ms=config.timeout_ms)
            )
        if device == "spectrum_analyzer":
            return (
                MockScpiInstrument("SA", config.model, resource=config.resource)
                if config.use_mock
                else PyVisaScpiInstrument(resource=config.resource, model=config.model, timeout_ms=config.timeout_ms)
            )
        raise ValueError(f"Unknown command device: {device}")

    def _on_prompt_ready(self, prompt: StepViewData) -> None:
        self._update_run_progress(prompt)
        self._selected_step_index = max(prompt.step_index - 1, 0)
        self._run_status_by_item[prompt.item_id] = prompt.status
        self.selected_step_changed.emit()
        self.step_view_changed.emit(prompt)
        self._append_log("INFO", "runner", prompt.item_name, f"步骤确认提示: {prompt.step_id}")
        self.refresh_overview()

    def _update_run_progress(self, prompt: StepViewData) -> None:
        item = self.catalog.get(prompt.item_id)
        completed_total = prompt.item_completed_substeps
        if completed_total <= 0 and prompt.step_index > 0:
            completed_total = sum(len(self._substeps_for_step(step)) for step in item.steps[: max(prompt.step_index - 1, 0)])
            if prompt.confirm_phase == "saved":
                completed_total += prompt.substep_index
            else:
                completed_total += max(0, prompt.substep_index - 1)
        completed_substep_ids: list[str] = []
        completed_step_ids: list[str] = []
        remaining_completed = max(0, completed_total)
        for item_step in item.steps:
            substeps = self._substeps_for_step(item_step)
            completed_count = min(len(substeps), remaining_completed)
            completed_substep_ids.extend(f"{item_step.id}:{substep.id}" for substep in substeps[:completed_count])
            if substeps and completed_count >= len(substeps):
                completed_step_ids.append(item_step.id)
            remaining_completed = max(0, remaining_completed - len(substeps))
        self._run_summaries_by_item[prompt.item_id] = {
            "item_id": prompt.item_id,
            "item_name": prompt.item_name,
            "state": prompt.status,
            "total_steps": prompt.step_total,
            "completed_big_steps": len(completed_step_ids),
            "completed_step_ids": tuple(completed_step_ids),
            "completed_steps": len(completed_substep_ids),
            "completed_substep_ids": tuple(completed_substep_ids),
            "active_step_id": prompt.step_id,
            "active_substep_id": prompt.substep_id,
            "active_confirm_phase": prompt.confirm_phase,
        }

    def _on_finished_summary(self, summary: object) -> None:
        run_summary = dict(summary)
        selected_item = self.selected_item
        item_id = str(run_summary.get("item_id") or self._active_run_item_id or (selected_item.id if selected_item else ""))
        item_name = str(run_summary.get("item_name") or (selected_item.name if selected_item else "未加载链路配置"))
        self._run_summaries_by_item[item_id] = run_summary
        self._run_status_by_item[item_id] = "Calibration completed"
        self.status_text_update("Calibration completed")
        self._append_log("INFO", "runner", item_name, "校准完成")
        self.refresh_overview()
        self.run_finished.emit(run_summary)

    def _on_worker_error(self, message: str) -> None:
        selected_item = self.selected_item
        item_id = self._active_run_item_id or (selected_item.id if selected_item else "")
        self._run_status_by_item[item_id] = f"Error: {message}"
        self._append_log("ERROR", "runner", selected_item.name if selected_item else "未加载链路配置", message)
        self.status_text_update(f"Error: {message}")
        self.refresh_overview()

    def _cleanup_worker(self) -> None:
        self._worker = None
        self._active_run_item_id = ""
        self.refresh_overview()

    def _append_log(self, level: str, source: str, name: str, message: str) -> None:
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"),
            level=level.upper(),
            source=source,
            name=name,
            message=message,
        )
        self._logs.append(entry)
        self.logs_changed.emit()

    def clear_logs(self) -> None:
        self._logs.clear()
        self.logs_changed.emit()

    def filtered_logs(self, *, level: str = "ALL", keyword: str = "") -> list[LogEntry]:
        keyword = keyword.strip().lower()
        level = level.strip().upper()
        records = self._logs
        if level and level != "ALL":
            if level == "WARN":
                level = "WARNING"
            records = [record for record in records if record.level == level]
        if keyword:
            records = [
                record
                for record in records
                if keyword in record.message.lower()
                or keyword in record.source.lower()
                or keyword in record.name.lower()
                or keyword in record.timestamp.lower()
            ]
        return records

    def _step_view_data(self, step, index: int, total: int) -> StepViewData:
        item = self.selected_item
        if item is None:
            raise RuntimeError("请先导入链路配置或导入默认配置。")
        substeps = self.substep_view_data(step)
        item_total_substeps = sum(len(self._substeps_for_step(item_step)) for item_step in item.steps)
        run_summary = self._run_summaries_by_item.get(item.id, {})
        item_completed_substeps = len({str(step_id) for step_id in run_summary.get("completed_substep_ids", ())})
        return StepViewData(
            item_id=item.id,
            item_name=item.name,
            step_id=step.id,
            step_name=step.name,
            step_index=index,
            step_total=total,
            status=self._overview_status_for(item.id),
            manual_instruction=step.manual_instruction,
            route_ids=step.route_ids,
            link_commands=step.link_commands,
            input_port=step.input_port,
            output_port=step.output_port,
            raw_outputs=step.raw_outputs,
            final_outputs=step.final_outputs,
            required_inputs=step.required_inputs,
            notes=step.notes,
            substep_total=len(substeps),
            item_total_substeps=item_total_substeps,
            item_completed_substeps=item_completed_substeps,
            path_template=step.path_template,
            path=step.path,
        )

    def substep_view_data(self, step: CalibrationStep) -> list[SubStepViewData]:
        return [
            SubStepViewData(
                id=substep.id,
                name=substep.name,
                input_port=substep.input_port,
                output_port=substep.output_port,
                manual_instruction=substep.manual_instruction,
                route_ids=substep.route_ids,
                link_commands=substep.link_commands,
                raw_output=substep.raw_output,
                final_output=substep.final_output,
                required_inputs=substep.required_inputs,
                notes=substep.notes,
                path_template=substep.path_template or step.path_template,
                path=substep.path or step.path,
            )
            for substep in self._substeps_for_step(step)
        ]

    def _total_substeps_for_item(self, item_id: str) -> int:
        item = self.catalog.get(item_id)
        return sum(len(self._substeps_for_step(step)) for step in item.steps)

    def _substeps_for_step(self, step: CalibrationStep) -> tuple[CalibrationSubStep, ...]:
        if step.substeps:
            return tuple(sorted(step.substeps, key=self._substep_order_key))
        raw_outputs = step.raw_outputs or (f"{step.id}_RAW",)
        substeps = []
        for index, raw_output in enumerate(raw_outputs):
            final_output = step.final_outputs[index] if index < len(step.final_outputs) else ""
            commands = (step.link_commands[index],) if len(step.link_commands) == len(raw_outputs) else step.link_commands
            route_ids = (step.route_ids[index],) if len(step.route_ids) == len(raw_outputs) else step.route_ids
            substeps.append(
                CalibrationSubStep(
                    id=self._safe_token(raw_output),
                    name=raw_output,
                    input_port=step.input_port,
                    output_port=step.output_port,
                    manual_instruction=step.manual_instruction,
                    route_ids=route_ids,
                    link_commands=commands,
                    raw_output=raw_output,
                    final_output=final_output,
                    required_inputs=step.required_inputs,
                    notes=step.notes,
                    path_template=step.path_template,
                    path=step.path,
                )
            )
        return tuple(substeps)

    @staticmethod
    def _substep_order_key(substep: CalibrationSubStep) -> tuple[int, int]:
        token = substep.id.upper()
        if token.startswith("V-") or token.startswith("V_") or token == "V":
            return (0, 0)
        if token.startswith("H-") or token.startswith("H_") or token == "H":
            return (1, 0)
        return (0, 1)

    @staticmethod
    def _safe_token(value: str) -> str:
        return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip()) or "MEAS"

    def status_text_update(self, text: str) -> None:
        self._status_text = text
        self.status_changed.emit(text)
