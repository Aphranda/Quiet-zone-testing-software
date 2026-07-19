from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any, Callable

import numpy as np

from catr_loss_calibrator.calibration import formulas
from catr_loss_calibrator.calibration.models import (
    CalibrationItem,
    CalibrationStep,
    CalibrationSubStep,
    MeasurementRole,
    OutputRole,
    classify_output_parameter,
)
from catr_loss_calibrator.calibration.recovery import (
    CalibrationFailure,
    CalibrationRunError,
    classify_failure,
    operator_cancelled,
)
from catr_loss_calibrator.calibration.state_machine import CalibrationState, CalibrationStateMachine
from catr_loss_calibrator.hardware.interfaces import LinkBox, SParameterTrace, Vna
from catr_loss_calibrator.storage.loss_file_policy import LossFilePolicy
from catr_loss_calibrator.storage.loss_file_storage import save_loss_record_with_policy
from catr_loss_calibrator.storage.metadata_writer import write_metadata
from catr_loss_calibrator.storage.models import MetadataRecord, TraceRecord
from catr_loss_calibrator.storage.raw_trace_storage import trace_record_from_sparameter
from catr_loss_calibrator.storage.workspace import SessionContext, write_latest_index, write_session_manifest


@dataclass
class MockCalibrationRunner:
    item: CalibrationItem
    vna: Vna
    link_box: LinkBox
    output_root: Path
    confirm_step: Callable[[CalibrationStep, CalibrationSubStep, str, int, int, int, int], str] | None = None
    event_callback: Callable[[str], None] | None = None
    vna_settings: dict[str, Any] = field(default_factory=dict)
    feed: str = "F10_17G"
    horn: str = "H10_15G"
    loss_file_policy: LossFilePolicy | None = None
    session_context: SessionContext | None = None
    state_machine: CalibrationStateMachine = field(default_factory=CalibrationStateMachine)
    events: list[str] = field(default_factory=list)
    _records: dict[str, TraceRecord] = field(default_factory=dict, init=False, repr=False)
    _saved_outputs: set[str] = field(default_factory=set, init=False, repr=False)
    _output_paths: dict[str, Path] = field(default_factory=dict, init=False, repr=False)
    _raw_paths: list[Path] = field(default_factory=list, init=False, repr=False)
    _metadata_paths: list[Path] = field(default_factory=list, init=False, repr=False)
    _manifest_path: Path | None = field(default=None, init=False, repr=False)
    _latest_index_path: Path | None = field(default=None, init=False, repr=False)
    _failure: CalibrationFailure | None = field(default=None, init=False, repr=False)

    def run(self) -> list[str]:
        self._ensure_ready()
        if self.state_machine.state not in {CalibrationState.IDLE, CalibrationState.DONE, CalibrationState.CANCELLED}:
            raise RuntimeError(f"Runner is busy in state {self.state_machine.state.value}")
        self._record_event(f"start:{self.item.id}")
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
                        self._record_cancellation(step, substep)
                        self.state_machine.transition(CalibrationState.CANCELLED)
                        self._record_event(f"cancel:{step.id}:{substep.id}")
                        self._write_session_manifest()
                        return self.events
                    if action == "skip":
                        self._record_event(f"skip:{step.id}:{substep.id}")
                        break

                    try:
                        self._run_substep(step, substep)
                    except Exception as exc:
                        raise self._fail_substep(exc, step, substep) from exc
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
                        self._record_cancellation(step, substep)
                        self.state_machine.transition(CalibrationState.CANCELLED)
                        self._record_event(f"cancel:{step.id}:{substep.id}")
                        self._write_session_manifest()
                        return self.events
                    if done_action == "retry":
                        self._record_event(f"retry:{step.id}:{substep.id}")
                        continue
                    if done_action == "skip":
                        self._record_event(f"skip:{step.id}:{substep.id}")
                    break
        self.state_machine.transition(CalibrationState.DONE)
        self._record_event(f"done:{self.item.id}")
        self._write_session_manifest()
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
            "output_root": str(self.output_root),
            "raw_files": tuple(str(path) for path in self._raw_paths),
            "loss_files": tuple(str(path) for path in self._output_paths.values()),
            "metadata_files": tuple(str(path) for path in self._metadata_paths),
            "manifest_file": str(self._manifest_path) if self._manifest_path else "",
            "latest_index_file": str(self._latest_index_path) if self._latest_index_path else "",
            **self._session_overview(),
            **self._failure_overview(),
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
            self._record_event(f"link:{step.id}:{substep.id}:{command}")

        self.state_machine.transition(CalibrationState.CONFIGURE_VNA)
        settings = self._normalized_vna_settings()
        self.vna.configure_sweep(settings["start_hz"], settings["stop_hz"], settings["points"])
        self.vna.configure_power(settings["power_dbm"])
        self.vna.configure_if_bandwidth(settings["if_bandwidth_hz"])
        configure_parameter = getattr(self.vna, "configure_measurement_parameter", None)
        if callable(configure_parameter):
            configure_parameter(settings["parameter"])
        configure_continuous = getattr(self.vna, "configure_continuous_sweep", None)
        if callable(configure_continuous):
            configure_continuous(settings["continuous_sweep"])

        self.state_machine.transition(CalibrationState.TRIGGER_SWEEP)
        self.vna.trigger_sweep(settings["parameter"])

        self.state_machine.transition(CalibrationState.READ_TRACE)
        trace = self.vna.read_s_parameter(settings["parameter"])

        self.state_machine.transition(CalibrationState.SAVE_RAW)
        source_step = f"{step.id}_{self._safe_token(substep.id)}"
        raw_parameter = substep.raw_output or (step.raw_outputs[0] if step.raw_outputs else settings["parameter"])
        raw_record = TraceRecord(
            frequency_hz=np.asarray(trace.frequency_hz, dtype=float),
            value_db=np.asarray(trace.value_db, dtype=float),
            parameter=raw_parameter,
            source_cal=self.item.id,
            source_step=source_step,
            output_role=classify_output_parameter(raw_parameter, declared_as=OutputRole.RAW_S21).value,
        )
        self._records[raw_record.parameter] = raw_record
        raw_path = self.output_root / "raw" / f"{self.item.id}_{source_step}.csv"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        _save_trace_like_csv(
            raw_path,
            raw_record.parameter,
            raw_record.frequency_hz,
            raw_record.value_db,
            raw_record.source_cal,
            raw_record.output_role,
        )
        self._track_path(self._raw_paths, raw_path)
        self._record_event(f"raw:{raw_path.name}")

        self.state_machine.transition(CalibrationState.COMPUTE_OUTPUT)
        output_paths = self._compute_available_outputs(source_step, raw_record.frequency_hz)
        self.state_machine.transition(CalibrationState.SAVE_OUTPUT)
        self._save_metadata(step, substep, trace, raw_path=raw_path, output_paths=output_paths)

    def _normalized_vna_settings(self) -> dict[str, Any]:
        settings = dict(self.vna_settings or {})
        parameter = str(settings.get("parameter") or "S21").strip().upper()
        if "start_hz" in settings:
            start_hz = float(settings["start_hz"])
        else:
            start_hz = float(settings.get("start_ghz", 10.0)) * 1e9
        if "stop_hz" in settings:
            stop_hz = float(settings["stop_hz"])
        else:
            stop_hz = float(settings.get("stop_ghz", 15.0)) * 1e9
        return {
            "start_hz": start_hz,
            "stop_hz": stop_hz,
            "points": int(settings.get("points", 51)),
            "power_dbm": float(settings.get("vna_power_dbm", settings.get("power_dbm", -10.0))),
            "if_bandwidth_hz": float(settings.get("if_bandwidth_hz", 1000.0)),
            "parameter": parameter,
            "continuous_sweep": bool(settings.get("continuous_sweep", False)),
        }

    def _compute_available_outputs(self, source_step: str, frequency_hz: np.ndarray) -> tuple[Path, ...]:
        saved_paths: list[Path] = []
        output_params = {
            output
            for item_step in self.item.steps
            for output in (*item_step.final_outputs, *(sub.final_output for sub in item_step.substeps if sub.final_output))
            if output and "/" not in output
        }

        changed = True
        while changed:
            changed = False
            for param in sorted(output_params):
                if param in self._saved_outputs:
                    continue
                value = self._calculate_output(param, frequency_hz)
                if value is None:
                    continue
                record = TraceRecord(
                    frequency_hz=np.asarray(frequency_hz, dtype=float),
                    value_db=np.asarray(value, dtype=float),
                    parameter=param,
                    source_cal=self.item.id,
                    source_step=source_step,
                    output_role=OutputRole.FINAL.value,
                    feed=self.feed,
                    horn=self.horn,
                )
                path = save_loss_record_with_policy(self.output_root / "loss", record, policy=self.loss_file_policy)
                self._records[param] = record
                self._saved_outputs.add(param)
                self._output_paths[param] = path
                self._record_event(f"loss:{path.name}")
                saved_paths.append(path)
                changed = True
        return tuple(saved_paths)

    def _calculate_output(self, param: str, frequency_hz: np.ndarray) -> np.ndarray | None:
        def require(*names: str) -> tuple[np.ndarray, ...] | None:
            values = []
            for name in names:
                value = self._value_for(name, frequency_hz)
                if value is None:
                    return None
                values.append(value)
            return tuple(values)

        if param.startswith("L_AUX_"):
            values = require(f"S21_AUX_{param.removeprefix('L_AUX_')}")
            return None if values is None else formulas.aux_loss(values[0])

        calculators: dict[str, Callable[[], np.ndarray | None]] = {
            "L_CH_INT_H": lambda: self._maybe(formulas.link_cal_001_h, require("S21_CH_INT_H_RAW", "L_AUX_A", "L_AUX_C", "G_STD_HORN_H")),
            "L_CH_INT_V": lambda: self._maybe(formulas.link_cal_001_v, require("S21_CH_INT_V_RAW", "L_AUX_B", "L_AUX_C", "G_STD_HORN_V")),
            "L_CH_INT_DUT": lambda: self._maybe(formulas.link_cal_001_dut, require("S21_CH_INT_DUT_RAW", "L_AUX_A", "L_AUX_C")),
            "L_CH_INT_FEED_H": lambda: self._maybe(formulas.feed_loss, require("L_CH_INT_H", "L_CH_INT_DUT")),
            "L_CH_INT_FEED_V": lambda: self._maybe(formulas.feed_loss, require("L_CH_INT_V", "L_CH_INT_DUT")),
            "L_DUT_VNA": lambda: self._maybe(formulas.link_cal_002_dut_vna, require("S21_DUT_VNA_RAW", "L_AUX_D")),
            "L_DUT_VNA_AMP1": lambda: self._maybe(formulas.link_cal_002_dut_vna, require("S21_DUT_VNA_AMP1_RAW", "L_AUX_D")),
            "L_DUT_VNA_F": lambda: self._maybe(formulas.link_cal_004_dut_vna_f, require("S21_DUT_VNA_F_RAW", "L_AUX_F")),
            "L_DUT_VNA_F_AMP1": lambda: self._maybe(formulas.link_cal_004_dut_vna_f, require("S21_DUT_VNA_F_AMP1_RAW", "L_AUX_F")),
            "L_DUT_VNA_G": lambda: self._maybe(formulas.link_cal_005_dut_vna_g, require("S21_DUT_VNA_G_RAW", "L_AUX_G")),
            "L_DUT_VNA_G_AMP1": lambda: self._maybe(formulas.link_cal_005_dut_vna_g, require("S21_DUT_VNA_G_AMP1_RAW", "L_AUX_G")),
            "L_DUT_SA": lambda: self._maybe(formulas.link_cal_003_dut_sa, require("T_AUXE_DUT_SA", "L_AUX_E")),
            "L_DUT_SA_AMP1": lambda: self._maybe(formulas.link_cal_003_dut_sa, require("T_AUXE_DUT_SA_AMP1", "L_AUX_E")),
            "L_VNA_FEED_H": lambda: self._maybe(formulas.link_cal_002_vna_feed, require("L_VNA_H", "G_STD_HORN_H", "L_DUT_VNA")),
            "L_VNA_FEED_V": lambda: self._maybe(formulas.link_cal_002_vna_feed, require("L_VNA_V", "G_STD_HORN_V", "L_DUT_VNA")),
            "L_VNA_FEED_H_AMP1": lambda: self._maybe(formulas.link_cal_002_vna_feed, require("L_VNA_H_AMP1", "G_STD_HORN_H", "L_DUT_VNA_AMP1")),
            "L_VNA_FEED_V_AMP1": lambda: self._maybe(formulas.link_cal_002_vna_feed, require("L_VNA_V_AMP1", "G_STD_HORN_V", "L_DUT_VNA_AMP1")),
            "L_VNA_FEED_H_AMP2": lambda: self._maybe(formulas.link_cal_002_vna_feed, require("L_VNA_H_AMP2", "G_STD_HORN_H", "L_DUT_VNA")),
            "L_VNA_FEED_V_AMP2": lambda: self._maybe(formulas.link_cal_002_vna_feed, require("L_VNA_V_AMP2", "G_STD_HORN_V", "L_DUT_VNA")),
            "L_SYS_TX_SA_H": lambda: self._maybe(formulas.link_cal_004_system_tx_sa, require("T_SYS_TX_SA_H", "G_STD_HORN_H", "L_DUT_VNA_F")),
            "L_SYS_TX_SA_V": lambda: self._maybe(formulas.link_cal_004_system_tx_sa, require("T_SYS_TX_SA_V", "G_STD_HORN_V", "L_DUT_VNA_F")),
            "L_SYS_TX_SA_H_AMP2": lambda: self._maybe(formulas.link_cal_004_system_tx_sa, require("T_SYS_TX_SA_H_AMP2", "G_STD_HORN_H", "L_DUT_VNA_F")),
            "L_SYS_TX_SA_V_AMP2": lambda: self._maybe(formulas.link_cal_004_system_tx_sa, require("T_SYS_TX_SA_V_AMP2", "G_STD_HORN_V", "L_DUT_VNA_F")),
            "L_SG_DUT_H": lambda: self._maybe(formulas.link_cal_005_sg, require("T_SG_H", "G_STD_HORN_H", "L_DUT_VNA_G")),
            "L_SG_DUT_V": lambda: self._maybe(formulas.link_cal_005_sg, require("T_SG_V", "G_STD_HORN_V", "L_DUT_VNA_G")),
            "L_SG_DUT_H_AMP1": lambda: self._maybe(formulas.link_cal_005_sg, require("T_SG_H_AMP1", "G_STD_HORN_H", "L_DUT_VNA_G_AMP1")),
            "L_SG_DUT_V_AMP1": lambda: self._maybe(formulas.link_cal_005_sg, require("T_SG_V_AMP1", "G_STD_HORN_V", "L_DUT_VNA_G_AMP1")),
            "L_HV_SG_H_AMP2": lambda: self._maybe(formulas.link_cal_005_sg, require("T_SG_H_AMP2", "G_STD_HORN_H", "L_DUT_VNA_G")),
            "L_HV_SG_V_AMP2": lambda: self._maybe(formulas.link_cal_005_sg, require("T_SG_V_AMP2", "G_STD_HORN_V", "L_DUT_VNA_G")),
        }
        calculator = calculators.get(param)
        return None if calculator is None else calculator()

    @staticmethod
    def _maybe(function: Callable[..., np.ndarray], values: tuple[np.ndarray, ...] | None) -> np.ndarray | None:
        if values is None:
            return None
        return function(*values)

    def _value_for(self, name: str, frequency_hz: np.ndarray) -> np.ndarray | None:
        if name in self._records:
            record = self._records[name]
            if len(record.frequency_hz) == len(frequency_hz) and np.allclose(record.frequency_hz, frequency_hz):
                return np.asarray(record.value_db, dtype=float)
            return np.interp(frequency_hz, record.frequency_hz, record.value_db)

        external_inputs = dict(self.vna_settings.get("external_inputs") or {})
        aliases = {
            "G_STD_HORN_H": ("G_STD_HORN_H", "horn_gain_h_dbi", "horn_gain_db"),
            "G_STD_HORN_V": ("G_STD_HORN_V", "horn_gain_v_dbi", "horn_gain_db"),
        }
        for key in aliases.get(name, (name,)):
            if key in external_inputs:
                return self._coerce_input(external_inputs[key], frequency_hz)
            if key in self.vna_settings:
                return self._coerce_input(self.vna_settings[key], frequency_hz)

        if name in {"G_STD_HORN_H", "G_STD_HORN_V"}:
            return np.zeros_like(frequency_hz, dtype=float)
        return None

    @staticmethod
    def _coerce_input(value: Any, frequency_hz: np.ndarray) -> np.ndarray:
        array = np.asarray(value, dtype=float)
        if array.ndim == 0:
            return np.full_like(frequency_hz, float(array), dtype=float)
        if len(array) != len(frequency_hz):
            raise ValueError(f"External input length {len(array)} does not match sweep length {len(frequency_hz)}.")
        return array

    def _save_metadata(
        self,
        step: CalibrationStep,
        substep: CalibrationSubStep,
        trace: SParameterTrace,
        *,
        raw_path: Path,
        output_paths: tuple[Path, ...],
    ) -> None:
        source_step = f"{step.id}_{self._safe_token(substep.id)}"
        metadata = MetadataRecord(
            session_id=self.session_context.session_id if self.session_context else f"{self.item.id}-{source_step}",
            project_name="CATR Loss Calibrator",
            project_version="0.1.0",
            calibration_item=self.item.id,
            calibration_step=source_step,
            instrument_snapshot={"vna": getattr(self.vna, "__class__", type(self.vna)).__name__},
            link_commands=substep.link_commands,
            manual_confirmation=True,
            input_files=(str(raw_path),),
            input_hashes=(_sha256(raw_path),),
            input_roles=(classify_output_parameter(substep.raw_output or step.id, declared_as=OutputRole.RAW_S21).value,),
            output_files=tuple(str(path) for path in output_paths),
            output_hashes=tuple(_sha256(path) for path in output_paths),
            output_roles=tuple(OutputRole.FINAL.value for _path in output_paths),
            **self._metadata_session_fields(),
            formula_version="v1",
            profile_version="lcd74000f:v1",
            note=f"mock-runner:{substep.name}",
        )
        metadata_path = self.output_root / "metadata" / f"{self.item.id}_{source_step}.json"
        write_metadata(metadata_path, metadata)
        self._track_path(self._metadata_paths, metadata_path)
        self._record_event(f"metadata:{metadata_path.name}")

    def _fail_substep(self, exc: BaseException, step: CalibrationStep, substep: CalibrationSubStep) -> CalibrationRunError:
        if isinstance(exc, CalibrationRunError):
            self._failure = exc.failure
        else:
            self._failure = classify_failure(
                exc,
                self.state_machine.state,
                step_id=step.id,
                substep_id=substep.id,
            )
        if self.state_machine.state not in {CalibrationState.FAILED, CalibrationState.CANCELLED, CalibrationState.DONE}:
            self.state_machine.transition(CalibrationState.FAILED)
        self._record_event(self._failure.event())
        self._write_session_manifest()
        return CalibrationRunError(self._failure)

    def _record_cancellation(self, step: CalibrationStep, substep: CalibrationSubStep) -> None:
        self._failure = operator_cancelled(step.id, substep.id, self.state_machine.state)
        self._record_event(self._failure.event())

    def _failure_overview(self) -> dict[str, object]:
        if self._failure is None:
            return {}
        return {
            "failure_kind": self._failure.kind.value,
            "failure_action": self._failure.action.value,
            "failure_state": self._failure.state,
            "failure_step_id": self._failure.step_id,
            "failure_substep_id": self._failure.substep_id,
            "failure_message": self._failure.message,
        }

    def _session_overview(self) -> dict[str, object]:
        if self.session_context is None:
            return {}
        session = self.session_context
        return {
            "run_uid": session.run_uid,
            "session_id": session.session_id,
            "session_root": str(session.session_root),
            "workspace_id": session.workspace.workspace_id,
            "workspace_root": str(session.workspace.workspace_root),
            "config_hash": session.workspace.config_hash,
            "config_source_path": session.workspace.config_source_path,
            "project_code": session.run.project_code,
            "calibration_stage": session.run.calibration_stage,
            "run_label": session.run.run_label,
            "operator": session.run.operator,
            "operator_note": session.run.operator_note,
        }

    def _metadata_session_fields(self) -> dict[str, str]:
        if self.session_context is None:
            return {}
        session = self.session_context
        return {
            "run_uid": session.run_uid,
            "workspace_id": session.workspace.workspace_id,
            "workspace_root": str(session.workspace.workspace_root),
            "session_root": str(session.session_root),
            "config_hash": session.workspace.config_hash,
            "config_source_path": session.workspace.config_source_path,
            "project_code": session.run.project_code,
            "calibration_stage": session.run.calibration_stage,
            "run_label": session.run.run_label,
            "operator": session.run.operator,
            "operator_note": session.run.operator_note,
        }

    def _write_session_manifest(self) -> None:
        if self.session_context is None:
            return
        failure = self._failure_overview()
        self._manifest_path = write_session_manifest(
            self.session_context,
            state=self.state_machine.state.value,
            raw_files=tuple(str(path) for path in self._raw_paths),
            loss_files=tuple(str(path) for path in self._output_paths.values()),
            metadata_files=tuple(str(path) for path in self._metadata_paths),
            last_event=self.events[-1] if self.events else "",
            failure=failure or None,
        )
        if self.state_machine.state == CalibrationState.DONE:
            self._latest_index_path = write_latest_index(self.session_context, self._manifest_path)

    def _record_event(self, event: str) -> None:
        self.events.append(event)
        if self.event_callback is not None:
            self.event_callback(event)

    @staticmethod
    def _track_path(paths: list[Path], path: Path) -> None:
        if path not in paths:
            paths.append(path)

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


def _save_trace_like_csv(path: Path, parameter: str, frequency_hz, value_db, source_cal: str, output_role: str) -> None:
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
        output_role=output_role,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
