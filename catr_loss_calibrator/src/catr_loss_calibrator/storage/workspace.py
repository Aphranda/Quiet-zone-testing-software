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


DEFAULT_OUTPUT_ROOT = Path("catr_loss_calibrator_output")
SESSION_MANIFEST_SCHEMA_VERSION = "catr-session-manifest.v1"
LATEST_INDEX_SCHEMA_VERSION = "catr-latest-session.v1"


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
        "config_hash": str(manifest.get("config_hash", "")),
        "config_source_path": str(manifest.get("config_source_path", "")),
        "project_code": str(manifest.get("project_code", "")),
        "calibration_stage": str(manifest.get("calibration_stage", "")),
        "run_label": str(manifest.get("run_label", "")),
        "operator": str(manifest.get("operator", "")),
        "operator_note": str(manifest.get("operator_note", "")),
        "started_at": str(manifest.get("started_at", "")),
        "finished_at": str(manifest.get("finished_at", "")),
    }


def _source_stem(source_path: str) -> str:
    return Path(source_path).stem if source_path else ""


def _safe_token(value: str) -> str:
    token = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]+', "_", value.strip())
    token = re.sub(r"_+", "_", token).strip("._-")
    return token or "UNTITLED"
