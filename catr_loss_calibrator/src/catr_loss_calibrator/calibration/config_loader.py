from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from catr_loss_calibrator.calibration.models import (
    CalibrationCatalog,
    CalibrationItem,
    CalibrationStep,
    CalibrationSubStep,
    MeasurementRole,
)


SUPPORTED_SCHEMA_VERSION = "catr-link-config.v1"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "catr_chamber_loss_calibration.json"


class LinkConfigError(ValueError):
    """Raised when a link configuration JSON cannot be converted to a catalog."""


def default_calibration_catalog_from_json() -> CalibrationCatalog:
    return load_calibration_catalog(DEFAULT_CONFIG_PATH)


def load_calibration_catalog(path: str | Path) -> CalibrationCatalog:
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LinkConfigError(f"Link config not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise LinkConfigError(f"Invalid JSON at {config_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise LinkConfigError("Link config root must be an object.")
    schema_version = _required_str(payload, "schema_version", "schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise LinkConfigError(
            f"Unsupported schema_version {schema_version!r}; expected {SUPPORTED_SCHEMA_VERSION!r}."
        )

    items_payload = _required_list(payload, "calibration_items", "calibration_items")
    items = tuple(_parse_item(item_data, f"calibration_items[{index}]") for index, item_data in enumerate(items_payload))
    _ensure_unique([item.id for item in items], "calibration_items[].id")

    return CalibrationCatalog(
        items=items,
        schema_version=schema_version,
        name=str(payload.get("name", "")),
        display_name=str(payload.get("display_name", "")),
        description=str(payload.get("description", "")),
        source_path=str(config_path),
        node_catalog=dict(payload.get("node_catalog") or {}),
        path_templates=dict(payload.get("path_templates") or {}),
        band_config=_parse_band_config(payload.get("band_config"), "band_config"),
    )


def _parse_item(data: Any, path: str) -> CalibrationItem:
    if not isinstance(data, dict):
        raise LinkConfigError(f"{path} must be an object.")
    steps_payload = _required_list(data, "steps", f"{path}.steps")
    steps = tuple(_parse_step(step_data, f"{path}.steps[{index}]") for index, step_data in enumerate(steps_payload))
    _ensure_unique([step.id for step in steps], f"{path}.steps[].id")
    return CalibrationItem(
        id=_required_str(data, "id", f"{path}.id"),
        name=_required_str(data, "name", f"{path}.name"),
        purpose=str(data.get("purpose", "")),
        steps=steps,
    )


def _parse_step(data: Any, path: str) -> CalibrationStep:
    if not isinstance(data, dict):
        raise LinkConfigError(f"{path} must be an object.")
    substeps_payload = data.get("substeps") or ()
    if not isinstance(substeps_payload, (list, tuple)):
        raise LinkConfigError(f"{path}.substeps must be an array.")
    substeps = tuple(
        _parse_substep(substep_data, f"{path}.substeps[{index}]") for index, substep_data in enumerate(substeps_payload)
    )
    _ensure_unique([substep.id for substep in substeps], f"{path}.substeps[].id")
    return CalibrationStep(
        id=_required_str(data, "id", f"{path}.id"),
        name=_required_str(data, "name", f"{path}.name"),
        role=_parse_role(data.get("role", MeasurementRole.VNA_S21.value), f"{path}.role"),
        input_port=str(data.get("input_port", "")),
        output_port=str(data.get("output_port", "")),
        manual_instruction=str(data.get("manual_instruction", "")),
        route_ids=_string_tuple(data.get("route_ids", ()), f"{path}.route_ids"),
        link_commands=_string_tuple(data.get("link_commands", ()), f"{path}.link_commands"),
        raw_outputs=_string_tuple(data.get("raw_outputs", ()), f"{path}.raw_outputs"),
        final_outputs=_string_tuple(data.get("final_outputs", ()), f"{path}.final_outputs"),
        required_inputs=_string_tuple(data.get("required_inputs", ()), f"{path}.required_inputs"),
        notes=str(data.get("notes", "")),
        substeps=substeps,
        path_template=str(data.get("path_template", "")),
        path=_optional_dict(data.get("path"), f"{path}.path"),
    )


def _parse_substep(data: Any, path: str) -> CalibrationSubStep:
    if not isinstance(data, dict):
        raise LinkConfigError(f"{path} must be an object.")
    return CalibrationSubStep(
        id=_required_str(data, "id", f"{path}.id"),
        name=_required_str(data, "name", f"{path}.name"),
        input_port=str(data.get("input_port", "")),
        output_port=str(data.get("output_port", "")),
        manual_instruction=str(data.get("manual_instruction", "")),
        route_ids=_string_tuple(data.get("route_ids", ()), f"{path}.route_ids"),
        link_commands=_string_tuple(data.get("link_commands", ()), f"{path}.link_commands"),
        raw_output=str(data.get("raw_output", "")),
        final_output=str(data.get("final_output", "")),
        required_inputs=_string_tuple(data.get("required_inputs", ()), f"{path}.required_inputs"),
        notes=str(data.get("notes", "")),
        parameter=str(data.get("parameter", "S21")),
        path_template=str(data.get("path_template", "")),
        path=_optional_dict(data.get("path"), f"{path}.path"),
    )


def _parse_role(value: Any, path: str) -> MeasurementRole:
    try:
        return MeasurementRole(str(value))
    except ValueError as exc:
        allowed = ", ".join(role.value for role in MeasurementRole)
        raise LinkConfigError(f"{path} must be one of: {allowed}.") from exc


def _required_str(data: dict[str, Any], key: str, path: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LinkConfigError(f"{path} is required and must be a non-empty string.")
    return value


def _required_list(data: dict[str, Any], key: str, path: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        raise LinkConfigError(f"{path} is required and must be an array.")
    return value


def _string_tuple(value: Any, path: str) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, (list, tuple)):
        raise LinkConfigError(f"{path} must be an array of strings.")
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise LinkConfigError(f"{path}[{index}] must be a string.")
        result.append(item)
    return tuple(result)


def _optional_dict(value: Any, path: str) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise LinkConfigError(f"{path} must be an object.")
    return dict(value)


def _parse_band_config(value: Any, path: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise LinkConfigError(f"{path} must be an object.")
    entries = value.get("feed_horn_bands", ())
    if not isinstance(entries, list):
        raise LinkConfigError(f"{path}.feed_horn_bands must be an array.")
    parsed_entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        entry_path = f"{path}.feed_horn_bands[{index}]"
        if not isinstance(entry, dict):
            raise LinkConfigError(f"{entry_path} must be an object.")
        feed = _required_str(entry, "feed", f"{entry_path}.feed").strip().upper()
        horn = _required_str(entry, "horn", f"{entry_path}.horn").strip().upper()
        band = _required_str(entry, "band", f"{entry_path}.band").strip().upper()
        key = (feed, horn)
        if key in seen:
            raise LinkConfigError(f"{entry_path} duplicates feed/horn pair: {feed}/{horn}.")
        seen.add(key)
        parsed = {"feed": feed, "horn": horn, "band": band}
        for numeric_key in ("start_ghz", "stop_ghz"):
            if numeric_key in entry:
                try:
                    parsed[numeric_key] = float(entry[numeric_key])
                except (TypeError, ValueError) as exc:
                    raise LinkConfigError(f"{entry_path}.{numeric_key} must be a number.") from exc
        if "horn_gain_file" in entry:
            horn_gain_file = str(entry["horn_gain_file"]).strip()
            if horn_gain_file:
                parsed["horn_gain_file"] = horn_gain_file
        parsed_entries.append(parsed)

    result = dict(value)
    result["feed_horn_bands"] = parsed_entries
    if result.get("default_feed"):
        result["default_feed"] = str(result["default_feed"]).strip().upper()
    if result.get("default_horn"):
        result["default_horn"] = str(result["default_horn"]).strip().upper()
    return result


def _ensure_unique(values: list[str], path: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise LinkConfigError(f"{path} contains duplicate values: {', '.join(sorted(duplicates))}.")
