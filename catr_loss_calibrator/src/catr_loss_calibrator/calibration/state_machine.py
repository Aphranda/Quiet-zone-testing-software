from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CalibrationState(str, Enum):
    IDLE = "IDLE"
    WAIT_MANUAL_CONFIRM = "WAIT_MANUAL_CONFIRM"
    CONFIGURE_LINK = "CONFIGURE_LINK"
    CONFIGURE_VNA = "CONFIGURE_VNA"
    TRIGGER_SWEEP = "TRIGGER_SWEEP"
    READ_TRACE = "READ_TRACE"
    SAVE_RAW = "SAVE_RAW"
    COMPUTE_OUTPUT = "COMPUTE_OUTPUT"
    SAVE_OUTPUT = "SAVE_OUTPUT"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class CalibrationStateMachine:
    state: CalibrationState = CalibrationState.IDLE
    history: list[CalibrationState] = field(default_factory=list)

    def transition(self, next_state: CalibrationState) -> CalibrationState:
        allowed: dict[CalibrationState, set[CalibrationState]] = {
            CalibrationState.IDLE: {CalibrationState.WAIT_MANUAL_CONFIRM, CalibrationState.CANCELLED},
            CalibrationState.WAIT_MANUAL_CONFIRM: {CalibrationState.CONFIGURE_LINK, CalibrationState.CANCELLED, CalibrationState.FAILED},
            CalibrationState.CONFIGURE_LINK: {CalibrationState.CONFIGURE_VNA, CalibrationState.FAILED, CalibrationState.CANCELLED},
            CalibrationState.CONFIGURE_VNA: {CalibrationState.TRIGGER_SWEEP, CalibrationState.FAILED, CalibrationState.CANCELLED},
            CalibrationState.TRIGGER_SWEEP: {CalibrationState.READ_TRACE, CalibrationState.FAILED, CalibrationState.CANCELLED},
            CalibrationState.READ_TRACE: {CalibrationState.SAVE_RAW, CalibrationState.FAILED, CalibrationState.CANCELLED},
            CalibrationState.SAVE_RAW: {CalibrationState.COMPUTE_OUTPUT, CalibrationState.FAILED, CalibrationState.CANCELLED},
            CalibrationState.COMPUTE_OUTPUT: {CalibrationState.SAVE_OUTPUT, CalibrationState.FAILED, CalibrationState.CANCELLED},
            CalibrationState.SAVE_OUTPUT: {CalibrationState.DONE, CalibrationState.WAIT_MANUAL_CONFIRM, CalibrationState.FAILED, CalibrationState.CANCELLED},
            CalibrationState.DONE: set(),
            CalibrationState.FAILED: set(),
            CalibrationState.CANCELLED: set(),
        }
        if next_state not in allowed[self.state]:
            raise ValueError(f"Invalid state transition: {self.state.value} -> {next_state.value}")
        self.history.append(self.state)
        self.state = next_state
        return self.state
