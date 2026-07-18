from __future__ import annotations

from dataclasses import dataclass

from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna


@dataclass
class InstrumentConnectionService:
    vna: MockVna
    link_box: MockLinkBox

    @classmethod
    def mock(cls) -> "InstrumentConnectionService":
        return cls(vna=MockVna(), link_box=MockLinkBox())

    def connect_all(self) -> None:
        self.vna.connect()
        self.link_box.connect()

    def disconnect_all(self) -> None:
        self.vna.disconnect()
        self.link_box.disconnect()

