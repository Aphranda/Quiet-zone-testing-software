from __future__ import annotations

from dataclasses import dataclass, field

from catr_loss_calibrator.instrument_management.connection_service import InstrumentConnectionService
from catr_loss_calibrator.instrument_management.models import InstrumentConnectionConfig, InstrumentState
from catr_loss_calibrator.instrument_management.resource_lock import ResourceLock


@dataclass
class InstrumentManagementService:
    connection_service: InstrumentConnectionService
    lock: ResourceLock = field(default_factory=ResourceLock)
    owner: str = "catr_loss_calibrator"

    @classmethod
    def mock(cls) -> "InstrumentManagementService":
        return cls(connection_service=InstrumentConnectionService.mock())

    @classmethod
    def from_configs(
        cls,
        *,
        vna_config: InstrumentConnectionConfig,
        link_box_config: InstrumentConnectionConfig,
    ) -> "InstrumentManagementService":
        return cls(
            connection_service=InstrumentConnectionService.from_configs(
                vna_config=vna_config,
                link_box_config=link_box_config,
            )
        )

    def acquire_exclusive(self) -> None:
        self.lock.acquire("VNA", self.owner)
        self.lock.acquire("LINK_BOX", self.owner)

    def release_exclusive(self) -> None:
        self.lock.release("VNA", self.owner)
        self.lock.release("LINK_BOX", self.owner)

    def connect_all(self) -> tuple[InstrumentState, InstrumentState]:
        self.acquire_exclusive()
        try:
            self.connection_service.connect_all()
            return self.snapshot()
        except Exception:
            self.release_exclusive()
            raise

    def disconnect_all(self) -> None:
        try:
            self.connection_service.disconnect_all()
        finally:
            self.release_exclusive()

    def snapshot(self) -> tuple[InstrumentState, InstrumentState]:
        return self.connection_service.snapshot()
