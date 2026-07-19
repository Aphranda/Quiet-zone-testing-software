from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class CurveQuality:
    state: str
    label: str
    reason: str
    point_count: int = 0
    columns: tuple[str, ...] = ()

    @property
    def is_usable(self) -> bool:
        return self.state in {"OK", "SUSPECT"}

    @property
    def should_retest(self) -> bool:
        return self.state != "OK"


def analyze_curve_csv(path: Path) -> CurveQuality:
    if not path.exists():
        return CurveQuality("BROKEN", "文件缺失", f"文件不存在: {path}")
    if path.suffix.lower() != ".csv":
        return CurveQuality("NO_CURVE", "无曲线", f"{path.name} 不是 CSV 文件")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = tuple(reader.fieldnames or ())
    except Exception as exc:
        return CurveQuality("BROKEN", "读取失败", str(exc))
    if not fieldnames:
        return CurveQuality("BROKEN", "表头缺失", "CSV 没有表头")
    freq_column = _detect_frequency_column(fieldnames)
    if not freq_column:
        return CurveQuality("BROKEN", "频率列缺失", "未找到频率列")
    x_raw = np.asarray([_to_float(row.get(freq_column)) for row in rows], dtype=float)
    x_ghz = _frequency_to_ghz(freq_column, x_raw)
    y_columns = _detect_curve_columns(fieldnames, freq_column)
    if not y_columns:
        return CurveQuality("NO_CURVE", "无 dB 曲线", "未找到 dB/S21 曲线列")
    valid_columns: list[str] = []
    max_points = 0
    suspect_reasons: list[str] = []
    for column in y_columns:
        y_values = np.asarray([_to_float(row.get(column)) for row in rows], dtype=float)
        valid = np.isfinite(x_ghz) & np.isfinite(y_values)
        point_count = int(np.count_nonzero(valid))
        if point_count < 2:
            continue
        valid_columns.append(column)
        max_points = max(max_points, point_count)
        x_valid = x_ghz[valid]
        y_valid = y_values[valid]
        if np.any(np.diff(x_valid) <= 0):
            suspect_reasons.append(f"{column}: 频率不是严格递增")
        if len(y_valid) >= 2 and float(np.nanmax(np.abs(np.diff(y_valid)))) > 80.0:
            suspect_reasons.append(f"{column}: 相邻点跳变超过 80 dB")
    if not valid_columns:
        return CurveQuality("BROKEN", "有效点不足", "所有曲线列有效点少于 2 个")
    if suspect_reasons:
        return CurveQuality("SUSPECT", "读取可疑", "; ".join(suspect_reasons), max_points, tuple(valid_columns))
    return CurveQuality("OK", "曲线可读取", "CSV 曲线可读取，质量需人工判定", max_points, tuple(valid_columns))


def _detect_frequency_column(fieldnames: tuple[str, ...]) -> str:
    normalized = {name.strip().lower(): name for name in fieldnames}
    for candidate in ("freq_hz", "frequency_hz", "freq", "frequency", "freq_ghz", "frequency_ghz", "freq_mhz", "frequency_mhz"):
        if candidate in normalized:
            return normalized[candidate]
    for name in fieldnames:
        if "freq" in name.strip().lower():
            return name
    return ""


def _detect_curve_columns(fieldnames: tuple[str, ...], freq_column: str) -> list[str]:
    priority = ("value_db", "raw_s21_db", "gain_db", "loss_db", "s21_db")
    lower_to_name = {name.strip().lower(): name for name in fieldnames}
    columns = [lower_to_name[name] for name in priority if name in lower_to_name and lower_to_name[name] != freq_column]
    for name in fieldnames:
        lower = name.strip().lower()
        if name == freq_column or name in columns:
            continue
        if lower.endswith("_db") or lower.endswith("_dbi") or "s21" in lower:
            columns.append(name)
    return columns


def _frequency_to_ghz(column: str, values: np.ndarray) -> np.ndarray:
    lower = column.strip().lower()
    if "ghz" in lower:
        return values
    if "mhz" in lower:
        return values / 1000.0
    return values / 1e9 if np.any(np.isfinite(values)) and np.nanmax(values) > 1e6 else values


def _to_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return float("nan")
