from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


pytest.importorskip("PySide6")


def test_gui_smoke_starts_main_window_and_loads_default_catalog() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(project_root / "src")
    env["QT_QPA_PLATFORM"] = "offscreen"

    result = subprocess.run(
        [sys.executable, "-m", "catr_loss_calibrator", "--gui-smoke"],
        cwd=project_root,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
