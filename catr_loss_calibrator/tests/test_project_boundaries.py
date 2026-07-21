from pathlib import Path
import tomllib

from catr_loss_calibrator.calibration.config_loader import DEFAULT_CONFIG_PATH
from catr_loss_calibrator.calibration.calibration_runner import CalibrationRunner
from catr_loss_calibrator.calibration.mock_runner import MockCalibrationRunner
from catr_loss_calibrator.runtime_resources import resolve_data_file


def test_catr_loss_calibrator_has_no_legacy_runtime_imports() -> None:
    base = Path(__file__).resolve().parents[1]
    roots = [base / "src" / "catr_loss_calibrator", base / "tests"]
    forbidden = "quiet" + "_zone" + "_tester"
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if forbidden in text:
                offenders.append(str(path))
    assert offenders == []


def test_presentation_uses_production_calibration_runner_name() -> None:
    base = Path(__file__).resolve().parents[1]
    presentation_root = base / "src" / "catr_loss_calibrator" / "presentation"
    offenders = [
        str(path)
        for path in presentation_root.rglob("*.py")
        if "MockCalibrationRunner" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
    assert issubclass(MockCalibrationRunner, CalibrationRunner)


def test_package_data_includes_gui_and_default_calibration_resources() -> None:
    base = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((base / "pyproject.toml").read_text(encoding="utf-8"))

    package_data = set(pyproject["tool"]["setuptools"]["package-data"]["catr_loss_calibrator"])

    assert "calibration/configs/*.json" in package_data
    assert "resources/*.csv" in package_data
    assert "style/*.qss" in package_data
    assert "style/*.svg" in package_data
    assert "style/*.png" in package_data
    assert "style/icons/*.png" in package_data

    gitignore = (base.parent / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "!catr_loss_calibrator/src/catr_loss_calibrator/resources/*.csv" in gitignore


def test_builtin_horn_gain_file_resolves_from_packaged_resources() -> None:
    resolved = resolve_data_file(
        "../../resources/10_15G_horn_gain_10MHz.csv",
        source_path=DEFAULT_CONFIG_PATH,
    )

    assert resolved.exists()
    assert resolved.name == "10_15G_horn_gain_10MHz.csv"


def test_workspace_config_snapshot_can_fallback_to_packaged_horn_gain_file(tmp_path: Path) -> None:
    snapshot = tmp_path / "workspaces" / "demo" / "config" / "link_config_snapshot.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("{}", encoding="utf-8")

    resolved = resolve_data_file(
        "../../resources/21P7_33G_horn_gain_10MHz.csv",
        source_path=snapshot,
    )

    assert resolved.exists()
    assert resolved.name == "21P7_33G_horn_gain_10MHz.csv"
