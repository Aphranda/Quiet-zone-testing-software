from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


SUPPORTED_S_PARAMETERS = ("S11", "S21", "S12", "S22")


def normalize_s_parameter(parameter: str) -> str:
    normalized = str(parameter).strip().upper()
    if normalized not in SUPPORTED_S_PARAMETERS:
        raise ValueError(f"Unsupported S-parameter for switch box routing: {parameter}")
    return normalized


@dataclass(frozen=True)
class SwitchBoxProfile:
    model: str
    command_by_parameter: Mapping[str, str]

    def __post_init__(self) -> None:
        normalized_commands = {
            normalize_s_parameter(parameter): str(command).strip()
            for parameter, command in self.command_by_parameter.items()
        }
        missing = [parameter for parameter in SUPPORTED_S_PARAMETERS if parameter not in normalized_commands]
        if missing:
            raise ValueError(f"Switch-box profile {self.model!r} missing commands for: {', '.join(missing)}")
        empty = [parameter for parameter, command in normalized_commands.items() if not command]
        if empty:
            raise ValueError(f"Switch-box profile {self.model!r} has empty commands for: {', '.join(empty)}")

        object.__setattr__(self, "model", str(self.model).strip().upper())
        object.__setattr__(self, "command_by_parameter", MappingProxyType(normalized_commands))

    def command_for(self, parameter: str) -> str:
        return self.command_by_parameter[normalize_s_parameter(parameter)]

    def with_overrides(self, overrides: Mapping[str, str]) -> "SwitchBoxProfile":
        commands = dict(self.command_by_parameter)
        for parameter, command in overrides.items():
            commands[normalize_s_parameter(parameter)] = str(command).strip()
        return SwitchBoxProfile(model=self.model, command_by_parameter=commands)


LCD74000F_PROFILE = SwitchBoxProfile(
    model="LCD74000F",
    command_by_parameter={
        "S11": "CONFigure:LINK H,VNA1",
        "S21": "CONFigure:LINK H,VNA1",
        "S12": "CONFigure:LINK V,VNA1",
        "S22": "CONFigure:LINK V,VNA1",
    },
)

TC500_PROFILE = SwitchBoxProfile(
    model="TC500",
    command_by_parameter={
        "S11": "PASSIVE",
        "S21": "PASSIVE",
        "S12": "PASSIVE",
        "S22": "PASSIVE",
    },
)

MOCK_SWITCH_BOX_PROFILE = SwitchBoxProfile(
    model="MOCK",
    command_by_parameter={
        "S11": "PASSIVE",
        "S21": "PASSIVE",
        "S12": "PASSIVE",
        "S22": "PASSIVE",
    },
)

_DEFAULT_PROFILES = {
    LCD74000F_PROFILE.model: LCD74000F_PROFILE,
    TC500_PROFILE.model: TC500_PROFILE,
    MOCK_SWITCH_BOX_PROFILE.model: MOCK_SWITCH_BOX_PROFILE,
}


def default_switch_box_profile(model: str) -> SwitchBoxProfile:
    normalized_model = str(model).strip().upper()
    try:
        return _DEFAULT_PROFILES[normalized_model]
    except KeyError as exc:
        raise ValueError(f"Unsupported switch-box model: {model}") from exc


def switch_box_profile_from_commands(
    model: str,
    *,
    s11_command: str,
    s21_command: str,
    s12_command: str,
    s22_command: str,
) -> SwitchBoxProfile:
    return SwitchBoxProfile(
        model=model,
        command_by_parameter={
            "S11": s11_command,
            "S21": s21_command,
            "S12": s12_command,
            "S22": s22_command,
        },
    )
