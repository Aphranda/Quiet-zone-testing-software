from __future__ import annotations

import threading
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal

from catr_loss_calibrator.calibration.config_loader import load_calibration_catalog
from catr_loss_calibrator.calibration.definitions import default_calibration_catalog
from catr_loss_calibrator.calibration.models import CalibrationCatalog, CalibrationStep, CalibrationSubStep
from catr_loss_calibrator.calibration.mock_runner import MockCalibrationRunner
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockScpiInstrument, MockVna
from catr_loss_calibrator.hardware.link_box.lcd74000f import Lcd74000fLinkBox
from catr_loss_calibrator.hardware.scpi import PyVisaScpiInstrument
from catr_loss_calibrator.hardware.vna.pyvisa_vna import PyVisaVna
from catr_loss_calibrator.instrument_management.models import InstrumentConnectionConfig
from catr_loss_calibrator.link_management.link_templates import link_command


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
    log_message = Signal(str)
    state_changed = Signal(str)
    finished_summary = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, runner: MockCalibrationRunner) -> None:
        super().__init__()
        self._runner = runner
        self._action_lock = threading.Condition()
        self._pending_action: str | None = None
        self._active_prompt: StepViewData | None = None

    def run(self) -> None:  # pragma: no cover - Qt thread
        try:
            self.state_changed.emit(self._runner.state_machine.state.value)
            self._runner.run()
            self.log_message.emit(f"run complete: {self._runner.item.id}")
            self.finished_summary.emit(self._runner.overview())
        except Exception as exc:  # pragma: no cover - Qt thread
            self.error_occurred.emit(str(exc))

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
        self._command_history: list[str] = []
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

    @property
    def command_history(self) -> list[str]:
        return list(self._command_history)

    def load_default_catalog(self) -> None:
        self._replace_catalog(default_calibration_catalog(), "已导入默认链路配置")

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
        if self._worker and self._worker.isRunning():
            self._append_log("runner already running")
            return
        item = self.selected_item
        if item is None:
            raise RuntimeError("请先导入链路配置或导入默认配置。")
        self._run_summaries_by_item.pop(item.id, None)
        self._run_status_by_item[item.id] = f"Running {item.id}"
        self._active_run_item_id = item.id
        runner = MockCalibrationRunner(
            item=item,
            vna=self._mock_vna,
            link_box=self._mock_link_box,
            output_root=Path("catr_loss_calibrator_output"),
            vna_settings=dict(vna_settings or {}),
        )
        worker = CalibrationRunWorker(runner)
        worker.prompt_ready.connect(self._on_prompt_ready)
        worker.log_message.connect(self._append_log)
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

    def submit_action(self, action: str) -> None:
        item_name = self.selected_item.name if self.selected_item is not None else "未加载链路配置"
        if self._worker and self._worker.isRunning():
            self._append_log("INFO", "ui", item_name, f"用户操作: {action}")
            self._worker.submit_action(action)
        else:
            self._append_log("WARNING", "ui", item_name, f"忽略操作: {action}")

    def send_command(self, command: str) -> str:
        return self.send_device_command("link_box", command)

    def send_device_command(self, device: str, command: str) -> str:
        command = command.strip()
        if not command:
            raise ValueError("Command is empty.")
        instrument, display_name = self._command_device(device)
        response = instrument.send_command(command)
        self._command_history.append(f"{display_name}> {command}\n{response}")
        self._command_response = response
        self.command_response_changed.emit(response)
        self._append_log("INFO", "command", display_name, f"发送命令: {command}")
        self._append_log("INFO", "command", display_name, f"返回响应: {response}")
        return response

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
                "设置 IFBW": "SENS:BAND:RES 1000",
                "配置 S21": "CALC1:PAR:DEF:EXT 'CH1_SPARAM','S21'",
                "选择轨迹": "CALC1:PAR:SEL 'CH1_SPARAM'",
                "单次扫描": "SENS1:SWE:MODE SING",
                "保持扫描": "SENS1:SWE:MODE HOLD",
                "连续扫描": "SENS1:SWE:MODE CONT",
                "触发源 IMM": "TRIG:SOUR IMM",
                "等待完成": "*OPC?",
                "查询扫时": "SENS1:SWE:TIME?",
                "读取 SDATA": "CALC:DATA? SDATA",
            },
            "signal_generator": {
                "*IDN?": "*IDN?",
                "设置频率": "FREQuency:CW 10GHz",
                "设置功率": "POWer:LEVel -10dBm",
                "打开输出": "OUTPut:STATe ON",
            },
            "link_box": {
                **self._link_box_command_presets(),
            },
            "spectrum_analyzer": {
                "*IDN?": "*IDN?",
                "设置中心频率": "FREQuency:CENTer 10GHz",
                "设置 Span": "FREQuency:SPAN 100MHz",
                "读取峰值": "CALCulate:MARKer1:Y?",
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

    def filtered_logs(self, *, level: str = "ALL", keyword: str = "") -> list[LogEntry]:
        keyword = keyword.strip().lower()
        level = level.strip().upper()
        records = self._logs
        if level and level != "ALL":
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
