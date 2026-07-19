from __future__ import annotations

import csv
from pathlib import Path

import numpy as np


def save_loss_csv(
    path: Path,
    *,
    frequency_hz: np.ndarray,
    value_db: np.ndarray,
    param: str,
    band: str,
    feed: str,
    horn: str,
    source_cal: str,
    output_role: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["freq_hz", "value_db", "param", "output_role", "band", "feed", "horn", "source_cal"])
        for freq, value in zip(frequency_hz, value_db, strict=True):
            writer.writerow(
                [f"{float(freq):.12g}", f"{float(value):.9g}", param, output_role, band, feed, horn, source_cal]
            )
