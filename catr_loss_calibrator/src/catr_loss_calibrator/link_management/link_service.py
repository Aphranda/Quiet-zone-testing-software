from __future__ import annotations

from dataclasses import dataclass, field

from catr_loss_calibrator.hardware.interfaces import LinkBox
from catr_loss_calibrator.link_management.lcd74000f_profile import Lcd74000fProfile
from catr_loss_calibrator.link_management.models import LinkCommand, LinkRoute


@dataclass
class LinkService:
    link_box: LinkBox
    profile: Lcd74000fProfile = field(default_factory=Lcd74000fProfile)

    def apply_commands(self, commands: tuple[str | LinkCommand, ...]) -> tuple[str, ...]:
        return tuple(self.link_box.send_command(_command_text(command)) for command in commands)

    def apply_route(self, route: LinkRoute) -> str:
        self.profile.validate_route(route)
        return self.link_box.send_command(route.to_command().command)

    def apply_route_id(self, route_id: str) -> str:
        return self.apply_route(self.profile.get_route(route_id))


def _command_text(command: str | LinkCommand) -> str:
    if isinstance(command, LinkCommand):
        return command.command
    return command
