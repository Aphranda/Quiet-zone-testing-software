from pathlib import Path


def test_catr_loss_calibrator_has_no_legacy_runtime_imports() -> None:
    base = Path(__file__).resolve().parents[1]
    roots = [base / "src" / "catr_loss_calibrator", base / "tests"]
    forbidden = "quiet" + "_zone" + "_tester"
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if forbidden in text:
                offenders.append(str(path))
    assert offenders == []
