from __future__ import annotations

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")
QCoreApplication = QtCore.QCoreApplication

from catr_loss_calibrator.presentation.viewmodels import CalibrationViewModel


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
