from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from catr_loss_calibrator.calibration.models import CalibrationItem, CalibrationStep, MeasurementRole
from catr_loss_calibrator.calibration.state_machine import CalibrationState, CalibrationStateMachine
from catr_loss_calibrator.hardware.interfaces import LinkBox, SParameterTrace, Vna
from catr_loss_calibrator.storage.loss_file_storage import save_loss_record_with_policy
from catr_loss_calibrator.storage.metadata_writer import write_metadata
from catr_loss_calibrator.storage.models import MetadataRecord
from catr_loss_calibrator.storage.raw_trace_storage import trace_record_from_sparameter


@dataclass
class MockCalibrationRunner:
    item: CalibrationItem
    vna: Vna
    link_box: LinkBox
    output_root: Path
    confirm_step: Callable[[CalibrationStep, int, int], str] | None = None
    state_machine: CalibrationStateMachine = field(default_factory=CalibrationStateMachine)
    events: list[str] = field(default_factory=list)

    def run(self) -> list[str]:
        self._ensure_ready()
        if self.state_machine.state not in {CalibrationState.IDLE, CalibrationState.DONE, CalibrationState.CANCELLED}:
            raise RuntimeError(f"Runner is busy in state {self.state_machine.state.value}")
        self.events.append(f"start:{self.item.id}")
        if self.state_machine.state == CalibrationState.IDLE:
            self.state_machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM)
        for index, step in enumerate(self.item.steps):
            action = self._confirm_step(step, index + 1, len(self.item.steps))
            if action == "cancel":
                self.state_machine.transition(CalibrationState.CANCELLED)
                self.events.append(f"cancel:{step.id}")
                return self.events
            if action == "skip":
                self.events.append(f"skip:{step.id}")
                continue
            self._run_step(step)
            if index < len(self.item.steps) - 1:
                self.state_machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM)
        self.state_machine.transition(CalibrationState.DONE)
        self.events.append(f"done:{self.item.id}")
        return self.events

    def overview(self) -> dict[str, object]:
        return {
            "item_id": self.item.id,
            "item_name": self.item.name,
            "state": self.state_machine.state.value,
            "total_steps": len(self.item.steps),
            "completed_steps": sum(1 for event in self.events if event.startswith(("raw:", "skip:", "cancel:"))),
            "link_box_connected": self.link_box.is_connected,
            "vna_connected": self.vna.is_connected,
            "last_event": self.events[-1] if self.events else "",
        }

    def format_step_status(self, step: CalibrationStep, index: int, total: int) -> str:
        return (
            f"[{index}/{total}] {step.id} - {step.name}\n"
            f"  状态: {self.state_machine.state.value}\n"
            f"  接线说明: {step.manual_instruction or 'None'}\n"
            f"  链路命令: {', '.join(step.link_commands) or 'None'}\n"
            f"  输入端口: {step.input_port or 'None'}\n"
            f"  输出端口: {step.output_port or 'None'}"
        )

    def _confirm_step(self, step: CalibrationStep, index: int, total: int) -> str:
        if self.confirm_step is None:
            return "continue"
        action = self.confirm_step(step, index, total).strip().lower()
        if action not in {"continue", "skip", "retry", "cancel"}:
            raise ValueError(f"Unsupported action: {action}")
        if action == "retry":
            return self._confirm_step(step, index, total)
        return action

    def _run_step(self, step: CalibrationStep) -> None:
        self.state_machine.transition(CalibrationState.CONFIGURE_LINK)
        for command in step.link_commands:
            self.link_box.send_command(command)
            self.events.append(f"link:{step.id}:{command}")

        self.state_machine.transition(CalibrationState.CONFIGURE_VNA)
        self.vna.configure_sweep(10e9, 15e9, 51)
        self.vna.configure_power(-10.0)
        self.vna.configure_if_bandwidth(1000.0)

        self.state_machine.transition(CalibrationState.TRIGGER_SWEEP)
        self.vna.trigger_sweep()

        self.state_machine.transition(CalibrationState.READ_TRACE)
        trace = self.vna.read_s_parameter()

        self.state_machine.transition(CalibrationState.SAVE_RAW)
        raw_record = trace_record_from_sparameter(trace, source_cal=self.item.id, source_step=step.id)
        raw_path = self.output_root / "raw" / f"{self.item.id}_{step.id}.csv"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        _save_trace_like_csv(raw_path, raw_record.parameter, raw_record.frequency_hz, raw_record.value_db, raw_record.source_cal)
        self.events.append(f"raw:{raw_path.name}")

        self.state_machine.transition(CalibrationState.COMPUTE_OUTPUT)
        self.state_machine.transition(CalibrationState.SAVE_OUTPUT)
        self._save_metadata(step, trace)

    def _save_metadata(self, step: CalibrationStep, trace: SParameterTrace) -> None:
        metadata = MetadataRecord(
            session_id=f"{self.item.id}-{step.id}",
            project_name="CATR Loss Calibrator",
            project_version="0.1.0",
            calibration_item=self.item.id,
            calibration_step=step.id,
            instrument_snapshot={"vna": getattr(self.vna, "__class__", type(self.vna)).__name__},
            link_commands=step.link_commands,
            manual_confirmation=True,
            input_files=(f"{self.item.id}_{step.id}.raw",),
            input_hashes=("mock",),
            output_files=(),
            output_hashes=(),
            formula_version="v1",
            profile_version="lcd74000f:v1",
            note="mock-runner",
        )
        metadata_path = self.output_root / "metadata" / f"{self.item.id}_{step.id}.json"
        write_metadata(metadata_path, metadata)
        self.events.append(f"metadata:{metadata_path.name}")

    def _ensure_ready(self) -> None:
        if not self.link_box.is_connected:
            raise RuntimeError("Link box must be connected before running calibration.")
        if not self.vna.is_connected:
            raise RuntimeError("VNA must be connected before running calibration.")


def _save_trace_like_csv(path: Path, parameter: str, frequency_hz, value_db, source_cal: str) -> None:
    from catr_loss_calibrator.storage.csv_storage import save_loss_csv

    save_loss_csv(
        path,
        frequency_hz=frequency_hz,
        value_db=value_db,
        param=parameter,
        band="RAW",
        feed="RAW",
        horn="RAW",
        source_cal=source_cal,
    )
