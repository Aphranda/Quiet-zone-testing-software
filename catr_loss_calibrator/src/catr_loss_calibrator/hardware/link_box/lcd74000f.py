from __future__ import annotations

from dataclasses import dataclass

from catr_loss_calibrator.hardware.interfaces import InstrumentInfo, LinkBox


@dataclass
class Lcd74000fLinkBox(LinkBox):
    resource: str
    model: str = "LCD74000F"
    timeout_ms: int = 10_000

    def __post_init__(self) -> None:
        self._connected = False
        self._resource = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> InstrumentInfo:
        try:
            import pyvisa
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pyvisa is required for Lcd74000fLinkBox.") from exc
        rm = pyvisa.ResourceManager()
        self._resource = rm.open_resource(self.resource)
        self._resource.timeout = self.timeout_ms
        self._connected = True
        return InstrumentInfo(resource=self.resource, model=self.model)

    def disconnect(self) -> None:
        if self._resource is not None:
            try:
                self._resource.close()
            finally:
                self._resource = None
        self._connected = False

    def send_command(self, command: str) -> str:
        if self._resource is None:
            raise RuntimeError("Link box is not connected.")
        command = command.strip()
        if not command:
            raise RuntimeError("Link box command is empty.")
        if command.endswith("?"):
            return str(self._resource.query(command)).strip()
        self._resource.write(command)
        self._wait_for_operation_complete()
        self._raise_for_error_queue()
        return "OK"

    def _wait_for_operation_complete(self) -> None:
        if self._resource is None:
            raise RuntimeError("Link box is not connected.")
        try:
            response = str(self._resource.query("*OPC?")).strip()
        except Exception:
            return
        if response not in {"", "1"}:
            raise RuntimeError(f"Link box *OPC? returned unexpected response: {response}")

    def _raise_for_error_queue(self) -> None:
        if self._resource is None:
            raise RuntimeError("Link box is not connected.")
        try:
            count = str(self._resource.query("SYSTem:ERRor:COUNt?")).strip()
            if count in {"", "0"}:
                return
            error = str(self._resource.query("SYSTem:ERRor:NEXT?")).strip()
        except Exception:
            return
        raise RuntimeError(f"Link box error queue: {error or count}")
