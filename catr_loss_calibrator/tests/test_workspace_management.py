from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from catr_loss_calibrator.calibration.definitions import default_calibration_catalog
from catr_loss_calibrator.storage.workspace import (
    CalibrationRunContext,
    config_hash_for_catalog,
    create_session_context,
    list_session_summaries,
    load_latest_summary,
    workspace_for_catalog,
    write_latest_index,
    write_session_manifest,
)


def test_workspace_id_is_stable_for_same_catalog() -> None:
    catalog = default_calibration_catalog()

    first = workspace_for_catalog(catalog, Path("out"))
    second = workspace_for_catalog(catalog, Path("out"))

    assert first.config_hash == second.config_hash
    assert first.workspace_id == second.workspace_id
    assert first.workspace_root == second.workspace_root


def test_config_hash_changes_when_source_file_changes(tmp_path: Path) -> None:
    first_config = tmp_path / "first.json"
    second_config = tmp_path / "second.json"
    first_config.write_text('{"name":"demo","items":[1]}', encoding="utf-8")
    second_config.write_text('{"name":"demo","items":[2]}', encoding="utf-8")
    catalog = default_calibration_catalog()

    first_hash = config_hash_for_catalog(replace(catalog, source_path=str(first_config)))
    second_hash = config_hash_for_catalog(replace(catalog, source_path=str(second_config)))

    assert first_hash != second_hash


def test_session_context_uses_project_stage_and_run_label(tmp_path: Path) -> None:
    workspace = workspace_for_catalog(default_calibration_catalog(), tmp_path)
    run = CalibrationRunContext(
        project_code="项目 A",
        calibration_stage="after repair",
        run_label="R02",
        operator="张三",
        operator_note="更换线缆后复测",
    )
    now = datetime(2026, 7, 19, 10, 11, 12, tzinfo=timezone.utc)

    session = create_session_context(workspace=workspace, run=run, item_id="LINK-CAL-001", now=now)

    assert session.session_id == "20260719_101112_LINK-CAL-001_after_repair_R02"
    assert session.session_root == (
        workspace.workspace_root
        / "projects"
        / "项目_A"
        / "sessions"
        / "20260719_101112_LINK-CAL-001_after_repair_R02"
    )
    assert session.run.project_code == "项目_A"
    assert session.run.operator == "张三"
    assert session.run.operator_note == "更换线缆后复测"


def test_write_session_manifest_records_workspace_project_and_files(tmp_path: Path) -> None:
    workspace = workspace_for_catalog(default_calibration_catalog(), tmp_path)
    session = create_session_context(
        workspace=workspace,
        run=CalibrationRunContext(project_code="PROJECT1", calibration_stage="initial", run_label="R01"),
        item_id="LINK-CAL-001",
        now=datetime(2026, 7, 19, 10, 11, 12, tzinfo=timezone.utc),
    )

    path = write_session_manifest(
        session,
        state="DONE",
        raw_files=("raw/a.csv",),
        loss_files=("loss/b.csv",),
        metadata_files=("metadata/c.json",),
        last_event="done:LINK-CAL-001",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path == session.session_root / "session_manifest.json"
    assert payload["schema_version"] == "catr-session-manifest.v1"
    assert payload["workspace_id"] == workspace.workspace_id
    assert payload["config_hash"] == workspace.config_hash
    assert payload["project_code"] == "PROJECT1"
    assert payload["calibration_stage"] == "initial"
    assert payload["run_label"] == "R01"
    assert payload["raw_files"] == ["raw/a.csv"]
    assert payload["loss_files"] == ["loss/b.csv"]
    assert payload["metadata_files"] == ["metadata/c.json"]


def test_latest_index_points_to_successful_manifest(tmp_path: Path) -> None:
    workspace = workspace_for_catalog(default_calibration_catalog(), tmp_path)
    session = create_session_context(
        workspace=workspace,
        run=CalibrationRunContext(project_code="PROJECT1", calibration_stage="initial", run_label="R01"),
        item_id="LINK-CAL-001",
        now=datetime(2026, 7, 19, 10, 11, 12, tzinfo=timezone.utc),
    )
    manifest_path = write_session_manifest(
        session,
        state="DONE",
        raw_files=("raw/a.csv",),
        loss_files=("loss/b.csv",),
        metadata_files=("metadata/c.json",),
        last_event="done:LINK-CAL-001",
    )

    latest_path = write_latest_index(session, manifest_path)
    latest = load_latest_summary(
        workspace=workspace,
        run=CalibrationRunContext(project_code="PROJECT1", calibration_stage="initial", run_label="R01"),
        item_id="LINK-CAL-001",
    )

    assert latest_path == workspace.workspace_root / "projects" / "PROJECT1" / "latest" / "LINK-CAL-001.json"
    assert latest["session_id"] == session.session_id
    assert latest["manifest_file"] == str(manifest_path)
    assert latest["raw_files"] == ("raw/a.csv",)
    assert latest["loss_files"] == ("loss/b.csv",)


def test_list_session_summaries_filters_item_and_sorts_newest_first(tmp_path: Path) -> None:
    workspace = workspace_for_catalog(default_calibration_catalog(), tmp_path)
    run = CalibrationRunContext(project_code="PROJECT1", calibration_stage="initial", run_label="R01")
    older = create_session_context(
        workspace=workspace,
        run=run,
        item_id="LINK-CAL-001",
        now=datetime(2026, 7, 19, 10, 0, 0, tzinfo=timezone.utc),
    )
    newer = create_session_context(
        workspace=workspace,
        run=run,
        item_id="LINK-CAL-001",
        now=datetime(2026, 7, 19, 11, 0, 0, tzinfo=timezone.utc),
    )
    other_item = create_session_context(
        workspace=workspace,
        run=run,
        item_id="LINK-CAL-002",
        now=datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc),
    )
    write_session_manifest(
        older,
        state="DONE",
        raw_files=("raw/old.csv",),
        loss_files=("loss/old.csv",),
        metadata_files=("metadata/old.json",),
    )
    write_session_manifest(
        newer,
        state="DONE",
        raw_files=("raw/new.csv",),
        loss_files=("loss/new.csv",),
        metadata_files=("metadata/new.json",),
    )
    write_session_manifest(
        other_item,
        state="DONE",
        raw_files=("raw/other.csv",),
        loss_files=("loss/other.csv",),
        metadata_files=("metadata/other.json",),
    )

    summaries = list_session_summaries(workspace=workspace, run=run, item_id="LINK-CAL-001")

    assert [summary["session_id"] for summary in summaries] == [newer.session_id, older.session_id]
    assert summaries[0]["raw_files"] == ("raw/new.csv",)
