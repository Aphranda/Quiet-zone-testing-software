from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from catr_loss_calibrator.application.errors import TaskExecutionError


T = TypeVar("T")


def run_task(task: Callable[[], T]) -> T:
    try:
        return task()
    except Exception as exc:  # pragma: no cover - thin boundary wrapper
        raise TaskExecutionError(str(exc)) from exc

