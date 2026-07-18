from catr_loss_calibrator.calibration.definitions import default_calibration_catalog


def test_default_catalog_contains_five_calibration_items() -> None:
    catalog = default_calibration_catalog()
    assert [item.id for item in catalog.items] == [
        "LINK-CAL-001",
        "LINK-CAL-002",
        "LINK-CAL-003",
        "LINK-CAL-004",
        "LINK-CAL-005",
    ]


def test_link_cal_005_contains_sg_commands() -> None:
    item = default_calibration_catalog().get("LINK-CAL-005")
    commands = tuple(command for step in item.steps for command in step.link_commands)
    assert "CONFigure:LINK H/V, SG" in commands
    assert "CONFigure:LINK H/V, AMP2, SG" in commands


def test_link_cal_004_contains_sa_hv_commands() -> None:
    item = default_calibration_catalog().get("LINK-CAL-004")
    commands = tuple(command for step in item.steps for command in step.link_commands)
    assert "CONFigure:LINK H/V, SA" in commands
    assert "CONFigure:LINK H/V, AMP2, SA" in commands
