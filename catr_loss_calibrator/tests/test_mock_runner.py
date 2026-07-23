from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from catr_loss_calibrator.calibration.definitions import default_calibration_catalog
from catr_loss_calibrator.calibration.mock_runner import MockCalibrationRunner
from catr_loss_calibrator.calibration.recovery import CalibrationRunError
from catr_loss_calibrator.calibration.state_machine import CalibrationState, CalibrationStateMachine
from catr_loss_calibrator.hardware.interfaces import SParameterTrace
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna
from catr_loss_calibrator.project.config import DEFAULT_VNA_POWER_DBM, SweepConfig
from catr_loss_calibrator.storage.loss_file_policy import LossFilePolicy
from catr_loss_calibrator.storage.workspace import (
    CalibrationRunContext,
    create_session_context,
    load_latest_summary,
    workspace_for_catalog,
)


class TimeoutLinkBox(MockLinkBox):
    def send_command(self, command: str) -> str:
        if command.strip().upper().startswith("CONFIGURE:LINK"):
            raise TimeoutError("LCD74000F did not respond.")
        return super().send_command(command)


class TimeoutReadVna(MockVna):
    def read_s_parameter(self, parameter: str = "S21"):
        raise TimeoutError("VNA sweep timed out.")


class ChangingReadVna(MockVna):
    def __init__(self, values: tuple[float, ...]) -> None:
        super().__init__()
        self._values = list(values)

    def read_s_parameter(self, parameter: str = "S21"):
        value = self._values.pop(0) if self._values else -99.0
        frequency = np.linspace(self._start_hz, self._stop_hz, self._points)
        return SParameterTrace(
            frequency_hz=frequency,
            value_db=np.full(self._points, value, dtype=float),
            phase_deg=np.zeros(self._points),
            parameter=parameter.upper(),
        )


class RealLikeVna(MockVna):
    def __init__(self) -> None:
        super().__init__(resource="TCPIP0::127.0.0.1::inst0::INSTR", model="E5080B")


class RecordingPowerVna(MockVna):
    def __init__(self) -> None:
        super().__init__()
        self.power_history: list[float] = []

    def configure_power(self, power_dbm: float) -> None:
        super().configure_power(power_dbm)
        self.power_history.append(power_dbm)


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
        assert overview["output_root"] == tmpdir
        expected_substeps = sum(len(runner._substeps_for(step)) for step in item.steps)
        assert len(overview["raw_files"]) == expected_substeps
        assert len(overview["metadata_files"]) == expected_substeps
        assert all(Path(path).exists() for path in overview["raw_files"])
        assert all(Path(path).exists() for path in overview["metadata_files"])


def test_mock_runner_writes_artifacts_inside_session_workspace() -> None:
    catalog = default_calibration_catalog()
    item = catalog.get("LINK-CAL-003")
    with TemporaryDirectory() as tmpdir:
        workspace = workspace_for_catalog(catalog, Path(tmpdir))
        session = create_session_context(
            workspace=workspace,
            run=CalibrationRunContext(
                project_code="PROJECT1",
                calibration_stage="after_repair",
                run_label="R02",
                operator="operator-a",
                operator_note="cable changed",
            ),
            item_id=item.id,
        )
        runner = MockCalibrationRunner(
            item,
            MockVna(),
            MockLinkBox(),
            session.session_root,
            vna_settings={"points": 3},
            session_context=session,
        )
        runner.link_box.connect()
        runner.vna.connect()
        runner.run()

        overview = runner.overview()
        manifest_path = Path(str(overview["manifest_file"]))
        assert overview["workspace_id"] == workspace.workspace_id
        assert overview["session_id"] == session.session_id
        assert overview["session_root"] == str(session.session_root)
        assert overview["publishable"] is True
        assert overview["publish_blockers"] == ()
        assert overview["project_code"] == "PROJECT1"
        assert overview["calibration_stage"] == "after_repair"
        assert overview["run_label"] == "R02"
        assert manifest_path == session.session_root / "session_manifest.json"
        assert manifest_path.exists()
        assert Path(str(overview["latest_index_file"])).exists()
        assert all(Path(path).is_relative_to(session.session_root) for path in overview["raw_files"])
        assert all(Path(path).is_relative_to(session.session_root) for path in overview["loss_files"])
        assert all(Path(path).is_relative_to(session.session_root) for path in overview["metadata_files"])

        metadata_path = next(Path(path) for path in overview["metadata_files"])
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["run_uid"] == session.run_uid
        assert metadata["workspace_id"] == workspace.workspace_id
        assert metadata["session_root"] == str(session.session_root)
        assert metadata["config_hash"] == workspace.config_hash
        assert metadata["project_code"] == "PROJECT1"
        assert metadata["calibration_stage"] == "after_repair"
        assert metadata["run_label"] == "R02"
        assert metadata["operator"] == "operator-a"
        assert metadata["operator_note"] == "cable changed"

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["state"] == "DONE"
        assert manifest["last_event"] == "done:LINK-CAL-003"
        assert manifest["raw_files"] == list(overview["raw_files"])
        assert manifest["loss_files"] == list(overview["loss_files"])
        assert manifest["metadata_files"] == list(overview["metadata_files"])

        latest = load_latest_summary(workspace=workspace, run=session.run, item_id=item.id)
        assert latest["session_id"] == session.session_id
        assert latest["manifest_file"] == str(manifest_path)


def test_mock_runner_cancelled_session_does_not_overwrite_latest_success() -> None:
    catalog = default_calibration_catalog()
    item = catalog.get("LINK-CAL-003")
    with TemporaryDirectory() as tmpdir:
        workspace = workspace_for_catalog(catalog, Path(tmpdir))
        run_context = CalibrationRunContext(project_code="PROJECT1", calibration_stage="initial", run_label="R01")
        success_session = create_session_context(
            workspace=workspace,
            run=run_context,
            item_id=item.id,
            now=datetime(2026, 7, 19, 10, 0, 0, tzinfo=timezone.utc),
        )
        success = MockCalibrationRunner(
            item,
            MockVna(),
            MockLinkBox(),
            success_session.session_root,
            vna_settings={"points": 3},
            session_context=success_session,
        )
        success.link_box.connect()
        success.vna.connect()
        success.run()

        cancelled_session = create_session_context(
            workspace=workspace,
            run=run_context,
            item_id=item.id,
            now=datetime(2026, 7, 19, 10, 1, 0, tzinfo=timezone.utc),
        )
        cancelled = MockCalibrationRunner(
            item,
            MockVna(),
            MockLinkBox(),
            cancelled_session.session_root,
            confirm_step=lambda *_args: "cancel",
            vna_settings={"points": 3},
            session_context=cancelled_session,
        )
        cancelled.link_box.connect()
        cancelled.vna.connect()
        cancelled.run()

        latest = load_latest_summary(workspace=workspace, run=run_context, item_id=item.id)
        cancelled_overview = cancelled.overview()
        assert latest["session_id"] == success_session.session_id
        assert Path(str(cancelled_overview["manifest_file"])).exists()
        assert cancelled_overview["latest_index_file"] == ""


def test_mock_runner_failed_session_does_not_overwrite_latest_success() -> None:
    catalog = default_calibration_catalog()
    item = catalog.get("LINK-CAL-001")
    with TemporaryDirectory() as tmpdir:
        workspace = workspace_for_catalog(catalog, Path(tmpdir))
        run_context = CalibrationRunContext(project_code="PROJECT1", calibration_stage="initial", run_label="R01")
        success_session = create_session_context(
            workspace=workspace,
            run=run_context,
            item_id=item.id,
            now=datetime(2026, 7, 19, 10, 0, 0, tzinfo=timezone.utc),
        )
        success = MockCalibrationRunner(
            item,
            MockVna(),
            MockLinkBox(),
            success_session.session_root,
            vna_settings={"points": 3},
            session_context=success_session,
        )
        success.link_box.connect()
        success.vna.connect()
        success.run()

        failed_session = create_session_context(
            workspace=workspace,
            run=run_context,
            item_id=item.id,
            now=datetime(2026, 7, 19, 10, 1, 0, tzinfo=timezone.utc),
        )
        failed = MockCalibrationRunner(
            item,
            TimeoutReadVna(),
            MockLinkBox(),
            failed_session.session_root,
            vna_settings={"points": 3},
            session_context=failed_session,
        )
        failed.link_box.connect()
        failed.vna.connect()
        try:
            failed.run()
        except CalibrationRunError:
            pass
        else:
            raise AssertionError("Expected CalibrationRunError.")

        latest = load_latest_summary(workspace=workspace, run=run_context, item_id=item.id)
        failed_overview = failed.overview()
        assert latest["session_id"] == success_session.session_id
        assert Path(str(failed_overview["manifest_file"])).exists()
        assert failed_overview["latest_index_file"] == ""


def test_mock_runner_creates_final_loss_files() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(
            item,
            MockVna(),
            MockLinkBox(),
            Path(tmpdir),
            vna_settings={"points": 3, "G_STD_HORN_H": 20.0, "G_STD_HORN_V": 21.0},
        )
        runner.link_box.connect()
        runner.vna.connect()
        runner.run()

        loss_dir = Path(tmpdir) / "loss"
        assert (loss_dir / "L_AUX_A_10_15G_F10_17G_H10_15G.csv").exists()
        h_path = loss_dir / "L_CH_INT_H_10_15G_F10_17G_H10_15G.csv"
        assert h_path.exists()
        content = h_path.read_text(encoding="utf-8-sig")
        assert "L_CH_INT_H" in content
        assert "-18" in content
        overview = runner.overview()
        assert str(h_path) in overview["loss_files"]
        assert all(Path(path).exists() for path in overview["loss_files"])


def test_non_mock_runner_records_missing_standard_horn_gain_without_stopping() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(item, RealLikeVna(), MockLinkBox(), Path(tmpdir), vna_settings={"points": 3})
        runner.link_box.connect()
        runner.vna.connect()
        runner.run()

        overview = runner.overview()
        assert overview["measurement_settings"]["horn_gain_status"] == "missing_default_zero"
        assert "standard horn gain missing; using 0 dB default" in overview["measurement_warnings"]


def test_runner_writes_measurement_warnings_to_metadata_and_manifest() -> None:
    catalog = default_calibration_catalog()
    item = catalog.get("LINK-CAL-001")
    with TemporaryDirectory() as tmpdir:
        workspace = workspace_for_catalog(catalog, Path(tmpdir))
        session = create_session_context(
            workspace=workspace,
            run=CalibrationRunContext(project_code="PROJECT1", calibration_stage="initial", run_label="R01"),
            item_id=item.id,
        )
        runner = MockCalibrationRunner(
            item,
            MockVna(),
            MockLinkBox(),
            session.session_root,
            vna_settings={"points": 3, "horn_gain_warnings": ("horn gain file changed",)},
            session_context=session,
        )
        runner.link_box.connect()
        runner.vna.connect()
        runner.run()

        overview = runner.overview()
        manifest = json.loads(Path(str(overview["manifest_file"])).read_text(encoding="utf-8"))
        metadata = json.loads(Path(str(overview["metadata_files"][0])).read_text(encoding="utf-8"))
        assert "horn gain file changed" in manifest["measurement_warnings"]
        assert "horn gain file changed" in metadata["measurement_warnings"]
        assert metadata["measurement_settings"]["points"] == 3


def test_runner_records_horn_gain_hash_in_measurement_settings() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    runner = MockCalibrationRunner(
        item,
        MockVna(),
        MockLinkBox(),
        Path("unused"),
        vna_settings={
            "points": 3,
            "horn_gain_file": "horn.csv",
            "horn_gain_sha256": "abc123",
        },
    )

    settings = runner.overview()["measurement_settings"]

    assert settings["horn_gain_file"] == "horn.csv"
    assert settings["horn_gain_sha256"] == "abc123"


def test_runner_interpolation_allows_extrapolation_for_operator_review_flow() -> None:
    values = MockCalibrationRunner._interpolate_value(
        "S21_AUX_A",
        np.array([1.0, 2.0, 3.0]),
        np.array([1.5, 2.0, 2.5]),
        np.array([-1.0, -2.0, -3.0]),
    )

    assert np.allclose(values, np.array([-1.0, -2.0, -3.0]))


def test_mock_runner_uses_project_band_config_for_loss_filenames() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    policy = LossFilePolicy.from_band_config(
        {
            "feed_horn_bands": [
                {"feed": "F_CUSTOM", "horn": "H_CUSTOM", "band": "33_40G"},
            ]
        }
    )
    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(
            item,
            MockVna(),
            MockLinkBox(),
            Path(tmpdir),
            vna_settings={"points": 3},
            feed="F_CUSTOM",
            horn="H_CUSTOM",
            loss_file_policy=policy,
        )
        runner.link_box.connect()
        runner.vna.connect()
        runner.run()

        overview = runner.overview()
        assert any(Path(path).name == "L_AUX_A_33_40G_F_CUSTOM_H_CUSTOM.csv" for path in overview["loss_files"])


def test_mock_runner_writes_output_roles_to_trace_and_metadata_files() -> None:
    item = default_calibration_catalog().get("LINK-CAL-003")
    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path(tmpdir), vna_settings={"points": 3})
        runner.link_box.connect()
        runner.vna.connect()
        runner.run()

        raw_path = Path(tmpdir) / "raw" / "LINK-CAL-003_CAL003-DUT-SA_DUT-SA.csv"
        metadata_path = Path(tmpdir) / "metadata" / "LINK-CAL-003_CAL003-DUT-SA_DUT-SA.json"

        assert "temporary" in raw_path.read_text(encoding="utf-8-sig")
        metadata = metadata_path.read_text(encoding="utf-8")
        assert '"input_roles": [\n    "temporary"\n  ]' in metadata
        assert '"output_roles": [\n    "final"\n  ]' in metadata


def test_mock_runner_emits_link_command_events() -> None:
    item = default_calibration_catalog().get("LINK-CAL-002")
    received: list[str] = []
    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(
            item,
            MockVna(),
            MockLinkBox(),
            Path(tmpdir),
            event_callback=received.append,
            vna_settings={"points": 3},
        )
        runner.link_box.connect()
        runner.vna.connect()
        runner.run()

    assert any(event == "link:CAL002-DUT-VNA2:S21_DUT_VNA_RAW:CONFigure:LINK DUT, VNA2" for event in received)
    assert any("CONFigure:LINK V, VNA1" in event for event in received)


def test_mock_runner_accepts_external_horn_gain_arrays() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(
            item,
            MockVna(),
            MockLinkBox(),
            Path(tmpdir),
            vna_settings={
                "points": 3,
                "external_inputs": {
                    "G_STD_HORN_H": np.array([10.0, 11.0, 12.0]),
                    "G_STD_HORN_V": np.array([13.0, 14.0, 15.0]),
                },
            },
        )
        runner.link_box.connect()
        runner.vna.connect()
        runner.run()

        h_path = Path(tmpdir) / "loss" / "L_CH_INT_H_10_15G_F10_17G_H10_15G.csv"
        content = h_path.read_text(encoding="utf-8-sig")
        assert "-9" in content
        assert "-10" in content


def test_mock_runner_overview_reports_status_and_connections() -> None:
    item = default_calibration_catalog().get("LINK-CAL-002")
    runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path("unused"))
    overview = runner.overview()
    assert overview["item_id"] == "LINK-CAL-002"
    assert overview["state"] == "IDLE"
    assert overview["link_box_connected"] is False
    assert overview["vna_connected"] is False


def test_mock_runner_uses_instrument_page_vna_settings() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    vna = MockVna()
    runner = MockCalibrationRunner(
        item,
        vna,
        MockLinkBox(),
        Path("unused"),
        vna_settings={
            "start_ghz": 12.0,
            "stop_ghz": 12.2,
            "points": 21,
            "vna_power_dbm": -7.5,
            "if_bandwidth_hz": 2000.0,
            "parameter": "S21",
            "continuous_sweep": False,
        },
    )
    runner.link_box.connect()
    runner.vna.connect()
    runner.state_machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM)

    runner._run_substep(item.steps[0], runner._substeps_for(item.steps[0])[0])

    assert vna._start_hz == 12e9
    assert vna._stop_hz == 12.2e9
    assert vna._points == 21
    assert vna._power_dbm == -7.5
    assert vna._if_bandwidth_hz == 2000.0


def test_mock_runner_defaults_vna_power_to_minus_30_dbm() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    vna = MockVna()
    runner = MockCalibrationRunner(item, vna, MockLinkBox(), Path("unused"))

    settings = runner._normalized_vna_settings()

    assert settings["power_dbm"] == DEFAULT_VNA_POWER_DBM
    assert SweepConfig().power_dbm == DEFAULT_VNA_POWER_DBM
    assert vna._power_dbm == DEFAULT_VNA_POWER_DBM


def test_runner_allows_substep_vna_power_overrides() -> None:
    item = default_calibration_catalog().get("LINK-CAL-002")
    step = next(step for step in item.steps if step.id == "CAL002-MAIN")
    with TemporaryDirectory() as tmpdir:
        vna = RecordingPowerVna()
        runner = MockCalibrationRunner(
            item,
            vna,
            MockLinkBox(),
            Path(tmpdir),
            vna_settings={
                "points": 3,
                "vna_power_dbm": -30.0,
                "substep_power_dbm": {
                    "CAL002-MAIN:V-THRU": -10.0,
                    "CAL002-MAIN:V-DUTAMP1": -35.0,
                },
            },
        )
        runner.link_box.connect()
        runner.vna.connect()
        v_thru = next(substep for substep in runner._substeps_for(step) if substep.id == "V-THRU")
        v_amp1 = next(substep for substep in runner._substeps_for(step) if substep.id == "V-DUTAMP1")

        runner.state_machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM)
        runner._run_substep(step, v_thru)
        runner.state_machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM)
        runner._run_substep(step, v_amp1)

        assert vna.power_history == [-10.0, -35.0]
        first_metadata = json.loads((Path(tmpdir) / "metadata" / "LINK-CAL-002_CAL002-MAIN_V-THRU.json").read_text(encoding="utf-8"))
        second_metadata = json.loads((Path(tmpdir) / "metadata" / "LINK-CAL-002_CAL002-MAIN_V-DUTAMP1.json").read_text(encoding="utf-8"))
        assert first_metadata["measurement_settings"]["power_dbm"] == -10.0
        assert second_metadata["measurement_settings"]["power_dbm"] == -35.0


def test_runner_uses_substep_measurement_parameter() -> None:
    item = default_calibration_catalog().get("LINK-CAL-002")
    step = next(step for step in item.steps if step.id == "CAL002-MAIN")
    substep = next(substep for substep in step.substeps if substep.id == "V-AMP2")
    with TemporaryDirectory() as tmpdir:
        vna = MockVna()
        runner = MockCalibrationRunner(item, vna, MockLinkBox(), Path(tmpdir), vna_settings={"points": 3})
        runner.link_box.connect()
        runner.vna.connect()
        runner.state_machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM)

        runner._run_substep(step, substep)

        metadata = json.loads((Path(tmpdir) / "metadata" / "LINK-CAL-002_CAL002-MAIN_V-AMP2.json").read_text(encoding="utf-8"))
        assert vna._parameter == "S12"
        assert metadata["measurement_settings"]["parameter"] == "S12"


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
        overview = runner.overview()
        assert overview["failure_kind"] == "operator_cancelled"
        assert overview["failure_action"] == "stopped_by_operator"


def test_mock_runner_marks_link_box_timeout_as_failed_with_recovery_action() -> None:
    item = default_calibration_catalog().get("LINK-CAL-002")
    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(item, MockVna(), TimeoutLinkBox(), Path(tmpdir), vna_settings={"points": 3})
        runner.link_box.connect()
        runner.vna.connect()

        try:
            runner.run()
        except CalibrationRunError as exc:
            assert exc.failure.kind.value == "link_box_no_response"
            assert exc.failure.action.value == "check_link_box_and_retry"
        else:
            raise AssertionError("Expected CalibrationRunError.")

        overview = runner.overview()
        assert runner.state_machine.state == CalibrationState.FAILED
        assert overview["failure_kind"] == "link_box_no_response"
        assert overview["failure_step_id"] == "CAL002-DUT-VNA2"
        assert any(event.startswith("failure:link_box_no_response:") for event in runner.events)


def test_mock_runner_marks_vna_timeout_as_failed_with_recovery_action() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(item, TimeoutReadVna(), MockLinkBox(), Path(tmpdir), vna_settings={"points": 3})
        runner.link_box.connect()
        runner.vna.connect()

        try:
            runner.run()
        except CalibrationRunError as exc:
            assert exc.failure.kind.value == "vna_timeout"
            assert exc.failure.action.value == "check_vna_and_retry"
        else:
            raise AssertionError("Expected CalibrationRunError.")

        overview = runner.overview()
        assert runner.state_machine.state == CalibrationState.FAILED
        assert overview["failure_kind"] == "vna_timeout"
        assert overview["failure_state"] == "READ_TRACE"


def test_mock_runner_marks_storage_save_failure_as_failed_with_recovery_action() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    with TemporaryDirectory() as tmpdir:
        output_root = Path(tmpdir) / "not-a-directory"
        output_root.write_text("occupied", encoding="utf-8")
        runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), output_root, vna_settings={"points": 3})
        runner.link_box.connect()
        runner.vna.connect()

        try:
            runner.run()
        except CalibrationRunError as exc:
            assert exc.failure.kind.value == "storage_save_failed"
            assert exc.failure.action.value == "choose_writable_output_and_retry"
        else:
            raise AssertionError("Expected CalibrationRunError.")

        overview = runner.overview()
        assert runner.state_machine.state == CalibrationState.FAILED
        assert overview["failure_kind"] == "storage_save_failed"
        assert overview["failure_state"] == "SAVE_RAW"


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


def test_saved_prompt_retry_recomputes_final_loss_from_new_raw() -> None:
    item = default_calibration_catalog().get("LINK-CAL-001")
    actions = iter(["continue", "retry", "continue", "cancel"])

    def confirm(step, substep, phase, index, total, substep_index, substep_total):
        _ = step, substep, phase, index, total, substep_index, substep_total
        return next(actions)

    with TemporaryDirectory() as tmpdir:
        runner = MockCalibrationRunner(
            item,
            ChangingReadVna(values=(-1.0, -11.0)),
            MockLinkBox(),
            Path(tmpdir),
            confirm_step=confirm,
            vna_settings={"points": 3},
        )
        runner.link_box.connect()
        runner.vna.connect()
        runner.run()
        loss_path = Path(tmpdir) / "loss" / "L_AUX_A_10_15G_F10_17G_H10_15G.csv"
        rows = loss_path.read_text(encoding="utf-8-sig").splitlines()

    assert rows[1].split(",")[1] == "11"


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
    assert overview["skipped_substep_ids"] == ("CAL001-AUX:AUX-A",)
    assert overview["publishable"] is False
    assert "skipped_substeps" in overview["publish_blockers"]


def test_skipped_session_does_not_publish_latest() -> None:
    catalog = default_calibration_catalog()
    item = catalog.get("LINK-CAL-001")
    actions = iter(["skip"] + ["continue"] * 32)

    def confirm(step, substep, phase, index, total, substep_index, substep_total):
        _ = step, substep, phase, index, total, substep_index, substep_total
        return next(actions)

    with TemporaryDirectory() as tmpdir:
        workspace = workspace_for_catalog(catalog, Path(tmpdir))
        run_context = CalibrationRunContext(project_code="PROJECT1", calibration_stage="initial", run_label="R01")
        session = create_session_context(workspace=workspace, run=run_context, item_id=item.id)
        runner = MockCalibrationRunner(
            item,
            MockVna(),
            MockLinkBox(),
            session.session_root,
            confirm_step=confirm,
            vna_settings={"points": 3},
            session_context=session,
        )
        runner.link_box.connect()
        runner.vna.connect()
        runner.run()
        overview = runner.overview()

        assert overview["publishable"] is False
        assert overview["latest_index_file"] == ""
        assert load_latest_summary(workspace=workspace, run=run_context, item_id=item.id) == {}


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
