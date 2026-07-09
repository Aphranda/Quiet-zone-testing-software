from __future__ import annotations

from enum import Enum


class ScanState(str, Enum):
    IDLE = "Idle"
    PLANNING = "Planning"
    RUNNING = "Running"
    PAUSED = "Paused"
    STOPPING = "Stopping"
    COMPLETED = "Completed"
    FAILED = "Failed"


class ScanStateError(RuntimeError):
    pass


class ScanStateMachine:
    _TRANSITIONS: dict[ScanState, dict[str, ScanState]] = {
        ScanState.IDLE: {
            "start_scan": ScanState.PLANNING,
            "reset": ScanState.IDLE,
        },
        ScanState.PLANNING: {
            "plan_ready": ScanState.RUNNING,
            "plan_failed": ScanState.FAILED,
            "stop": ScanState.STOPPING,
        },
        ScanState.RUNNING: {
            "pause": ScanState.PAUSED,
            "stop": ScanState.STOPPING,
            "point_completed": ScanState.RUNNING,
            "scan_completed": ScanState.COMPLETED,
            "error": ScanState.FAILED,
        },
        ScanState.PAUSED: {
            "resume": ScanState.RUNNING,
            "stop": ScanState.STOPPING,
            "error": ScanState.FAILED,
        },
        ScanState.STOPPING: {
            "stopped": ScanState.COMPLETED,
            "stop_failed": ScanState.FAILED,
            "error": ScanState.FAILED,
        },
        ScanState.COMPLETED: {
            "reset": ScanState.IDLE,
        },
        ScanState.FAILED: {
            "reset": ScanState.IDLE,
        },
    }

    def __init__(self, initial_state: ScanState = ScanState.IDLE) -> None:
        self._state = initial_state

    @property
    def state(self) -> ScanState:
        return self._state

    @property
    def is_busy(self) -> bool:
        return self._state in {
            ScanState.PLANNING,
            ScanState.RUNNING,
            ScanState.PAUSED,
            ScanState.STOPPING,
        }

    @property
    def can_start(self) -> bool:
        return self._state == ScanState.IDLE

    @property
    def can_pause(self) -> bool:
        return self._state == ScanState.RUNNING

    @property
    def can_resume(self) -> bool:
        return self._state == ScanState.PAUSED

    @property
    def can_stop(self) -> bool:
        return self._state in {ScanState.PLANNING, ScanState.RUNNING, ScanState.PAUSED}

    def can_handle(self, event: str) -> bool:
        return event in self._TRANSITIONS[self._state]

    def handle(self, event: str) -> ScanState:
        transitions = self._TRANSITIONS[self._state]
        if event not in transitions:
            raise ScanStateError(f"Cannot handle scan event {event!r} while state is {self._state.value}.")
        self._state = transitions[event]
        return self._state

    def reset(self) -> ScanState:
        return self.handle("reset")
