from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    src_dir = Path(__file__).resolve().parents[1]
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

from quiet_zone_tester.app import run_app


def Main() -> int:
    return run_app()


def main() -> int:
    return Main()


if __name__ == "__main__":
    raise SystemExit(Main())
