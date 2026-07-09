from __future__ import annotations

import logging
import time

from quiet_zone_tester.hardware.interfaces import InstrumentInfo
from quiet_zone_tester.domains.link_management import LinkRouter

logger = logging.getLogger(__name__)


class MockSwitchBoxController:
    """Mock switch box for workflow testing without RF switch hardware."""

    def __init__(self) -> None:
        self._connected = False
        self._selected_parameter = "S21"
        self._selected_command = "PASSIVE"

    def connect(self) -> InstrumentInfo:
        logger.info("Connecting mock switch box.")
        time.sleep(0.2)
        self._connected = True
        return InstrumentInfo(
            resource_name="MOCK::SWITCH::001",
            model="Mock RF Switch Box",
            serial_number="SW-MOCK-001",
            is_mock=True,
        )

    def disconnect(self) -> None:
        logger.info("Disconnecting mock switch box.")
        time.sleep(0.1)
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def select_s_parameter(self, parameter: str) -> str:
        self._ensure_connected()
        route = LinkRouter.for_model("MOCK").resolve(parameter)

        time.sleep(0.08)
        self._selected_parameter = route.parameter
        self._selected_command = route.command
        logger.info(
            "Mock switch box selected %s with command %s.",
            self._selected_parameter,
            self._selected_command,
        )
        return self._selected_command

    def send_command(self, command: str) -> str:
        self._ensure_connected()
        command = command.strip()
        if not command:
            raise ValueError("Switch box command cannot be empty.")

        time.sleep(0.08)
        self._selected_command = command
        logger.info("Mock switch box executed command %s.", command)
        return command

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Mock switch box is not connected.")
