from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path


def write_metadata(path: Path, metadata: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(metadata) if is_dataclass(metadata) else metadata
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
