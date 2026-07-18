from __future__ import annotations

from pathlib import Path

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")
QCoreApplication = QtCore.QCoreApplication

from catr_loss_calibrator.calibration.mock_runner import MockCalibrationRunner
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna
from catr_loss_calibrator.presentation.viewmodels import CalibrationRunWorker, CalibrationViewModel, StepViewData


def test_viewmodel_scopes_run_summary_to_selected_item() -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    vm = CalibrationViewModel()
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
        item=CalibrationViewModel().selected_item,
        vna=MockVna(),
        link_box=MockLinkBox(),
        output_root=Path("unused"),
    )
    worker = CalibrationRunWorker(runner)
    first_step = runner.item.steps[0]
    first_step_substeps = len(runner._substeps_for(first_step))

    assert worker._item_completed_substeps(2, 1, "start") == first_step_substeps
    assert worker._item_completed_substeps(2, 1, "saved") == first_step_substeps + 1
