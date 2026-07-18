from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class TraceRecord:
    frequency_hz: np.ndarray
    value_db: np.ndarray
    parameter: str
    source_cal: str
    source_step: str
    band: str = ""
    feed: str = ""
    horn: str = ""


@dataclass(frozen=True)
class MetadataRecord:
    session_id: str
    project_name: str
    project_version: str
    calibration_item: str
    calibration_step: str
    instrument_snapshot: dict[str, Any]
    link_commands: tuple[str, ...]
    manual_confirmation: bool
    input_files: tuple[str, ...]
    input_hashes: tuple[str, ...]
    output_files: tuple[str, ...] = ()
    output_hashes: tuple[str, ...] = ()
    formula_version: str = ""
    profile_version: str = ""
    note: str = ""
