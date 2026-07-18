from __future__ import annotations

from catr_loss_calibrator.calibration.definitions import default_calibration_catalog


def run() -> int:
    catalog = default_calibration_catalog()
    print("CATR Loss Calibrator")
    print("Available calibration items:")
    for item in catalog.items:
        print(f"- {item.id}: {item.name} ({len(item.steps)} steps)")
    return 0

