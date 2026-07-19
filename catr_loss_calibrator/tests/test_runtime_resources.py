from __future__ import annotations

from pathlib import Path

from catr_loss_calibrator.calibration.config_loader import load_calibration_catalog
from catr_loss_calibrator.runtime_resources import (
    initialize_runtime_files,
    resolve_data_file,
    runtime_default_config_path,
    runtime_paths,
)


def test_runtime_paths_separate_user_config_resources_and_output(tmp_path: Path) -> None:
    env = {
        "CATR_LOSS_CALIBRATOR_HOME": str(tmp_path / "appdata"),
        "CATR_LOSS_CALIBRATOR_OUTPUT": str(tmp_path / "calibrations"),
    }

    paths = runtime_paths(env)

    assert paths.app_data_dir == tmp_path / "appdata"
    assert paths.user_config_dir == tmp_path / "appdata" / "calibration" / "configs"
    assert paths.user_resources_dir == tmp_path / "appdata" / "resources"
    assert paths.default_output_root == tmp_path / "calibrations"


def test_initialize_runtime_files_copies_default_config_and_horn_gain_csv(tmp_path: Path) -> None:
    env = {
        "CATR_LOSS_CALIBRATOR_HOME": str(tmp_path / "appdata"),
        "CATR_LOSS_CALIBRATOR_OUTPUT": str(tmp_path / "calibrations"),
    }
    paths = initialize_runtime_files(runtime_paths(env))

    assert paths.default_user_config_path.exists()
    assert (paths.user_resources_dir / "10_15G_horn_gain_10MHz.csv").exists()
    assert (paths.user_resources_dir / "14P5_22G_horn_gain_10MHz_fabricated.csv").exists()
    assert (paths.user_resources_dir / "21P7_33G_horn_gain_10MHz.csv").exists()
    assert paths.default_output_root.exists()
    assert runtime_default_config_path(env) == paths.default_user_config_path

    catalog = load_calibration_catalog(paths.default_user_config_path)
    horn_gain_file = catalog.band_config["feed_horn_bands"][0]["horn_gain_file"]
    resolved = resolve_data_file(horn_gain_file, source_path=paths.default_user_config_path)

    assert resolved == (paths.user_resources_dir / "10_15G_horn_gain_10MHz.csv").resolve()
