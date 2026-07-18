from __future__ import annotations

from dataclasses import dataclass

from catr_loss_calibrator.hardware.interfaces import LinkBox


@dataclass
class LinkService:
    link_box: LinkBox

    def apply_commands(self, commands: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(self.link_box.send_command(command) for command in commands)

