from __future__ import annotations

import threading
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal

from catr_loss_calibrator.calibration.definitions import default_calibration_catalog
from catr_loss_calibrator.calibration.mock_runner import MockCalibrationRunner
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockScpiInstrument, MockVna
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


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    level: str
    source: str
    name: str
    message: str


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

    def confirm_step(self, step, index: int, total: int) -> str:
        prompt = StepViewData(
            item_id=self._runner.item.id,
            item_name=self._runner.item.name,
            step_id=step.id,
            step_name=step.name,
            step_index=index,
            step_total=total,
            status=self._runner.state_machine.state.value,
            manual_instruction=step.manual_instruction,
            route_ids=step.route_ids,
            link_commands=step.link_commands,
            input_port=step.input_port,
            output_port=step.output_port,
            raw_outputs=step.raw_outputs,
            final_outputs=step.final_outputs,
            required_inputs=step.required_inputs,
            notes=step.notes,
        )
        self._active_prompt = prompt
        self.prompt_ready.emit(prompt)
        self.state_changed.emit("WAIT_MANUAL_CONFIRM")
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

    def __init__(self) -> None:
        super().__init__()
        self.catalog = default_calibration_catalog()
        self._selected_index = 0
        self._selected_step_index = 0
        self._logs: list[LogEntry] = []
        self._overview: dict[str, object] = {}
        self._run_summary: dict[str, object] = {}
        self._status_text = "Ready"
        self._command_response = ""
        self._worker: CalibrationRunWorker | None = None
        self._mock_link_box = MockLinkBox()
        self._mock_vna = MockVna()
        self._mock_signal_generator = MockScpiInstrument("SG", "MOCK-SG")
        self._mock_spectrum_analyzer = MockScpiInstrument("SA", "MOCK-SA")
        self._command_history: list[str] = []

    @property
    def selected_item(self):
        return self.catalog.items[self._selected_index]

    @property
    def selected_step(self):
        steps = self.selected_item.steps
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

    def select_item(self, index: int) -> None:
        if 0 <= index < len(self.catalog.items):
            self._selected_index = index
            self.selected_item_changed.emit()
            self.select_step(0)
            self.refresh_overview()

    def select_step(self, index: int) -> None:
        steps = self.selected_item.steps
        if not steps:
            self._selected_step_index = 0
            self.selected_step_changed.emit()
            return
        if 0 <= index < len(steps):
            self._selected_step_index = index
            self.selected_step_changed.emit()
            self._append_log("INFO", "ui", self.selected_item.name, f"切换到步骤 {steps[index].id}")
            self.step_view_changed.emit(self._step_view_data(steps[index], index + 1, len(steps)))

    def connect_mock_devices(self) -> None:
        self._mock_link_box.connect()
        self._mock_vna.connect()
        self._mock_signal_generator.connect()
        self._mock_spectrum_analyzer.connect()
        self._status_text = "Mock devices connected"
        self.status_changed.emit(self._status_text)
        self._append_log("INFO", "device", "mock", "Mock 设备已连接")
        self.refresh_overview()

    def disconnect_mock_devices(self) -> None:
        self._mock_link_box.disconnect()
        self._mock_vna.disconnect()
        self._mock_signal_generator.disconnect()
        self._mock_spectrum_analyzer.disconnect()
        self._status_text = "Mock devices disconnected"
        self.status_changed.emit(self._status_text)
        self._append_log("INFO", "device", "mock", "Mock 设备已断开")
        self.refresh_overview()

    def start_selected(self) -> None:
        if self._worker and self._worker.isRunning():
            self._append_log("runner already running")
            return
        item = self.selected_item
        runner = MockCalibrationRunner(
            item=item,
            vna=self._mock_vna,
            link_box=self._mock_link_box,
            output_root=Path("catr_loss_calibrator_output"),
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
        if self._worker and self._worker.isRunning():
            self._append_log("INFO", "ui", self.selected_item.name, f"用户操作: {action}")
            self._worker.submit_action(action)
        else:
            self._append_log("WARNING", "ui", self.selected_item.name, f"忽略操作: {action}")

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

    def preset_command(self, preset: str) -> str:
        return self.device_preset_command("link_box", preset)

    def device_preset_command(self, device: str, preset: str) -> str:
        presets = self.device_command_presets()[device]
        return presets[preset]

    def device_command_presets(self) -> dict[str, dict[str, str]]:
        presets = {
            "vna": {
                "*IDN?": "*IDN?",
                "配置 S21": "CALCulate:PARameter:DEFine 'Meas1',S21",
                "触发扫描": "INITiate:IMMediate",
                "读取轨迹": "CALCulate:DATA? FDATA",
            },
            "signal_generator": {
                "*IDN?": "*IDN?",
                "设置频率": "FREQuency:CW 10GHz",
                "设置功率": "POWer:LEVel -10dBm",
                "打开输出": "OUTPut:STATe ON",
            },
            "link_box": {
                "H_TO_VNA1": link_command("H", "VNA1"),
                "V_TO_VNA1": link_command("V", "VNA1"),
                "DUT_TO_VNA2": link_command("DUT", "VNA2"),
                "DUT_AMP1_VNA2": link_command("DUT", "AMP1", "VNA2"),
                "DUT_TO_SA": link_command("DUT", "SA"),
                "HV_AMP2_SA": "CONFigure:LINK H/V, AMP2, SA",
            },
            "spectrum_analyzer": {
                "*IDN?": "*IDN?",
                "设置中心频率": "FREQuency:CENTer 10GHz",
                "设置 Span": "FREQuency:SPAN 100MHz",
                "读取峰值": "CALCulate:MARKer1:Y?",
            },
        }
        return presets

    def refresh_overview(self) -> None:
        item = self.selected_item
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
            "status": self._status_text,
            **({"run_summary": self._run_summary} if self._run_summary else {}),
        }
        self.overview_changed.emit(self._overview)

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

    def _on_prompt_ready(self, prompt: StepViewData) -> None:
        self._selected_step_index = max(prompt.step_index - 1, 0)
        self.step_view_changed.emit(prompt)
        self.selected_step_changed.emit()
        self._append_log("INFO", "runner", prompt.item_name, f"步骤确认提示: {prompt.step_id}")

    def _on_finished_summary(self, summary: object) -> None:
        self._run_summary = dict(summary)
        self.status_text_update("Calibration completed")
        self._append_log("INFO", "runner", self.selected_item.name, "校准完成")
        self.refresh_overview()

    def _on_worker_error(self, message: str) -> None:
        self._append_log("ERROR", "runner", self.selected_item.name, message)
        self.status_text_update(f"Error: {message}")

    def _cleanup_worker(self) -> None:
        self._worker = None
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
        return StepViewData(
            item_id=self.selected_item.id,
            item_name=self.selected_item.name,
            step_id=step.id,
            step_name=step.name,
            step_index=index,
            step_total=total,
            status=self._status_text,
            manual_instruction=step.manual_instruction,
            route_ids=step.route_ids,
            link_commands=step.link_commands,
            input_port=step.input_port,
            output_port=step.output_port,
            raw_outputs=step.raw_outputs,
            final_outputs=step.final_outputs,
            required_inputs=step.required_inputs,
            notes=step.notes,
        )

    def status_text_update(self, text: str) -> None:
        self._status_text = text
        self.status_changed.emit(text)
