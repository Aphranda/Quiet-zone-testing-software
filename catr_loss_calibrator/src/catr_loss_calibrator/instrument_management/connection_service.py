from __future__ import annotations

from dataclasses import dataclass

from catr_loss_calibrator.hardware.interfaces import InstrumentInfo, LinkBox, Vna
from catr_loss_calibrator.hardware.link_box.lcd74000f import Lcd74000fLinkBox
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna
from catr_loss_calibrator.hardware.vna.pyvisa_vna import PyVisaVna
from catr_loss_calibrator.instrument_management.recovery import ConnectionRecoveryPolicy
from catr_loss_calibrator.instrument_management.models import InstrumentConnectionConfig, InstrumentState


@dataclass
class InstrumentConnectionService:
    vna: Vna
    link_box: LinkBox
    recovery_policy: ConnectionRecoveryPolicy = ConnectionRecoveryPolicy()

    @classmethod
    def mock(cls) -> "InstrumentConnectionService":
        return cls(vna=MockVna(), link_box=MockLinkBox())

    @classmethod
    def from_configs(
        cls,
        *,
        vna_config: InstrumentConnectionConfig,
        link_box_config: InstrumentConnectionConfig,
    ) -> "InstrumentConnectionService":
        vna = (
            MockVna()
            if vna_config.use_mock
            else PyVisaVna(resource=vna_config.resource, model=vna_config.model, timeout_ms=vna_config.timeout_ms)
        )
        link_box = (
            MockLinkBox()
            if link_box_config.use_mock
            else Lcd74000fLinkBox(
                resource=link_box_config.resource,
                model=link_box_config.model,
                timeout_ms=link_box_config.timeout_ms,
            )
        )
        return cls(vna=vna, link_box=link_box)

    def connect_all(self) -> tuple[InstrumentInfo, InstrumentInfo]:
        self.recovery_policy.validate()
        last_error: Exception | None = None
        for attempt in range(self.recovery_policy.max_retries + 1):
            try:
                vna_info = self.vna.connect()
                link_info = self.link_box.connect()
                return vna_info, link_info
            except Exception as exc:
                last_error = exc
                self._cleanup_connected()
                if attempt >= self.recovery_policy.max_retries:
                    raise
        assert last_error is not None
        raise last_error

    def disconnect_all(self) -> None:
        self._cleanup_connected()

    def snapshot(self) -> tuple[InstrumentState, InstrumentState]:
        vna_state = InstrumentState(
            name="VNA",
            is_connected=self.vna.is_connected,
            resource=getattr(self.vna, "resource", ""),
            model=getattr(self.vna, "model", ""),
        )
        link_box_state = InstrumentState(
            name="LinkBox",
            is_connected=self.link_box.is_connected,
            resource=getattr(self.link_box, "resource", ""),
            model=getattr(self.link_box, "model", ""),
        )
        return vna_state, link_box_state

    def _cleanup_connected(self) -> None:
        if self.link_box.is_connected:
            self.link_box.disconnect()
        if self.vna.is_connected:
            self.vna.disconnect()
