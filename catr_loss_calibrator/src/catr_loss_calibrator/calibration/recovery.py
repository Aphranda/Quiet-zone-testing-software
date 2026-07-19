from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from catr_loss_calibrator.calibration.state_machine import CalibrationState


class CalibrationFailureKind(str, Enum):
    VNA_TIMEOUT = "vna_timeout"
    VNA_ERROR = "vna_error"
    LINK_BOX_NO_RESPONSE = "link_box_no_response"
    LINK_BOX_ERROR = "link_box_error"
    STORAGE_SAVE_FAILED = "storage_save_failed"
    OPERATOR_CANCELLED = "operator_cancelled"
    UNKNOWN = "unknown"


class RecoveryAction(str, Enum):
    RETRY_CURRENT_SUBSTEP = "retry_current_substep"
    CHECK_VNA_AND_RETRY = "check_vna_and_retry"
    CHECK_LINK_BOX_AND_RETRY = "check_link_box_and_retry"
    CHOOSE_WRITABLE_OUTPUT_AND_RETRY = "choose_writable_output_and_retry"
    STOPPED_BY_OPERATOR = "stopped_by_operator"
    REVIEW_ERROR_AND_RETRY = "review_error_and_retry"


@dataclass(frozen=True)
class CalibrationFailure:
    kind: CalibrationFailureKind
    action: RecoveryAction
    state: str
    step_id: str
    substep_id: str
    message: str

    def event(self) -> str:
        return (
            f"failure:{self.kind.value}:{self.step_id}:{self.substep_id}:"
            f"{self.state}:{self.action.value}:{self.message}"
        )

    def operator_message(self) -> str:
        return (
            f"{self.kind.value} at {self.step_id}/{self.substep_id} "
            f"while {self.state}: {self.message}; action={self.action.value}"
        )


class CalibrationRunError(RuntimeError):
    def __init__(self, failure: CalibrationFailure) -> None:
        super().__init__(failure.operator_message())
        self.failure = failure


def classify_failure(exc: BaseException, state: CalibrationState, *, step_id: str, substep_id: str) -> CalibrationFailure:
    message = str(exc) or exc.__class__.__name__
    kind = _kind_for(exc, state)
    return CalibrationFailure(
        kind=kind,
        action=_action_for(kind),
        state=state.value,
        step_id=step_id,
        substep_id=substep_id,
        message=message,
    )


def operator_cancelled(step_id: str, substep_id: str, state: CalibrationState) -> CalibrationFailure:
    return CalibrationFailure(
        kind=CalibrationFailureKind.OPERATOR_CANCELLED,
        action=RecoveryAction.STOPPED_BY_OPERATOR,
        state=state.value,
        step_id=step_id,
        substep_id=substep_id,
        message="Operator cancelled calibration.",
    )


def _kind_for(exc: BaseException, state: CalibrationState) -> CalibrationFailureKind:
    if isinstance(exc, TimeoutError):
        if state == CalibrationState.CONFIGURE_LINK:
            return CalibrationFailureKind.LINK_BOX_NO_RESPONSE
        if state in {CalibrationState.CONFIGURE_VNA, CalibrationState.TRIGGER_SWEEP, CalibrationState.READ_TRACE}:
            return CalibrationFailureKind.VNA_TIMEOUT

    if isinstance(exc, OSError) and state in {
        CalibrationState.SAVE_RAW,
        CalibrationState.COMPUTE_OUTPUT,
        CalibrationState.SAVE_OUTPUT,
    }:
        return CalibrationFailureKind.STORAGE_SAVE_FAILED

    if state == CalibrationState.CONFIGURE_LINK:
        return CalibrationFailureKind.LINK_BOX_ERROR
    if state in {CalibrationState.CONFIGURE_VNA, CalibrationState.TRIGGER_SWEEP, CalibrationState.READ_TRACE}:
        return CalibrationFailureKind.VNA_ERROR
    if state in {CalibrationState.SAVE_RAW, CalibrationState.COMPUTE_OUTPUT, CalibrationState.SAVE_OUTPUT}:
        return CalibrationFailureKind.STORAGE_SAVE_FAILED
    return CalibrationFailureKind.UNKNOWN


def _action_for(kind: CalibrationFailureKind) -> RecoveryAction:
    actions = {
        CalibrationFailureKind.VNA_TIMEOUT: RecoveryAction.CHECK_VNA_AND_RETRY,
        CalibrationFailureKind.VNA_ERROR: RecoveryAction.CHECK_VNA_AND_RETRY,
        CalibrationFailureKind.LINK_BOX_NO_RESPONSE: RecoveryAction.CHECK_LINK_BOX_AND_RETRY,
        CalibrationFailureKind.LINK_BOX_ERROR: RecoveryAction.CHECK_LINK_BOX_AND_RETRY,
        CalibrationFailureKind.STORAGE_SAVE_FAILED: RecoveryAction.CHOOSE_WRITABLE_OUTPUT_AND_RETRY,
        CalibrationFailureKind.OPERATOR_CANCELLED: RecoveryAction.STOPPED_BY_OPERATOR,
        CalibrationFailureKind.UNKNOWN: RecoveryAction.REVIEW_ERROR_AND_RETRY,
    }
    return actions[kind]
