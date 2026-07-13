from __future__ import annotations

import sys
from pathlib import Path


def resource_path(name: str) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "resource" / name)
    candidates.extend((
        Path.cwd() / "resource" / name,
        project_root / "resource" / name,
    ))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]
