from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from quiet_zone_tester.domains.link_management.switch_box_profiles import normalize_s_parameter

logger = logging.getLogger(__name__)


class LinkSwitchBoxController(Protocol):
    @property
    def is_connected(self) -> bool:
        ...

    def select_s_parameter(self, parameter: str) -> str:
        ...

    def send_command(self, command: str) -> str:
        ...


class LinkServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class LinkService:
    controller: LinkSwitchBoxController

    def select_s_parameter(self, parameter: str) -> str:
        self._ensure_connected()
        parameter = normalize_s_parameter(parameter)
        try:
            command = self.controller.select_s_parameter(parameter)
        except Exception as exc:
            logger.exception("Switch-box S-parameter routing failed.")
            raise LinkServiceError(f"Switch-box route selection failed: {exc}") from exc

        logger.info("Switch box routed %s with command %s.", parameter, command)
        return command

    def send_command(self, command: str) -> str:
        self._ensure_connected()
        command = str(command).strip()
        if not command:
            raise LinkServiceError("Switch-box command cannot be empty.")

        send_command = getattr(self.controller, "send_command", None)
        if not callable(send_command):
            raise LinkServiceError("Switch-box controller does not support raw commands.")

        try:
            response = str(send_command(command))
        except Exception as exc:
            logger.exception("Switch-box command failed.")
            raise LinkServiceError(f"Switch-box command failed: {exc}") from exc

        logger.info("Switch box command executed: %s -> %s.", command, response)
        return response

    def _ensure_connected(self) -> None:
        if not self.controller.is_connected:
            raise LinkServiceError("Switch-box controller is not connected.")
