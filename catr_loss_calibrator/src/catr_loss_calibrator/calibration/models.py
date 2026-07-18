from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MeasurementRole(str, Enum):
    MANUAL = "manual"
    VNA_S21 = "vna_s21"
    COMPUTE = "compute"


@dataclass(frozen=True)
class CalibrationSubStep:
    id: str
    name: str
    input_port: str = ""
    output_port: str = ""
    manual_instruction: str = ""
    route_ids: tuple[str, ...] = ()
    link_commands: tuple[str, ...] = ()
    raw_output: str = ""
    final_output: str = ""
    required_inputs: tuple[str, ...] = ()
    notes: str = ""
    parameter: str = "S21"


@dataclass(frozen=True)
class CalibrationStep:
    id: str
    name: str
    role: MeasurementRole
    input_port: str = ""
    output_port: str = ""
    manual_instruction: str = ""
    route_ids: tuple[str, ...] = ()
    link_commands: tuple[str, ...] = ()
    raw_outputs: tuple[str, ...] = ()
    final_outputs: tuple[str, ...] = ()
    required_inputs: tuple[str, ...] = ()
    notes: str = ""
    substeps: tuple[CalibrationSubStep, ...] = ()


@dataclass(frozen=True)
class CalibrationItem:
    id: str
    name: str
    purpose: str
    steps: tuple[CalibrationStep, ...] = ()


@dataclass(frozen=True)
class CalibrationCatalog:
    items: tuple[CalibrationItem, ...] = field(default_factory=tuple)

    def get(self, item_id: str) -> CalibrationItem:
        normalized = item_id.strip().upper()
        for item in self.items:
            if item.id == normalized:
                return item
        raise KeyError(f"Unknown calibration item: {item_id}")
