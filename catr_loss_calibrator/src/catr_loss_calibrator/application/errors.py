from __future__ import annotations


class CatrLossCalibratorError(Exception):
    """Base error for the CATR loss calibrator application."""


class TaskExecutionError(CatrLossCalibratorError):
    """Raised when an application task fails."""

