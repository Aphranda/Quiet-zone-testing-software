from __future__ import annotations

from pathlib import Path

from catr_loss_calibrator.storage.resume import analyze_curve_csv


def test_analyze_curve_csv_accepts_valid_db_curve(tmp_path: Path) -> None:
    path = tmp_path / "valid.csv"
    path.write_text("freq_hz,value_db\n10000000000,1.0\n10010000000,1.2\n", encoding="utf-8")

    quality = analyze_curve_csv(path)

    assert quality.state == "OK"
    assert quality.is_usable
    assert not quality.should_retest
    assert quality.point_count == 2
    assert quality.columns == ("value_db",)


def test_analyze_curve_csv_reports_no_curve_without_db_columns(tmp_path: Path) -> None:
    path = tmp_path / "no_curve.csv"
    path.write_text("freq_hz,phase_deg\n10000000000,0\n10010000000,1\n", encoding="utf-8")

    quality = analyze_curve_csv(path)

    assert quality.state == "NO_CURVE"
    assert quality.should_retest


def test_analyze_curve_csv_marks_non_monotonic_frequency_suspect(tmp_path: Path) -> None:
    path = tmp_path / "suspect.csv"
    path.write_text("freq_hz,value_db\n10010000000,1.0\n10000000000,1.2\n", encoding="utf-8")

    quality = analyze_curve_csv(path)

    assert quality.state == "SUSPECT"
    assert quality.is_usable
    assert quality.should_retest
    assert "频率不是严格递增" in quality.reason


def test_analyze_curve_csv_reports_missing_file(tmp_path: Path) -> None:
    quality = analyze_curve_csv(tmp_path / "missing.csv")

    assert quality.state == "BROKEN"
    assert not quality.is_usable
    assert quality.should_retest
