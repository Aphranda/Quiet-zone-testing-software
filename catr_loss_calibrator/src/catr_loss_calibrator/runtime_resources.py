from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys
from collections.abc import Mapping


APP_DIR_NAME = "CATRLossCalibrator"
APP_DISPLAY_DIR_NAME = "CATR Loss Calibrator"
PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "calibration" / "configs" / "catr_chamber_loss_calibration.json"
PACKAGE_RESOURCES_DIR = PACKAGE_ROOT / "resources"
PACKAGE_STYLE_DIR = PACKAGE_ROOT / "style"
LEGACY_RESOURCE_FILENAMES = {
    "14P5_22G_horn_gain_10MHz_fabricated.csv": "14P5_22G_horn_gain_10MHz.csv",
}


@dataclass(frozen=True)
class RuntimePaths:
    is_frozen: bool
    bundled_root: Path
    app_data_dir: Path
    user_config_dir: Path
    user_resources_dir: Path
    default_user_config_path: Path
    default_output_root: Path


def runtime_paths(env: Mapping[str, str] | None = None) -> RuntimePaths:
    values = os.environ if env is None else env
    app_data_dir = _user_app_data_dir(values)
    user_config_dir = app_data_dir / "calibration" / "configs"
    return RuntimePaths(
        is_frozen=is_frozen_app(),
        bundled_root=bundled_root(),
        app_data_dir=app_data_dir,
        user_config_dir=user_config_dir,
        user_resources_dir=app_data_dir / "resources",
        default_user_config_path=user_config_dir / PACKAGE_DEFAULT_CONFIG_PATH.name,
        default_output_root=_default_output_root(values),
    )


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundled_root() -> Path:
    if is_frozen_app():
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            root = Path(str(meipass))
            package_root = root / "catr_loss_calibrator"
            return package_root if package_root.exists() else root
    return PACKAGE_ROOT


def initialize_runtime_files(
    paths: RuntimePaths | None = None,
    *,
    overwrite: bool = False,
) -> RuntimePaths:
    paths = paths or runtime_paths()
    paths.user_config_dir.mkdir(parents=True, exist_ok=True)
    paths.user_resources_dir.mkdir(parents=True, exist_ok=True)
    paths.default_output_root.mkdir(parents=True, exist_ok=True)

    _copy_if_needed(PACKAGE_DEFAULT_CONFIG_PATH, paths.default_user_config_path, overwrite=overwrite)
    for source in sorted(PACKAGE_RESOURCES_DIR.glob("*.csv")):
        _copy_if_needed(source, paths.user_resources_dir / source.name, overwrite=overwrite)
    _migrate_legacy_resource_names(paths.default_user_config_path)
    return paths


def runtime_default_config_path(env: Mapping[str, str] | None = None) -> Path:
    paths = runtime_paths(env)
    return paths.default_user_config_path if paths.default_user_config_path.exists() else PACKAGE_DEFAULT_CONFIG_PATH


def default_output_root(env: Mapping[str, str] | None = None) -> Path:
    return runtime_paths(env).default_output_root


def resolve_data_file(path_text: str | Path, *, source_path: str | Path | None = None) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path

    candidates: list[Path] = []
    if source_path:
        source = Path(source_path)
        source_dir = source if source.is_dir() else source.parent
        candidates.append(source_dir / path)

    candidates.append(PACKAGE_ROOT / path)
    candidates.append(runtime_paths().user_resources_dir / path.name)
    candidates.append(PACKAGE_RESOURCES_DIR / path.name)

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve() if candidates else path.resolve()


def _copy_if_needed(source: Path, target: Path, *, overwrite: bool) -> None:
    if not source.exists():
        return
    if target.exists() and not overwrite:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _migrate_legacy_resource_names(config_path: Path) -> None:
    if not config_path.exists():
        return

    text = config_path.read_text(encoding="utf-8")
    migrated = text
    for legacy_name, current_name in LEGACY_RESOURCE_FILENAMES.items():
        migrated = migrated.replace(legacy_name, current_name)
    if migrated != text:
        config_path.write_text(migrated, encoding="utf-8")


def _user_app_data_dir(env: Mapping[str, str]) -> Path:
    override = str(env.get("CATR_LOSS_CALIBRATOR_HOME", "")).strip()
    if override:
        return Path(override)
    if os.name == "nt":
        appdata = str(env.get("APPDATA", "")).strip()
        if appdata:
            return Path(appdata) / APP_DIR_NAME
        userprofile = str(env.get("USERPROFILE", "")).strip()
        if userprofile:
            return Path(userprofile) / "AppData" / "Roaming" / APP_DIR_NAME
    xdg_config = str(env.get("XDG_CONFIG_HOME", "")).strip()
    if xdg_config:
        return Path(xdg_config) / APP_DIR_NAME
    return Path.home() / ".config" / APP_DIR_NAME


def _default_output_root(env: Mapping[str, str]) -> Path:
    override = str(env.get("CATR_LOSS_CALIBRATOR_OUTPUT", "")).strip()
    if override:
        return Path(override)
    return _user_documents_dir(env) / APP_DISPLAY_DIR_NAME / "Calibrations"


def _user_documents_dir(env: Mapping[str, str]) -> Path:
    override = str(env.get("CATR_LOSS_CALIBRATOR_DOCUMENTS", "")).strip()
    if override:
        return Path(override)
    home_text = str(env.get("USERPROFILE") or env.get("HOME") or "").strip()
    home = Path(home_text) if home_text else Path.home()
    documents = home / "Documents"
    return documents if documents.exists() else home
