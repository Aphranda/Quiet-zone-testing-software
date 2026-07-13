from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScanWorkflowState:
    sampling_active: bool = False
    active_mode: str | None = None
    completed_points: int = 0
    total_points: int = 0
    stop_requested: bool = False
    paused: bool = False
    failed: bool = False
    task_running: bool = False
    stop_positioner_task_running: bool = False

    def begin_preview_sample(self) -> None:
        self.completed_points = 1
        self.total_points = 1

    def begin_scan(self, total_points: int) -> None:
        self.sampling_active = True
        self.active_mode = "scan"
        self.completed_points = 0
        self.total_points = max(int(total_points), 0)
        self.stop_requested = False
        self.paused = False
        self.failed = False

    def mark_scan_task_running(self, running: bool) -> None:
        self.task_running = bool(running)

    def set_progress(self, completed_points: int, total_points: int) -> None:
        self.completed_points = int(completed_points)
        self.total_points = max(int(total_points), 1)

    def pause(self) -> None:
        if self.sampling_active:
            self.paused = True

    def resume(self) -> None:
        self.paused = False

    def request_stop(self) -> None:
        self.stop_requested = True
        self.paused = False
        self.sampling_active = False
        self.active_mode = None

    def mark_stopped(self) -> None:
        self.stop_requested = True
        self.failed = False
        self.paused = False
        self.sampling_active = False
        self.active_mode = None

    def mark_failed(self) -> None:
        self.failed = True
        self.paused = False
        self.sampling_active = False
        self.active_mode = None

    def begin_finished_cleanup(self) -> tuple[bool, bool]:
        stop_requested = self.stop_requested
        failed = self.failed
        self.task_running = False
        self.paused = False
        return stop_requested, failed

    def result_state(self) -> str:
        if self.stop_requested and self.failed:
            return "StoppedWithError"
        if self.stop_requested:
            return "Stopped"
        if self.failed:
            return "Failed"
        return "Completed"

    def finish_inactive_cleanup(self) -> None:
        self.stop_requested = False
        self.failed = False

    def finish_success_cleanup(self) -> None:
        self.sampling_active = False
        self.active_mode = None
        self.stop_requested = False
        self.failed = False
        self.paused = False

    def set_stop_positioner_task_running(self, running: bool) -> None:
        self.stop_positioner_task_running = bool(running)

    def reset(self) -> None:
        self.sampling_active = False
        self.active_mode = None
        self.completed_points = 0
        self.total_points = 0
        self.stop_requested = False
        self.paused = False
        self.failed = False
        self.task_running = False
        self.stop_positioner_task_running = False

    def connection_busy(self, busy: bool) -> bool:
        return bool(busy) or self.sampling_active or self.task_running or self.stop_positioner_task_running

    def test_busy(self, busy: bool) -> bool:
        return bool(busy) or self.sampling_active
