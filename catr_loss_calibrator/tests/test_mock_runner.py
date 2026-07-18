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

    def confirm(step, index, total):
        _ = step, index, total
        return next(actions)

    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path(tmpdir), confirm_step=confirm)
        runner.link_box.connect()
        runner.vna.connect()
        events = runner.run()
        assert "skip:CAL001-AUX" in events
        assert events[-1] == "cancel:CAL001-H"
        assert runner.state_machine.state == CalibrationState.CANCELLED


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
    from catr_loss_calibrator.presentation.main import run

    assert run() == 0
