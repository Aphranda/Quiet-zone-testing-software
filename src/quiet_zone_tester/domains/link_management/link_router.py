from __future__ import annotations

from dataclasses import dataclass

from quiet_zone_tester.domains.link_management.switch_box_profiles import (
    SwitchBoxProfile,
    default_switch_box_profile,
    normalize_s_parameter,
)


@dataclass(frozen=True)
class LinkRoute:
    parameter: str
    command: str
    profile_model: str


class LinkRouter:
    def __init__(self, profile: SwitchBoxProfile) -> None:
        self._profile = profile

    @classmethod
    def for_model(cls, model: str) -> "LinkRouter":
        return cls(default_switch_box_profile(model))

    @property
    def profile(self) -> SwitchBoxProfile:
        return self._profile

    def resolve(self, parameter: str) -> LinkRoute:
        normalized_parameter = normalize_s_parameter(parameter)
        return LinkRoute(
            parameter=normalized_parameter,
            command=self._profile.command_for(normalized_parameter),
            profile_model=self._profile.model,
        )
