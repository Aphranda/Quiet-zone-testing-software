from __future__ import annotations

from pathlib import Path
import sys

if __package__ is None or __package__ == "":  # pragma: no cover - direct script execution support
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from catr_loss_calibrator.presentation.main import run


def main() -> int:
    return run()


if __name__ == "__main__":  # pragma: no cover - direct script execution support
    raise SystemExit(main())
"""  """