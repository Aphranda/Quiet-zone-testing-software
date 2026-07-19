from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_runtime_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATR_LOSS_CALIBRATOR_HOME", str(tmp_path / "appdata"))
    monkeypatch.setenv("CATR_LOSS_CALIBRATOR_OUTPUT", str(tmp_path / "calibrations"))
