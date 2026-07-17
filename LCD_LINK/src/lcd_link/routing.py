from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


SUPPORTED_S_PARAMETERS = ("S11", "S21", "S12", "S22")

DEFAULT_LINK_COMMANDS = (
    "CONFigure:LINK DUT, AMP1, SA",
    "CONFigure:LINK DUT, AMP1, VNA2",
    "CONFigure:LINK H, SG",
    "CONFigure:LINK H, VNA1",
    "CONFigure:LINK H, SA",
    "CONFigure:LINK H, AMP2, SG",
    "CONFigure:LINK H, AMP2, VNA1",
    "CONFigure:LINK H, AMP2, SA",
    "CONFigure:LINK V, SG",
    "CONFigure:LINK V, VNA1",
    "CONFigure:LINK V, SA",
    "CONFigure:LINK V, AMP2, SG",
    "CONFigure:LINK V, AMP2, VNA1",
    "CONFigure:LINK V, AMP2, SA",
)


def normalize_s_parameter(parameter: str) -> str:
    normalized = str(parameter).strip().upper()
    if normalized not in SUPPORTED_S_PARAMETERS:
        raise ValueError(f"Unsupported S-parameter for switch box routing: {parameter}")
    return normalized


def normalize_polarization(polarization: str) -> str:
    normalized = str(polarization).strip().upper()
    if normalized not in {"H", "V"}:
        raise ValueError(f"Unsupported polarization for switch box routing: {polarization}")
    return normalized


def command_with_polarization(command: str, polarization: str | None) -> str:
    if polarization is None or str(polarization).strip() == "":
        return command

    selected_polarization = normalize_polarization(polarization)
    return re.sub(
        r"(?i)(?<![A-Z0-9_])[HV](?![A-Z0-9_])",
        selected_polarization,
        command,
    )


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

    def command_for(self, parameter: str, polarization: str | None = None) -> str:
        command = self.command_by_parameter[normalize_s_parameter(parameter)]
        return command_with_polarization(command, polarization)

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


@dataclass(frozen=True)
class LinkRoute:
    parameter: str
    command: str
    profile_model: str


class LinkRouter:
    def __init__(self, profile: SwitchBoxProfile = LCD74000F_PROFILE) -> None:
        self._profile = profile

    @property
    def profile(self) -> SwitchBoxProfile:
        return self._profile

    def resolve(self, parameter: str, polarization: str | None = None) -> LinkRoute:
        normalized_parameter = normalize_s_parameter(parameter)
        return LinkRoute(
            parameter=normalized_parameter,
            command=self._profile.command_for(normalized_parameter, polarization),
            profile_model=self._profile.model,
        )
