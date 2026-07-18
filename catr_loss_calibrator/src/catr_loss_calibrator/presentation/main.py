from __future__ import annotations

import sys
from pathlib import Path

from catr_loss_calibrator.calibration.definitions import default_calibration_catalog
from catr_loss_calibrator.calibration.mock_runner import MockCalibrationRunner
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna


def run() -> int:
    if "--interactive" in sys.argv[1:]:
        return run_interactive()
    catalog = default_calibration_catalog()
    print("CATR Loss Calibrator")
    print("Available calibration items:")
    for item in catalog.items:
        print(f"- {item.id}: {item.name} ({len(item.steps)} steps)")
    first_item = catalog.items[0]
    runner = MockCalibrationRunner(first_item, MockVna(), MockLinkBox(), Path("catr_loss_calibrator_output"))
    runner.link_box.connect()
    runner.vna.connect()
    print("Runner overview before run:")
    print(runner.overview())
    runner.run()
    print("Runner overview after run:")
    print(runner.overview())
    print(f"Mock runner state: {runner.state_machine.state.value}")
    print(f"Mock runner events: {len(runner.events)}")
    return 0


def run_interactive() -> int:
    catalog = default_calibration_catalog()
    print("CATR Loss Calibrator - Interactive")
    for index, item in enumerate(catalog.items, start=1):
        print(f"{index}. {item.id}: {item.name}")
    selection = input("Select calibration item number: ").strip()
    try:
        item = catalog.items[int(selection) - 1]
    except Exception:
        print("Invalid selection.")
        return 1

    def confirm(step, step_index: int, total: int) -> str:
        print(runner.format_step_status(step, step_index, total))
        action = input("Continue / Skip / Retry / Cancel ? [c/s/r/x]: ").strip().lower()
        return {"c": "continue", "s": "skip", "r": "retry", "x": "cancel"}.get(action, "continue")

    runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path("catr_loss_calibrator_output"), confirm_step=confirm)
    runner.link_box.connect()
    runner.vna.connect()
    print("Runner overview before run:")
    print(runner.overview())
    runner.run()
    print("Runner overview after run:")
    print(runner.overview())
    print(f"State: {runner.state_machine.state.value}")
    print(f"Events: {len(runner.events)}")
    return 0
