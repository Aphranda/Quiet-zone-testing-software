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
    output_role: str = ""
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
    input_roles: tuple[str, ...] = ()
    output_files: tuple[str, ...] = ()
    output_hashes: tuple[str, ...] = ()
    output_roles: tuple[str, ...] = ()
    measurement_settings: dict[str, Any] | None = None
    measurement_warnings: tuple[str, ...] = ()
    run_uid: str = ""
    workspace_id: str = ""
    workspace_root: str = ""
    session_root: str = ""
    config_hash: str = ""
    config_source_path: str = ""
    project_code: str = ""
    calibration_stage: str = ""
    run_label: str = ""
    operator: str = ""
    operator_note: str = ""
    formula_version: str = ""
    profile_version: str = ""
    note: str = ""
