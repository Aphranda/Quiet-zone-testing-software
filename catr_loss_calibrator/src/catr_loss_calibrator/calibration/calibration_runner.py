from __future__ import annotations

from dataclasses import dataclass

from catr_loss_calibrator.calibration.models import CalibrationItem


@dataclass
class CalibrationRunner:
    item: CalibrationItem

    def step_ids(self) -> tuple[str, ...]:
        return tuple(step.id for step in self.item.steps)

