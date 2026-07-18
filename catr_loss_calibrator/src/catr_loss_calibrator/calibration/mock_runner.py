from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from catr_loss_calibrator.calibration.models import CalibrationItem, CalibrationStep, CalibrationSubStep, MeasurementRole
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
    confirm_step: Callable[[CalibrationStep, CalibrationSubStep, str, int, int, int, int], str] | None = None
    state_machine: CalibrationStateMachine = field(default_factory=CalibrationStateMachine)
    events: list[str] = field(default_factory=list)

    def run(self) -> list[str]:
        self._ensure_ready()
        if self.state_machine.state not in {CalibrationState.IDLE, CalibrationState.DONE, CalibrationState.CANCELLED}:
            raise RuntimeError(f"Runner is busy in state {self.state_machine.state.value}")
        self.events.append(f"start:{self.item.id}")
        if self.state_machine.state == CalibrationState.IDLE:
            self.state_machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM)
        for step_index, step in enumerate(self.item.steps):
            substeps = self._substeps_for(step)
            for substep_index, substep in enumerate(substeps):
                while True:
                    action = self._confirm_step(
                        step,
                        substep,
                        "start",
                        step_index + 1,
                        len(self.item.steps),
                        substep_index + 1,
                        len(substeps),
                    )
                    if action == "cancel":
                        self.state_machine.transition(CalibrationState.CANCELLED)
                        self.events.append(f"cancel:{step.id}:{substep.id}")
                        return self.events
                    if action == "skip":
                        self.events.append(f"skip:{step.id}:{substep.id}")
                        break

                    self._run_substep(step, substep)
                    self.state_machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM)
                    done_action = self._confirm_step(
                        step,
                        substep,
                        "saved",
                        step_index + 1,
                        len(self.item.steps),
                        substep_index + 1,
                        len(substeps),
                    )
                    if done_action == "cancel":
                        self.state_machine.transition(CalibrationState.CANCELLED)
                        self.events.append(f"cancel:{step.id}:{substep.id}")
                        return self.events
                    if done_action == "retry":
                        self.events.append(f"retry:{step.id}:{substep.id}")
                        continue
                    if done_action == "skip":
                        self.events.append(f"skip:{step.id}:{substep.id}")
                    break
        self.state_machine.transition(CalibrationState.DONE)
        self.events.append(f"done:{self.item.id}")
        return self.events

    def overview(self) -> dict[str, object]:
        completed_substep_ids = self._completed_substep_ids()
        completed_step_ids = tuple(
            step.id
            for step in self.item.steps
            if all(f"{step.id}:{substep.id}" in completed_substep_ids for substep in self._substeps_for(step))
        )
        return {
            "item_id": self.item.id,
            "item_name": self.item.name,
            "state": self.state_machine.state.value,
            "total_steps": len(self.item.steps),
            "total_substeps": sum(len(self._substeps_for(step)) for step in self.item.steps),
            "completed_steps": len(completed_substep_ids),
            "completed_big_steps": len(completed_step_ids),
            "completed_step_ids": completed_step_ids,
            "completed_substep_ids": tuple(sorted(completed_substep_ids)),
            "link_box_connected": self.link_box.is_connected,
            "vna_connected": self.vna.is_connected,
            "last_event": self.events[-1] if self.events else "",
        }

    def _completed_substep_ids(self) -> set[str]:
        completed: set[str] = set()
        event_set = set(self.events)
        for step in self.item.steps:
            for substep in self._substeps_for(step):
                substep_key = f"{step.id}:{substep.id}"
                raw_file = f"{self.item.id}_{step.id}_{self._safe_token(substep.id)}.csv"
                if f"raw:{raw_file}" in event_set or f"skip:{substep_key}" in event_set:
                    completed.add(substep_key)
        return completed

    def format_step_status(self, step: CalibrationStep, index: int, total: int) -> str:
        return (
            f"[{index}/{total}] {step.id} - {step.name}\n"
            f"  状态: {self.state_machine.state.value}\n"
            f"  接线说明: {step.manual_instruction or 'None'}\n"
            f"  链路命令: {', '.join(step.link_commands) or 'None'}\n"
            f"  输入端口: {step.input_port or 'None'}\n"
            f"  输出端口: {step.output_port or 'None'}"
        )

    def _confirm_step(
        self,
        step: CalibrationStep,
        substep: CalibrationSubStep,
        phase: str,
        step_index: int,
        step_total: int,
        substep_index: int,
        substep_total: int,
    ) -> str:
        if self.confirm_step is None:
            return "continue"
        action = self.confirm_step(step, substep, phase, step_index, step_total, substep_index, substep_total).strip().lower()
        if action not in {"continue", "skip", "retry", "cancel"}:
            raise ValueError(f"Unsupported action: {action}")
        if phase == "start" and action == "retry":
            return self._confirm_step(step, substep, phase, step_index, step_total, substep_index, substep_total)
        return action

    def _run_substep(self, step: CalibrationStep, substep: CalibrationSubStep) -> None:
        self.state_machine.transition(CalibrationState.CONFIGURE_LINK)
        for command in substep.link_commands:
            self.link_box.send_command(command)
            self.events.append(f"link:{step.id}:{substep.id}:{command}")

        self.state_machine.transition(CalibrationState.CONFIGURE_VNA)
        self.vna.configure_sweep(10e9, 15e9, 51)
        self.vna.configure_power(-10.0)
        self.vna.configure_if_bandwidth(1000.0)

        self.state_machine.transition(CalibrationState.TRIGGER_SWEEP)
        self.vna.trigger_sweep(substep.parameter)

        self.state_machine.transition(CalibrationState.READ_TRACE)
        trace = self.vna.read_s_parameter(substep.parameter)

        self.state_machine.transition(CalibrationState.SAVE_RAW)
        source_step = f"{step.id}_{self._safe_token(substep.id)}"
        raw_record = trace_record_from_sparameter(trace, source_cal=self.item.id, source_step=source_step)
        raw_path = self.output_root / "raw" / f"{self.item.id}_{source_step}.csv"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        _save_trace_like_csv(raw_path, raw_record.parameter, raw_record.frequency_hz, raw_record.value_db, raw_record.source_cal)
        self.events.append(f"raw:{raw_path.name}")

        self.state_machine.transition(CalibrationState.COMPUTE_OUTPUT)
        self.state_machine.transition(CalibrationState.SAVE_OUTPUT)
        self._save_metadata(step, substep, trace)

    def _save_metadata(self, step: CalibrationStep, substep: CalibrationSubStep, trace: SParameterTrace) -> None:
        source_step = f"{step.id}_{self._safe_token(substep.id)}"
        metadata = MetadataRecord(
            session_id=f"{self.item.id}-{source_step}",
            project_name="CATR Loss Calibrator",
            project_version="0.1.0",
            calibration_item=self.item.id,
            calibration_step=source_step,
            instrument_snapshot={"vna": getattr(self.vna, "__class__", type(self.vna)).__name__},
            link_commands=substep.link_commands,
            manual_confirmation=True,
            input_files=(f"{self.item.id}_{source_step}.raw",),
            input_hashes=("mock",),
            output_files=((substep.final_output,) if substep.final_output else ()),
            output_hashes=(),
            formula_version="v1",
            profile_version="lcd74000f:v1",
            note=f"mock-runner:{substep.name}",
        )
        metadata_path = self.output_root / "metadata" / f"{self.item.id}_{source_step}.json"
        write_metadata(metadata_path, metadata)
        self.events.append(f"metadata:{metadata_path.name}")

    def _substeps_for(self, step: CalibrationStep) -> tuple[CalibrationSubStep, ...]:
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
