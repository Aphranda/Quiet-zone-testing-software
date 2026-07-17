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
        """Deprecated compatibility route; new link operations should use send_command()."""
        ...

    def send_command(self, command: str) -> str:
        ...


class LinkServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class LinkService:
    controller: LinkSwitchBoxController

    def select_s_parameter(self, parameter: str) -> str:
        """Deprecated compatibility route for historical S-parameter based switching."""
        self._ensure_connected()
        parameter = normalize_s_parameter(parameter)
        try:
            command = self.controller.select_s_parameter(parameter)
        except Exception as exc:
            logger.exception("Switch-box S-parameter routing failed.")
            raise LinkServiceError(f"Switch-box route selection failed: {exc}") from exc

        logger.info("Switch box routed %s with command %s.", parameter, command)
        return command

    def select_polarization(self, polarization: str | None) -> str:
        polarization = str(polarization or "").strip().upper()
        if polarization not in {"H", "V"}:
            raise LinkServiceError("Polarization must be H or V.")
        return self.send_command(f"CONFigure:LINK {polarization}, VNA1")

    def select_dut_path(self, target: str) -> str:
        target = str(target).strip().upper()
        if target not in {"VNA2", "VNA2_AMP1", "SA"}:
            raise LinkServiceError("DUT target must be VNA2, VNA2_AMP1, or SA.")
        if target == "VNA2":
            return self.send_command("CONFigure:LINK DUT, VNA2")
        if target == "VNA2_AMP1":
            return self.send_command("CONFigure:LINK DUT, AMP1, VNA2")
        return self.send_command("CONFigure:LINK DUT, AMP1, SA")

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
