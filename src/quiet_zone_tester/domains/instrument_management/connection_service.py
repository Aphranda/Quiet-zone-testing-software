from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from quiet_zone_tester.hardware import InstrumentInfo

logger = logging.getLogger(__name__)


class ManagedInstrumentController(Protocol):
    @property
    def is_connected(self) -> bool:
        ...

    def connect(self) -> InstrumentInfo:
        ...

    def disconnect(self) -> None:
        ...


class InstrumentConnectionServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstrumentConnectionService:
    def connect_controller(self, controller: ManagedInstrumentController | None, name: str) -> InstrumentInfo:
        if controller is None:
            raise InstrumentConnectionServiceError(f"{name} controller is not configured.")
        if controller.is_connected:
            controller.disconnect()
        return controller.connect()

    def disconnect_controller(self, controller: ManagedInstrumentController | None, name: str) -> None:
        if controller is None:
            return
        try:
            if controller.is_connected:
                controller.disconnect()
        except Exception as exc:
            logger.exception("Failed to disconnect %s.", name)
            raise InstrumentConnectionServiceError(f"{name} disconnect failed: {exc}") from exc

    def disconnect_all(self, controllers: list[ManagedInstrumentController | None]) -> None:
        errors: list[Exception] = []
        for controller in controllers:
            if controller is None:
                continue
            try:
                if controller.is_connected:
                    controller.disconnect()
            except Exception as exc:  # noqa: BLE001 - service must collect driver failures.
                logger.exception("Failed to disconnect controller.")
                errors.append(exc)

        if errors:
            raise InstrumentConnectionServiceError(f"Failed to disconnect {len(errors)} instrument(s).")

    def cleanup_after_failed_connect(self, controllers: list[ManagedInstrumentController | None]) -> None:
        for controller in controllers:
            if controller is None:
                continue
            try:
                controller.disconnect()
            except Exception:
                logger.exception("Failed to clean up controller after connection failure.")

    def cleanup_controller(self, controller: ManagedInstrumentController | None, name: str) -> None:
        if controller is None:
            return
        try:
            controller.disconnect()
        except Exception:
            logger.exception("Failed to clean up %s after connection failure.", name)
