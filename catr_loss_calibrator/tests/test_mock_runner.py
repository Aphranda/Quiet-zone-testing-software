from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from catr_loss_calibrator.calibration.definitions import default_calibration_catalog
from catr_loss_calibrator.calibration.mock_runner import MockCalibrationRunner
from catr_loss_calibrator.calibration.state_machine import CalibrationState, CalibrationStateMachine
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna


def test_state_machine_enforces_order() -> None:
    machine = CalibrationStateMachine()
    assert machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM) == CalibrationState.WAIT_MANUAL_CONFIRM
    assert machine.transition(CalibrationState.CONFIGURE_LINK) == CalibrationState.CONFIGURE_LINK
    try:
        machine.transition(CalibrationState.DONE)
    except ValueError as exc:
        assert "Invalid state transition" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_mock_runner_creates_raw_and_metadata_artifacts() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path(tmpdir))
        runner.link_box.connect()
        runner.vna.connect()
        events = runner.run()
        assert events[0] == "start:LINK-CAL-001"
        assert runner.state_machine.state == CalibrationState.DONE
        assert (Path(tmpdir) / "raw").exists()
        assert (Path(tmpdir) / "metadata").exists()
        assert any(event.startswith("raw:") for event in events)
        assert any(event.startswith("metadata:") for event in events)
        overview = runner.overview()
        assert overview["completed_big_steps"] == len(item.steps)
        assert overview["completed_step_ids"] == tuple(step.id for step in item.steps)


def test_mock_runner_overview_reports_status_and_connections() -> None:
    item = default_calibration_catalog().get("LINK-CAL-002")
    runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path("unused"))
    overview = runner.overview()
    assert overview["item_id"] == "LINK-CAL-002"
    assert overview["state"] == "IDLE"
    assert overview["link_box_connected"] is False
    assert overview["vna_connected"] is False


def test_mock_runner_can_skip_and_cancel_steps() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    actions = iter(["skip", "cancel"])

    def confirm(step, substep, phase, index, total, substep_index, substep_total):
        _ = step, substep, phase, index, total, substep_index, substep_total
        return next(actions)

    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path(tmpdir), confirm_step=confirm)
        runner.link_box.connect()
        runner.vna.connect()
        events = runner.run()
        assert "skip:CAL001-AUX:AUX-A" in events
        assert events[-1] == "cancel:CAL001-AUX:AUX-B"
        assert runner.state_machine.state == CalibrationState.CANCELLED


def test_mock_runner_splits_aux_step_into_operator_confirmed_substeps() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    prompts: list[tuple[str, str]] = []

    def confirm(step, substep, phase, index, total, substep_index, substep_total):
        _ = index, total, substep_index, substep_total
        prompts.append((step.id, f"{phase}:{substep.id}"))
        if step.id == "CAL001-AUX" and phase == "saved" and substep.id == "AUX-C":
            return "cancel"
        return "continue"

    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path(tmpdir), confirm_step=confirm)
        runner.link_box.connect()
        runner.vna.connect()
        events = runner.run()
        assert prompts[:6] == [
            ("CAL001-AUX", "start:AUX-A"),
            ("CAL001-AUX", "saved:AUX-A"),
            ("CAL001-AUX", "start:AUX-B"),
            ("CAL001-AUX", "saved:AUX-B"),
            ("CAL001-AUX", "start:AUX-C"),
            ("CAL001-AUX", "saved:AUX-C"),
        ]
        assert any(event.startswith("raw:LINK-CAL-001_CAL001-AUX_AUX-A") for event in events)
        assert any(event.startswith("raw:LINK-CAL-001_CAL001-AUX_AUX-B") for event in events)
        assert any(event.startswith("raw:LINK-CAL-001_CAL001-AUX_AUX-C") for event in events)


def test_saved_prompt_retry_repeats_current_substep() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    actions = iter(["continue", "retry", "continue", "cancel"])
    prompts: list[str] = []

    def confirm(step, substep, phase, index, total, substep_index, substep_total):
        _ = index, total, substep_index, substep_total
        prompts.append(f"{phase}:{step.id}:{substep.id}")
        return next(actions)

    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path(tmpdir), confirm_step=confirm)
        runner.link_box.connect()
        runner.vna.connect()
        events = runner.run()

    assert prompts == [
        "start:CAL001-AUX:AUX-A",
        "saved:CAL001-AUX:AUX-A",
        "start:CAL001-AUX:AUX-A",
        "saved:CAL001-AUX:AUX-A",
    ]
    assert "retry:CAL001-AUX:AUX-A" in events
    assert sum(1 for event in events if event.startswith("raw:LINK-CAL-001_CAL001-AUX_AUX-A")) == 2


def test_saved_prompt_next_skips_without_double_counting_substep() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    actions = iter(["continue", "skip", "cancel"])

    def confirm(step, substep, phase, index, total, substep_index, substep_total):
        _ = step, substep, phase, index, total, substep_index, substep_total
        return next(actions)

    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path(tmpdir), confirm_step=confirm)
        runner.link_box.connect()
        runner.vna.connect()
        events = runner.run()
        overview = runner.overview()

    assert "skip:CAL001-AUX:AUX-A" in events
    assert overview["completed_steps"] == 1
    assert overview["completed_substep_ids"] == ("CAL001-AUX:AUX-A",)


def test_runner_orders_polarized_substeps_v_before_h() -> None:
    item = default_calibration_catalog().get("LINK-CAL-002")
    step = next(step for step in item.steps if step.id == "CAL002-MAIN")
    runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path("unused"))

    substep_ids = [substep.id for substep in runner._substeps_for(step)]

    assert substep_ids == [
        "V-THRU",
        "V-DUTAMP1",
        "V-AMP2",
        "H-THRU",
        "H-DUTAMP1",
        "H-AMP2",
    ]


def test_mock_runner_rejects_unconnected_instruments() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path("unused"))
    try:
        runner.run()
    except RuntimeError as exc:
        assert "must be connected" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_presentation_cli_runs_demo_flow() -> None:
    from catr_loss_calibrator.presentation.main import run_cli

    assert run_cli() == 0
