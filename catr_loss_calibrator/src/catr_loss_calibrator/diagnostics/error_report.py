from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorReport:
    message: str
    detail: str = ""

