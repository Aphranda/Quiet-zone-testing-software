from __future__ import annotations

import json
from pathlib import Path

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")
QCoreApplication = QtCore.QCoreApplication

from catr_loss_calibrator.calibration.mock_runner import MockCalibrationRunner
from catr_loss_calibrator.calibration.config_loader import DEFAULT_CONFIG_PATH
from catr_loss_calibrator.calibration.state_machine import CalibrationState
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna
from catr_loss_calibrator.presentation.viewmodels import CalibrationRunWorker, CalibrationViewModel, StepViewData


def test_viewmodel_scopes_run_summary_to_selected_item() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    vm.load_default_catalog()
    first_item = vm.selected_item
    second_item = vm.catalog.items[1]

    first_summary = {
        "item_id": first_item.id,
        "item_name": first_item.name,
        "state": "DONE",
        "completed_steps": 99,
        "completed_big_steps": 1,
        "completed_step_ids": (first_item.steps[0].id,),
    }
    vm._on_finished_summary(first_summary)

    assert vm.overview["run_summary"]["item_id"] == first_item.id
    assert vm.overview["status"] == "Calibration completed"
    assert vm.run_summary_for_item(first_item.id)["item_id"] == first_item.id
    assert vm.run_summary_for_item(second_item.id) == {}

    vm.select_item(1)

    assert vm.overview["item_id"] == second_item.id
    assert "run_summary" not in vm.overview
    assert vm.overview["status"] == "Ready"
    step_view = vm._step_view_data(second_item.steps[0], 1, len(second_item.steps))
    assert step_view.status == "Ready"

    second_summary = {
        "item_id": second_item.id,
        "item_name": second_item.name,
        "state": "DONE",
        "completed_steps": 1,
        "completed_big_steps": 1,
        "completed_step_ids": (second_item.steps[0].id,),
    }
    vm._on_finished_summary(second_summary)

    assert vm.overview["run_summary"]["item_id"] == second_item.id

    vm.select_item(0)

    assert vm.overview["run_summary"]["item_id"] == first_item.id
    assert vm.overview["run_summary"]["completed_steps"] == 99


def test_viewmodel_marks_previous_big_step_completed_during_run() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    vm.load_default_catalog()
    item = vm.selected_item
    second_step = item.steps[1]

    vm._on_prompt_ready(
        StepViewData(
            item_id=item.id,
            item_name=item.name,
            step_id=second_step.id,
            step_name=second_step.name,
            step_index=2,
            step_total=len(item.steps),
            status="等待开始确认",
            manual_instruction=second_step.manual_instruction,
            route_ids=second_step.route_ids,
            link_commands=second_step.link_commands,
            input_port=second_step.input_port,
            output_port=second_step.output_port,
            raw_outputs=second_step.raw_outputs,
            final_outputs=second_step.final_outputs,
            required_inputs=second_step.required_inputs,
            notes=second_step.notes,
            substep_id="",
            substep_name="",
            substep_index=1,
            substep_total=1,
            confirm_phase="start",
        )
    )

    summary = vm.run_summary_for_item(item.id)
    assert summary["completed_step_ids"] == (item.steps[0].id,)
    assert summary["completed_big_steps"] == 1


def test_worker_counts_progress_by_substep_not_big_step() -> None:
    runner = MockCalibrationRunner(
        item=default_loaded_viewmodel().selected_item,
        vna=MockVna(),
        link_box=MockLinkBox(),
        output_root=Path("unused"),
    )
    worker = CalibrationRunWorker(runner)
    first_step = runner.item.steps[0]
    first_step_substeps = len(runner._substeps_for(first_step))

    assert worker._item_completed_substeps(2, 1, "start") == first_step_substeps
    assert worker._item_completed_substeps(2, 1, "saved") == first_step_substeps + 1


def test_worker_saved_prompt_exposes_saved_csv_files(tmp_path: Path) -> None:
    item = default_loaded_viewmodel().selected_item
    step = item.steps[0]
    runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), tmp_path, vna_settings={"points": 3})
    runner.link_box.connect()
    runner.vna.connect()
    substep = runner._substeps_for(step)[0]

    runner.state_machine.transition(CalibrationState.WAIT_MANUAL_CONFIRM)
    runner._run_substep(step, substep)
    worker = CalibrationRunWorker(runner)
    saved_files = worker._saved_files_for_prompt(step, substep, "saved")

    assert len(saved_files) >= 2
    assert all(Path(path).exists() for path in saved_files)
    assert Path(saved_files[0]).parent.name == "loss"
    assert Path(saved_files[-1]).parent.name == "raw"


def test_viewmodel_can_retest_single_substep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(
        "catr_loss_calibrator.presentation.viewmodels.DEFAULT_OUTPUT_ROOT",
        tmp_path,
    )
    vm = default_loaded_viewmodel()
    vm.connect_mock_devices()
    step = vm.selected_item.steps[0]
    substep = vm._substeps_for_step(step)[0]

    summary = vm.run_single_substep(step.id, substep.id, {"points": 3, "project_code": "UNIT", "run_label": "R01"})

    assert summary["item_id"] == vm.selected_item.id
    assert f"{step.id}:{substep.id}" in summary["completed_substep_ids"]
    assert summary["publishable"] is False
    assert summary["latest_index_file"] == ""
    assert summary["raw_files"]
    assert summary["metadata_files"]
    assert all(Path(path).exists() for path in summary["raw_files"])


def test_viewmodel_generates_resumed_done_from_accepted_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(
        "catr_loss_calibrator.presentation.viewmodels.DEFAULT_OUTPUT_ROOT",
        tmp_path,
    )
    vm = default_loaded_viewmodel()
    item = vm.selected_item
    historical_runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), tmp_path / "history", vna_settings={"points": 3})
    historical_runner.link_box.connect()
    historical_runner.vna.connect()
    historical_runner.run()
    history_summary = historical_runner.overview()
    judgments = {
        f"{step.id}:{substep.id}": "accept"
        for step in item.steps
        for substep in vm._substeps_for_step(step)
    }

    summary = vm.generate_resume_results(history_summary, judgments, {"points": 3, "project_code": "UNIT", "run_label": "R01"})

    assert summary["state"] == "RESUMED_DONE"
    assert summary["latest_index_file"]
    assert Path(summary["latest_index_file"]).exists()
    assert summary["loss_files"]
    manifest = json.loads(Path(summary["manifest_file"]).read_text(encoding="utf-8"))
    assert manifest["state"] == "RESUMED_DONE"
    assert manifest["resume_source"]["item_id"] == item.id
    assert manifest["reused_files"]
    assert manifest["substep_status"]
    assert manifest["resume_compatibility_blockers"] == []
    assert {record["status"] for record in manifest["substep_status"].values()} == {"VALID_HISTORY"}


def test_viewmodel_generates_partial_when_history_not_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(
        "catr_loss_calibrator.presentation.viewmodels.DEFAULT_OUTPUT_ROOT",
        tmp_path,
    )
    vm = default_loaded_viewmodel()
    item = vm.selected_item
    historical_runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), tmp_path / "history", vna_settings={"points": 3})
    historical_runner.link_box.connect()
    historical_runner.vna.connect()
    historical_runner.run()

    summary = vm.generate_resume_results(historical_runner.overview(), {}, {"points": 3, "project_code": "UNIT", "run_label": "R01"})

    assert summary["state"] == "PARTIAL"
    assert summary["latest_index_file"] == ""
    assert summary["completed_substep_ids"] == ()
    manifest = json.loads(Path(summary["manifest_file"]).read_text(encoding="utf-8"))
    assert manifest["state"] == "PARTIAL"
    assert manifest["reused_files"] == []


def test_viewmodel_warns_resume_when_measurement_settings_differ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(
        "catr_loss_calibrator.presentation.viewmodels.DEFAULT_OUTPUT_ROOT",
        tmp_path,
    )
    vm = default_loaded_viewmodel()
    item = vm.selected_item
    historical_runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), tmp_path / "history", vna_settings={"points": 3})
    historical_runner.link_box.connect()
    historical_runner.vna.connect()
    historical_runner.run()
    judgments = {
        f"{step.id}:{substep.id}": "accept"
        for step in item.steps
        for substep in vm._substeps_for_step(step)
    }

    summary = vm.generate_resume_results(
        historical_runner.overview(),
        judgments,
        {"points": 4, "project_code": "UNIT", "run_label": "R01"},
    )

    assert summary["state"] == "RESUMED_DONE"
    assert summary["latest_index_file"]
    assert "points mismatch" in summary["resume_compatibility_warnings"]
    assert summary["resume_compatibility_blockers"] == ()
    assert {record["status"] for record in summary["substep_status"].values()} == {"VALID_HISTORY"}
    assert all("warnings" in record for record in summary["substep_status"].values())


def test_viewmodel_warns_accepted_legacy_history_without_measurement_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(
        "catr_loss_calibrator.presentation.viewmodels.DEFAULT_OUTPUT_ROOT",
        tmp_path,
    )
    vm = default_loaded_viewmodel()
    item = vm.selected_item
    historical_runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), tmp_path / "history", vna_settings={"points": 3})
    historical_runner.link_box.connect()
    historical_runner.vna.connect()
    historical_runner.run()
    history_summary = dict(historical_runner.overview())
    history_summary.pop("measurement_settings", None)
    judgments = {
        f"{step.id}:{substep.id}": "accept"
        for step in item.steps
        for substep in vm._substeps_for_step(step)
    }

    summary = vm.generate_resume_results(history_summary, judgments, {"points": 3, "project_code": "UNIT", "run_label": "R01"})

    assert summary["state"] == "RESUMED_DONE"
    assert summary["latest_index_file"]
    assert "measurement_settings missing" in summary["resume_compatibility_warnings"]
    assert summary["resume_compatibility_blockers"] == ()
    assert {record["status"] for record in summary["substep_status"].values()} == {"VALID_HISTORY"}


def test_worker_formats_link_events_for_log_panel() -> None:
    fields = CalibrationRunWorker._log_fields_for_event(
        "link:CAL002-MAIN:V-THRU:CONFigure:LINK V, VNA1",
        "VNA 链路损耗校准",
    )

    assert fields == (
        "INFO",
        "link_box",
        "VNA 链路损耗校准",
        "下发链路箱命令: CONFigure:LINK V, VNA1",
    )


def test_worker_formats_failure_events_for_log_panel() -> None:
    fields = CalibrationRunWorker._log_fields_for_event(
        "failure:vna_timeout:CAL001-AUX:AUX-A:READ_TRACE:check_vna_and_retry:VNA sweep timed out.",
        "暗室内部链路校准",
    )

    assert fields[0] == "ERROR"
    assert fields[1] == "runner"
    assert fields[2] == "暗室内部链路校准"
    assert "vna_timeout" in fields[3]
    assert "check_vna_and_retry" in fields[3]


def test_viewmodel_marks_last_big_step_completed_after_last_substep_saved() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = default_loaded_viewmodel()
    item = vm.selected_item
    last_step = item.steps[-1]
    last_substeps = vm._substeps_for_step(last_step)
    total_substeps = sum(len(vm._substeps_for_step(step)) for step in item.steps)

    prompt = StepViewData(
        item_id=item.id,
        item_name=item.name,
        step_id=last_step.id,
        step_name=last_step.name,
        step_index=len(item.steps),
        step_total=len(item.steps),
        status="等待保存完成确认",
        manual_instruction=last_step.manual_instruction,
        route_ids=last_step.route_ids,
        link_commands=last_step.link_commands,
        input_port=last_step.input_port,
        output_port=last_step.output_port,
        raw_outputs=last_step.raw_outputs,
        final_outputs=last_step.final_outputs,
        required_inputs=last_step.required_inputs,
        notes=last_step.notes,
        substep_id=last_substeps[-1].id,
        substep_name=last_substeps[-1].name,
        substep_index=len(last_substeps),
        substep_total=len(last_substeps),
        confirm_phase="saved",
        item_total_substeps=total_substeps,
        item_completed_substeps=total_substeps,
    )

    vm._update_run_progress(prompt)

    assert vm.step_progress_state(item.id, last_step.id) == "done"
    assert len(vm.run_summary_for_item(item.id)["completed_step_ids"]) == len(item.steps)


def test_viewmodel_exposes_substep_path_templates_for_detail_switching() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    vm.load_default_catalog()
    vm.select_item(1)
    main_step = next(step for step in vm.selected_item.steps if step.id == "CAL002-MAIN")

    templates = {substep.id: substep.path_template for substep in vm.substep_view_data(main_step)}

    assert templates["V-THRU"] == "CAL002-MAIN:V-THRU"
    assert templates["V-AMP2"] == "CAL002-MAIN:V-AMP2"


def test_viewmodel_load_catalog_replaces_current_config_and_clears_run_state(tmp_path: Path) -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    vm.load_default_catalog()
    first_item = vm.selected_item
    vm._on_finished_summary(
        {
            "item_id": first_item.id,
            "item_name": first_item.name,
            "state": "DONE",
            "completed_steps": 1,
            "completed_big_steps": 1,
            "completed_step_ids": (first_item.steps[0].id,),
        }
    )

    payload = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    payload["display_name"] = "导入测试链路配置"
    target = tmp_path / "imported_link_config.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    vm.load_catalog(target)

    assert vm.catalog.display_name == "导入测试链路配置"
    assert vm.catalog.source_path == str(target)
    assert vm.selected_item.id == "LINK-CAL-001"
    assert vm.run_summary_for_item(first_item.id) == {}
    assert vm.overview["item_id"] == "LINK-CAL-001"


def test_viewmodel_starts_without_loaded_catalog() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()

    assert vm.catalog.items == ()
    assert vm.selected_item is None
    vm.refresh_overview()
    assert vm.overview["item_name"] == "未加载链路配置"


def test_viewmodel_clear_logs_removes_existing_records() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()

    assert vm.logs
    vm.clear_logs()

    assert vm.logs == []


def test_viewmodel_command_tracking_uses_log_not_legacy_command_history() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    vm.connect_device("link_box")

    response = vm.send_device_command("link_box", "*IDN?")

    assert response.startswith("MOCK,")
    assert vm.command_response == response
    assert not hasattr(vm, "command_history")
    messages = [record.message for record in vm.logs if record.source == "command"]
    assert "发送命令: *IDN?" in messages
    assert any(message.startswith("返回响应: MOCK,") for message in messages)


def test_viewmodel_rejects_unknown_inline_action_with_clear_status() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()

    accepted = vm.submit_action("bad-action")

    assert accepted is False
    assert vm.status_text == "非法操作: bad-action"
    assert vm.logs[-1].level == "ERROR"
    assert vm.logs[-1].message == "非法操作: bad-action"


def test_viewmodel_rejects_inline_action_when_no_prompt_is_active() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    vm.load_default_catalog()

    accepted = vm.submit_action("continue")

    assert accepted is False
    assert "当前没有等待确认的校准步骤" in vm.status_text
    assert vm.logs[-1].level == "WARNING"
    assert "已忽略 continue" in vm.logs[-1].message


def test_viewmodel_device_model_options_include_target_sg_and_sa_models() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()

    assert "N5183B" in vm.device_model_options("signal_generator")
    assert "N9020B" in vm.device_model_options("spectrum_analyzer")


def test_viewmodel_configures_signal_generator_with_structured_settings() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    vm.connect_device("signal_generator")

    response = vm.configure_signal_generator(
        {
            "frequency_ghz": 12.5,
            "power_dbm": -7.5,
            "output_enabled": True,
        }
    )

    assert response == "OK: SG 12500000000 Hz, -7.5 dBm, output ON"
    assert vm._mock_signal_generator.commands == [
        "FREQuency:CW 12500000000",
        "POWer:LEVel -7.5",
        "OUTPut:STATe ON",
    ]
    messages = [record.message for record in vm.logs if record.source == "signal_generator"]
    assert "发送命令: FREQuency:CW 12500000000" in messages
    assert "发送命令: OUTPut:STATe ON" in messages


def test_viewmodel_configures_spectrum_analyzer_with_structured_settings() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    vm.connect_device("spectrum_analyzer")

    response = vm.configure_spectrum_analyzer(
        {
            "center_ghz": 21.7,
            "span_mhz": 200.0,
            "points": 1601,
            "rbw_hz": 10000.0,
            "vbw_hz": 30000.0,
            "reference_level_dbm": -5.0,
            "attenuation_db": 6.0,
        }
    )

    assert response == "OK: SA center 21700000000 Hz, span 200000000 Hz, 1601 pts, RBW 10000 Hz, VBW 30000 Hz"
    assert vm._mock_spectrum_analyzer.commands == [
        "INSTrument:SELect SA",
        "CONFigure:SANalyzer",
        "FREQuency:CENTer 21700000000",
        "FREQuency:SPAN 200000000",
        "SWEep:POINts 1601",
        "BANDwidth:RESolution 10000",
        "BANDwidth:VIDeo 30000",
        "DISPlay:WINDow:TRACe:Y:RLEVel -5",
        "POWer:ATTenuation 6",
    ]
    messages = [record.message for record in vm.logs if record.source == "spectrum_analyzer"]
    assert "发送命令: FREQuency:CENTer 21700000000" in messages
    assert "发送命令: POWer:ATTenuation 6" in messages


def test_viewmodel_signal_generator_accepts_manual_scpi_commands() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    vm.connect_device("signal_generator")
    vm.configure_signal_generator(
        {
            "frequency_ghz": 14.5,
            "power_dbm": -3.0,
            "output_enabled": False,
        }
    )

    output_on = vm.send_device_command("signal_generator", "OUTPut:STATe ON")
    query_output = vm.send_device_command("signal_generator", "OUTPut:STATe?")
    query_frequency = vm.send_device_command("signal_generator", "FREQuency:CW?")
    query_power = vm.send_device_command("signal_generator", "POWer:LEVel?")

    assert output_on == "OK"
    assert query_output == "1"
    assert query_frequency == "14500000000"
    assert query_power == "-3"
    assert vm._mock_signal_generator.commands[-4:] == [
        "OUTPut:STATe ON",
        "OUTPut:STATe?",
        "FREQuency:CW?",
        "POWer:LEVel?",
    ]


def test_viewmodel_spectrum_analyzer_accepts_manual_scpi_commands() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    vm.connect_device("spectrum_analyzer")
    vm.configure_spectrum_analyzer(
        {
            "center_ghz": 24.0,
            "span_mhz": 500.0,
            "points": 1001,
            "rbw_hz": 100000.0,
            "vbw_hz": 100000.0,
            "reference_level_dbm": 0.0,
            "attenuation_db": 10.0,
        }
    )

    assert vm.send_device_command("spectrum_analyzer", "INITiate:IMMediate") == "OK"
    assert vm.send_device_command("spectrum_analyzer", "*OPC?") == "1"
    assert vm.send_device_command("spectrum_analyzer", "CALCulate:MARKer1:MAXimum") == "OK"
    assert vm.send_device_command("spectrum_analyzer", "CALCulate:MARKer1:X?") == "24000000000"
    assert vm.send_device_command("spectrum_analyzer", "CALCulate:MARKer1:Y?") == "-42.0"
    assert vm.send_device_command("spectrum_analyzer", "SYSTem:ERRor?") == "0,No error"


def test_viewmodel_device_presets_include_target_sg_and_sa_commands() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
    presets = vm.device_command_presets()

    vna = presets["vna"]
    assert vna["N5245B 端口1功率"] == "SOUR1:POW1:LEV:IMM:AMPL -10"
    assert vna["关闭连续扫描"] == "SENS1:SWE:MODE HOLD"
    assert vna["立即触发"] == "SENS1:SWE:MODE SING"
    assert vna["N5245B 关闭连续扫描"] == "INIT1:CONT OFF"
    assert vna["N5245B INIT 触发"] == "INIT1:IMM"
    assert vna["二进制 REAL64"] == "FORM:DATA REAL,64"
    assert vna["读取 SDATA"] == "CALC1:DATA? SDATA"

    signal_generator = presets["signal_generator"]
    assert signal_generator["设置频率"] == "FREQuency:CW 10GHz"
    assert signal_generator["设置功率"] == "POWer:LEVel -10dBm"
    assert signal_generator["关闭输出"] == "OUTPut:STATe OFF"
    assert signal_generator["查询错误"] == "SYSTem:ERRor?"

    spectrum_analyzer = presets["spectrum_analyzer"]
    assert spectrum_analyzer["选择频谱模式"] == "INSTrument:SELect SA"
    assert spectrum_analyzer["配置频谱测量"] == "CONFigure:SANalyzer"
    assert spectrum_analyzer["设置中心频率"] == "FREQuency:CENTer 10GHz"
    assert spectrum_analyzer["设置点数"] == "SWEep:POINts 1001"
    assert spectrum_analyzer["设置 RBW"] == "BANDwidth:RESolution 1MHz"
    assert spectrum_analyzer["设置 VBW"] == "BANDwidth:VIDeo 1MHz"
    assert "关闭连续测量" not in spectrum_analyzer
    assert spectrum_analyzer["读取频谱数据"] == "READ:SANalyzer?"
    assert spectrum_analyzer["峰值搜索"] == "CALCulate:MARKer1:MAXimum"
    assert spectrum_analyzer["读取 Marker 幅度"] == "CALCulate:MARKer1:Y?"


def default_loaded_viewmodel() -> CalibrationViewModel:
    vm = CalibrationViewModel()
    vm.load_default_catalog()
    return vm
