from __future__ import annotations

from dataclasses import dataclass

from catr_loss_calibrator.hardware.interfaces import InstrumentInfo


@dataclass
class PyVisaScpiInstrument:
    resource: str
    model: str = "UNKNOWN"
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
            raise RuntimeError("pyvisa is required for PyVisaScpiInstrument.") from exc
        rm = pyvisa.ResourceManager()
        self._resource = rm.open_resource(self.resource)
        self._resource.timeout = self.timeout_ms
        self._connected = True
        try:
            idn = str(self._resource.query("*IDN?"))
        except Exception:
            idn = self.model
        return InstrumentInfo(resource=self.resource, model=idn.split(",")[1] if "," in idn else self.model)

    def disconnect(self) -> None:
        if self._resource is not None:
            try:
                self._resource.close()
            finally:
                self._resource = None
        self._connected = False

    def send_command(self, command: str) -> str:
        if self._resource is None:
            raise RuntimeError("SCPI instrument is not connected.")
        if command.strip().endswith("?"):
            return str(self._resource.query(command))
        self._resource.write(command)
        return "OK"
