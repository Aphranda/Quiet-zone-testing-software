from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from catr_loss_calibrator.calibration.models import CalibrationCatalog
from catr_loss_calibrator.runtime_resources import default_output_root


DEFAULT_OUTPUT_ROOT = default_output_root()
SESSION_MANIFEST_SCHEMA_VERSION = "catr-session-manifest.v1"
LATEST_INDEX_SCHEMA_VERSION = "catr-latest-session.v1"
WORKSPACE_MANIFEST_SCHEMA_VERSION = "catr-workspace.v1"
WORKSPACE_CONFIG_DIR = "config"
WORKSPACE_CONFIG_SNAPSHOT = "link_config_snapshot.json"


@dataclass(frozen=True)
class CalibrationRunContext:
    project_code: str = "DEFAULT_PROJECT"
    calibration_stage: str = "initial"
    run_label: str = "R01"
    operator: str = ""
    operator_note: str = ""

    def normalized(self) -> "CalibrationRunContext":
        return CalibrationRunContext(
            project_code=_safe_token(self.project_code or "DEFAULT_PROJECT"),
            calibration_stage=_safe_token(self.calibration_stage or "initial"),
            run_label=_safe_token(self.run_label or "R01"),
            operator=self.operator.strip(),
            operator_note=self.operator_note.strip(),
        )


@dataclass(frozen=True)
class WorkspaceContext:
    output_base: Path
    config_name: str
    config_display_name: str
    config_source_path: str
    config_hash: str
    workspace_id: str
    workspace_root: Path


@dataclass(frozen=True)
class SessionContext:
    run_uid: str
    session_id: str
    session_root: Path
    workspace: WorkspaceContext
    run: CalibrationRunContext
    item_id: str
    started_at: str


def workspace_for_catalog(
    catalog: CalibrationCatalog,
    output_base: Path = DEFAULT_OUTPUT_ROOT,
) -> WorkspaceContext:
    config_hash = config_hash_for_catalog(catalog)
    config_name = catalog.name or catalog.display_name or _source_stem(catalog.source_path) or "link_config"
    workspace_id = f"{_safe_token(config_name)}_{config_hash[:8]}"
    return WorkspaceContext(
        output_base=output_base,
        config_name=config_name,
        config_display_name=catalog.display_name or catalog.name or "",
        config_source_path=catalog.source_path,
        config_hash=config_hash,
        workspace_id=workspace_id,
        workspace_root=output_base / "workspaces" / workspace_id,
    )


def write_workspace_manifest(workspace: WorkspaceContext, catalog: CalibrationCatalog) -> Path:
    workspace.workspace_root.mkdir(parents=True, exist_ok=True)
    snapshot_path = workspace_config_snapshot_path(workspace.workspace_root)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    source_path = Path(catalog.source_path) if catalog.source_path else None
    if source_path is not None and source_path.exists():
        snapshot_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        snapshot_path.write_text(
            json.dumps(_catalog_to_link_config_payload(catalog), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    payload = {
        "schema_version": WORKSPACE_MANIFEST_SCHEMA_VERSION,
        "workspace_id": workspace.workspace_id,
        "workspace_root": str(workspace.workspace_root),
        "config_name": workspace.config_name,
        "config_display_name": workspace.config_display_name,
        "config_hash": workspace.config_hash,
        "config_source_path": workspace.config_source_path,
        "config_snapshot_file": str(snapshot_path),
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    path = workspace.workspace_root / "workspace.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def workspace_config_snapshot_path(workspace_root: Path) -> Path:
    return workspace_root / WORKSPACE_CONFIG_DIR / WORKSPACE_CONFIG_SNAPSHOT


def config_hash_for_catalog(catalog: CalibrationCatalog) -> str:
    if catalog.source_path:
        path = Path(catalog.source_path)
        if path.exists():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {
        "schema_version": catalog.schema_version,
        "name": catalog.name,
        "display_name": catalog.display_name,
        "band_config": catalog.band_config,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "purpose": item.purpose,
                "steps": [step.id for step in item.steps],
            }
            for item in catalog.items
        ],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def create_session_context(
    *,
    workspace: WorkspaceContext,
    run: CalibrationRunContext,
    item_id: str,
    now: datetime | None = None,
) -> SessionContext:
    normalized_run = run.normalized()
    current = now or datetime.now().astimezone()
    timestamp = current.strftime("%Y%m%d_%H%M%S")
    session_id = "_".join(
        part
        for part in (
            timestamp,
            _safe_token(item_id),
            normalized_run.calibration_stage,
            normalized_run.run_label,
        )
        if part
    )
    session_root = (
        workspace.workspace_root
        / "projects"
        / normalized_run.project_code
        / "sessions"
        / session_id
    )
    return SessionContext(
        run_uid=str(uuid4()),
        session_id=session_id,
        session_root=session_root,
        workspace=workspace,
        run=normalized_run,
        item_id=item_id,
        started_at=current.isoformat(timespec="seconds"),
    )


def write_session_manifest(
    session: SessionContext,
    *,
    state: str,
    raw_files: tuple[str, ...],
    loss_files: tuple[str, ...],
    metadata_files: tuple[str, ...],
    last_event: str = "",
    failure: dict[str, object] | None = None,
    finished_at: datetime | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> Path:
    payload: dict[str, Any] = {
        "schema_version": SESSION_MANIFEST_SCHEMA_VERSION,
        "run_uid": session.run_uid,
        "session_id": session.session_id,
        "session_root": str(session.session_root),
        "workspace_id": session.workspace.workspace_id,
        "workspace_root": str(session.workspace.workspace_root),
        "config_hash": session.workspace.config_hash,
        "config_name": session.workspace.config_name,
        "config_display_name": session.workspace.config_display_name,
        "config_source_path": session.workspace.config_source_path,
        **asdict(session.run),
        "item_id": session.item_id,
        "state": state,
        "started_at": session.started_at,
        "finished_at": (finished_at or datetime.now().astimezone()).isoformat(timespec="seconds"),
        "raw_files": raw_files,
        "loss_files": loss_files,
        "metadata_files": metadata_files,
        "last_event": last_event,
    }
    if failure:
        payload["failure"] = failure
    if extra_fields:
        payload.update(extra_fields)
    path = session.session_root / "session_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def project_root_for_session(session: SessionContext) -> Path:
    return session.workspace.workspace_root / "projects" / session.run.project_code


def latest_index_path(session: SessionContext) -> Path:
    return project_root_for_session(session) / "latest" / f"{_safe_token(session.item_id)}.json"


def write_latest_index(session: SessionContext, manifest_path: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = {
        "schema_version": LATEST_INDEX_SCHEMA_VERSION,
        "item_id": session.item_id,
        "workspace_id": session.workspace.workspace_id,
        "workspace_root": str(session.workspace.workspace_root),
        "project_code": session.run.project_code,
        "latest_session_id": session.session_id,
        "latest_session_root": str(session.session_root),
        "manifest_file": str(manifest_path),
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest": manifest,
    }
    path = latest_index_path(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def latest_index_path_for(
    *,
    workspace: WorkspaceContext,
    run: CalibrationRunContext,
    item_id: str,
) -> Path:
    normalized_run = run.normalized()
    return workspace.workspace_root / "projects" / normalized_run.project_code / "latest" / f"{_safe_token(item_id)}.json"


def load_latest_summary(
    *,
    workspace: WorkspaceContext,
    run: CalibrationRunContext,
    item_id: str,
) -> dict[str, object]:
    path = latest_index_path_for(workspace=workspace, run=run, item_id=item_id)
    return load_latest_summary_from_index(path)


def load_latest_summary_from_index(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    manifest = payload.get("manifest") if isinstance(payload, dict) else {}
    if not isinstance(manifest, dict):
        return {}
    summary = _summary_from_manifest(manifest)
    if not summary.get("manifest_file"):
        summary["manifest_file"] = str(payload.get("manifest_file", ""))
    summary["latest_index_file"] = str(path)
    summary["result_view_mode"] = "latest"
    return summary


def load_session_summary_from_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        return {}
    summary = _summary_from_manifest(manifest)
    if not summary.get("manifest_file"):
        summary["manifest_file"] = str(path)
    summary["result_view_mode"] = "history"
    return summary


def list_session_summaries(
    *,
    workspace: WorkspaceContext,
    run: CalibrationRunContext,
    item_id: str | None = None,
) -> tuple[dict[str, object], ...]:
    normalized_run = run.normalized()
    project_root = workspace.workspace_root / "projects" / normalized_run.project_code
    return list_session_summaries_from_project_root(project_root=project_root, item_id=item_id)


def list_session_summaries_from_project_root(
    *,
    project_root: Path,
    item_id: str | None = None,
) -> tuple[dict[str, object], ...]:
    sessions_root = project_root / "sessions"
    if not sessions_root.exists():
        return ()
    summaries: list[dict[str, object]] = []
    for manifest_path in sessions_root.glob("*/session_manifest.json"):
        try:
            summary = load_session_summary_from_manifest(manifest_path)
        except Exception:
            continue
        if not summary:
            continue
        if item_id and str(summary.get("item_id", "")) != item_id:
            continue
        summaries.append(summary)
    return tuple(
        sorted(
            summaries,
            key=lambda summary: (
                str(summary.get("finished_at") or summary.get("started_at") or ""),
                str(summary.get("session_id") or ""),
            ),
            reverse=True,
        )
    )


def list_session_summaries_from_workspace_root(
    *,
    workspace_root: Path,
    item_id: str | None = None,
    project_code: str | None = None,
) -> tuple[dict[str, object], ...]:
    projects_root = workspace_root / "projects"
    if project_code:
        project_roots = (projects_root / _safe_token(project_code),)
    elif projects_root.exists():
        project_roots = tuple(path for path in sorted(projects_root.iterdir()) if path.is_dir())
    elif (workspace_root / "sessions").exists():
        project_roots = (workspace_root,)
    else:
        project_roots = ()
    summaries: list[dict[str, object]] = []
    for project_root in project_roots:
        summaries.extend(list_session_summaries_from_project_root(project_root=project_root, item_id=item_id))
    return tuple(
        sorted(
            summaries,
            key=lambda summary: (
                str(summary.get("finished_at") or summary.get("started_at") or ""),
                str(summary.get("session_id") or ""),
            ),
            reverse=True,
        )
    )


def load_legacy_output_summary(root: Path, item_id: str | None = None) -> dict[str, object]:
    legacy_root = _legacy_output_root(root)
    metadata_root = legacy_root / "metadata"
    raw_files: list[str] = []
    loss_files: list[str] = []
    metadata_files: list[str] = []
    matched_item_id = item_id or ""
    if metadata_root.exists():
        for metadata_path in sorted(metadata_root.glob("*.json")):
            try:
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            metadata_item_id = str(payload.get("calibration_item") or payload.get("item_id") or "")
            if item_id and metadata_item_id != item_id:
                continue
            matched_item_id = matched_item_id or metadata_item_id
            metadata_files.append(str(metadata_path))
            raw_files.extend(_existing_legacy_paths(legacy_root, payload.get("input_files", ()) or ()))
            loss_files.extend(_existing_legacy_paths(legacy_root, payload.get("output_files", ()) or ()))
    if item_id:
        raw_files.extend(str(path) for path in sorted((legacy_root / "raw").glob(f"{item_id}_*.csv")))
        loss_files.extend(str(path) for path in sorted((legacy_root / "loss").glob("*.csv")))
    summary = {
        "item_id": matched_item_id or str(item_id or ""),
        "item_name": matched_item_id or str(item_id or "旧版输出目录"),
        "state": "LEGACY_READONLY",
        "completed_steps": "",
        "completed_big_steps": "",
        "last_event": "legacy_readonly",
        "output_root": str(legacy_root),
        "raw_files": tuple(_unique_existing_paths(raw_files)),
        "loss_files": tuple(_unique_existing_paths(loss_files)),
        "metadata_files": tuple(_unique_existing_paths(metadata_files)),
        "manifest_file": "",
        "run_uid": "",
        "session_id": "LEGACY_READONLY",
        "session_root": str(legacy_root),
        "workspace_id": "UNBOUND_LEGACY",
        "workspace_root": str(legacy_root),
        "config_hash": "UNBOUND_LEGACY",
        "config_source_path": "",
        "project_code": "未绑定配置",
        "calibration_stage": "legacy_readonly",
        "run_label": "",
        "operator": "",
        "operator_note": "旧版输出目录只读兼容展示",
        "started_at": "",
        "finished_at": "",
        "result_view_mode": "legacy",
    }
    return summary if summary["raw_files"] or summary["loss_files"] or summary["metadata_files"] else {}


def _legacy_output_root(root: Path) -> Path:
    if root.name.lower() in {"metadata", "raw", "loss"}:
        return root.parent
    return root


def _existing_legacy_paths(legacy_root: Path, paths: Any) -> list[str]:
    result: list[str] = []
    for raw_path in paths:
        path = Path(str(raw_path))
        if not path.is_absolute():
            path = legacy_root / path.relative_to(legacy_root.name) if path.parts and path.parts[0] == legacy_root.name else legacy_root / path
        if path.exists():
            result.append(str(path))
    return result


def _unique_existing_paths(paths: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for raw_path in paths:
        path = str(Path(raw_path))
        key = path.lower()
        if key not in seen and Path(path).exists():
            seen.add(key)
            result.append(path)
    return tuple(result)


def _summary_from_manifest(manifest: dict[str, Any]) -> dict[str, object]:
    raw_files = tuple(str(path) for path in manifest.get("raw_files", ()) or ())
    loss_files = tuple(str(path) for path in manifest.get("loss_files", ()) or ())
    metadata_files = tuple(str(path) for path in manifest.get("metadata_files", ()) or ())
    return {
        "item_id": str(manifest.get("item_id", "")),
        "item_name": str(manifest.get("item_id", "")),
        "state": str(manifest.get("state", "")),
        "completed_steps": "",
        "completed_big_steps": "",
        "last_event": str(manifest.get("last_event", "")),
        "output_root": str(manifest.get("session_root", "")),
        "raw_files": raw_files,
        "loss_files": loss_files,
        "metadata_files": metadata_files,
        "manifest_file": str(manifest.get("manifest_file", "")),
        "run_uid": str(manifest.get("run_uid", "")),
        "session_id": str(manifest.get("session_id", "")),
        "session_root": str(manifest.get("session_root", "")),
        "workspace_id": str(manifest.get("workspace_id", "")),
        "workspace_root": str(manifest.get("workspace_root", "")),
        "config_name": str(manifest.get("config_name", "")),
        "config_display_name": str(manifest.get("config_display_name", "")),
        "config_hash": str(manifest.get("config_hash", "")),
        "config_source_path": str(manifest.get("config_source_path", "")),
        "project_code": str(manifest.get("project_code", "")),
        "calibration_stage": str(manifest.get("calibration_stage", "")),
        "run_label": str(manifest.get("run_label", "")),
        "operator": str(manifest.get("operator", "")),
        "operator_note": str(manifest.get("operator_note", "")),
        "started_at": str(manifest.get("started_at", "")),
        "finished_at": str(manifest.get("finished_at", "")),
        "resume_source": manifest.get("resume_source", {}) if isinstance(manifest.get("resume_source", {}), dict) else {},
        "substep_status": manifest.get("substep_status", {}) if isinstance(manifest.get("substep_status", {}), dict) else {},
        "reused_files": tuple(str(path) for path in manifest.get("reused_files", ()) or ()),
        "new_files": tuple(str(path) for path in manifest.get("new_files", ()) or ()),
        "invalid_files": tuple(str(path) for path in manifest.get("invalid_files", ()) or ()),
        "completed_substep_ids": tuple(str(value) for value in manifest.get("completed_substep_ids", ()) or ()),
        "completed_step_ids": tuple(str(value) for value in manifest.get("completed_step_ids", ()) or ()),
        "current_retested_substep_ids": tuple(str(value) for value in manifest.get("current_retested_substep_ids", ()) or ()),
        "skipped_substep_ids": tuple(str(value) for value in manifest.get("skipped_substep_ids", ()) or ()),
        "publishable": bool(manifest.get("publishable", False)),
        "publish_blockers": tuple(str(value) for value in manifest.get("publish_blockers", ()) or ()),
        "measurement_settings": manifest.get("measurement_settings", {}) if isinstance(manifest.get("measurement_settings", {}), dict) else {},
        "measurement_warnings": tuple(str(value) for value in manifest.get("measurement_warnings", ()) or ()),
        "resume_compatibility_blockers": tuple(str(value) for value in manifest.get("resume_compatibility_blockers", ()) or ()),
        "resume_compatibility_warnings": tuple(str(value) for value in manifest.get("resume_compatibility_warnings", ()) or ()),
    }


def _source_stem(source_path: str) -> str:
    return Path(source_path).stem if source_path else ""


def _catalog_to_link_config_payload(catalog: CalibrationCatalog) -> dict[str, Any]:
    return {
        "schema_version": catalog.schema_version or "catr-link-config.v1",
        "name": catalog.name,
        "display_name": catalog.display_name,
        "description": catalog.description,
        "node_catalog": catalog.node_catalog,
        "path_templates": catalog.path_templates,
        "band_config": catalog.band_config,
        "calibration_items": [
            {
                "id": item.id,
                "name": item.name,
                "purpose": item.purpose,
                "steps": [
                    {
                        "id": step.id,
                        "name": step.name,
                        "role": getattr(step.role, "value", str(step.role)),
                        "input_port": step.input_port,
                        "output_port": step.output_port,
                        "manual_instruction": step.manual_instruction,
                        "route_ids": list(step.route_ids),
                        "link_commands": list(step.link_commands),
                        "raw_outputs": list(step.raw_outputs),
                        "final_outputs": list(step.final_outputs),
                        "required_inputs": list(step.required_inputs),
                        "notes": step.notes,
                        "path_template": step.path_template,
                        **({"vna_power_dbm": step.vna_power_dbm} if step.vna_power_dbm is not None else {}),
                        **({"path": step.path} if step.path else {}),
                        "substeps": [
                            {
                                "id": substep.id,
                                "name": substep.name,
                                "input_port": substep.input_port,
                                "output_port": substep.output_port,
                                "manual_instruction": substep.manual_instruction,
                                "route_ids": list(substep.route_ids),
                                "link_commands": list(substep.link_commands),
                                "raw_output": substep.raw_output,
                                "final_output": substep.final_output,
                                "required_inputs": list(substep.required_inputs),
                                "notes": substep.notes,
                                **({"vna_power_dbm": substep.vna_power_dbm} if substep.vna_power_dbm is not None else {}),
                                "parameter": substep.parameter,
                                "path_template": substep.path_template,
                                **({"path": substep.path} if substep.path else {}),
                            }
                            for substep in step.substeps
                        ],
                    }
                    for step in item.steps
                ],
            }
            for item in catalog.items
        ],
    }


def _safe_token(value: str) -> str:
    token = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]+', "_", value.strip())
    token = re.sub(r"_+", "_", token).strip("._-")
    return token or "UNTITLED"
