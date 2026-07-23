from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MeasurementRole(str, Enum):
    MANUAL = "manual"
    VNA_S21 = "vna_s21"
    COMPUTE = "compute"


class OutputRole(str, Enum):
    RAW_S21 = "raw_s21"
    TEMPORARY = "temporary"
    FINAL = "final"


@dataclass(frozen=True)
class OutputParameter:
    name: str
    role: OutputRole


def classify_output_parameter(name: str, *, declared_as: OutputRole | str | None = None) -> OutputRole:
    normalized_name = name.strip().upper()
    if not normalized_name:
        raise ValueError("Output parameter name is required.")

    if declared_as is not None:
        role = OutputRole(declared_as)
        if role == OutputRole.FINAL:
            return OutputRole.FINAL
        if role == OutputRole.RAW_S21:
            return OutputRole.RAW_S21 if normalized_name.startswith("S21") else OutputRole.TEMPORARY
        return role

    if normalized_name.startswith("S21"):
        return OutputRole.RAW_S21
    if normalized_name.startswith("T_"):
        return OutputRole.TEMPORARY
    if normalized_name.startswith("L_"):
        return OutputRole.FINAL
    return OutputRole.TEMPORARY


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
    vna_power_dbm: float | None = None
    path_template: str = ""
    path: dict[str, Any] | None = None

    @property
    def output_parameters(self) -> tuple[OutputParameter, ...]:
        outputs: list[OutputParameter] = []
        if self.raw_output:
            outputs.append(
                OutputParameter(
                    self.raw_output,
                    classify_output_parameter(self.raw_output, declared_as=OutputRole.RAW_S21),
                )
            )
        if self.final_output:
            outputs.append(OutputParameter(self.final_output, OutputRole.FINAL))
        return tuple(outputs)


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
    vna_power_dbm: float | None = None
    substeps: tuple[CalibrationSubStep, ...] = ()
    path_template: str = ""
    path: dict[str, Any] | None = None

    @property
    def output_parameters(self) -> tuple[OutputParameter, ...]:
        outputs = [
            OutputParameter(name, classify_output_parameter(name, declared_as=OutputRole.RAW_S21))
            for name in self.raw_outputs
        ]
        outputs.extend(OutputParameter(name, OutputRole.FINAL) for name in self.final_outputs)
        for substep in self.substeps:
            outputs.extend(substep.output_parameters)
        return tuple(outputs)

    def outputs_by_role(self, role: OutputRole | str) -> tuple[str, ...]:
        normalized_role = OutputRole(role)
        return tuple(output.name for output in self.output_parameters if output.role == normalized_role)


@dataclass(frozen=True)
class CalibrationItem:
    id: str
    name: str
    purpose: str
    steps: tuple[CalibrationStep, ...] = ()


@dataclass(frozen=True)
class CalibrationCatalog:
    items: tuple[CalibrationItem, ...] = field(default_factory=tuple)
    schema_version: str = ""
    name: str = ""
    display_name: str = ""
    description: str = ""
    source_path: str = ""
    node_catalog: dict[str, Any] = field(default_factory=dict)
    path_templates: dict[str, Any] = field(default_factory=dict)
    band_config: dict[str, Any] = field(default_factory=dict)

    def get(self, item_id: str) -> CalibrationItem:
        normalized = item_id.strip().upper()
        for item in self.items:
            if item.id == normalized:
                return item
        raise KeyError(f"Unknown calibration item: {item_id}")
