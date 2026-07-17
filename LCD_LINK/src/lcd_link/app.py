from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lcd_link.window import LcdLinkControlWindow


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv if argv is None else argv)
    window = LcdLinkControlWindow()
    window.resize(1100, 780)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
