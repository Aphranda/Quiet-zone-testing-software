from __future__ import annotations

from dataclasses import dataclass, field

from catr_loss_calibrator.instrument_management.models import InstrumentState


@dataclass
class InstrumentManager:
    states: dict[str, InstrumentState] = field(default_factory=dict)

    def update_state(self, state: InstrumentState) -> None:
        self.states[state.name] = state

    def snapshot(self) -> tuple[InstrumentState, ...]:
        return tuple(self.states.values())

