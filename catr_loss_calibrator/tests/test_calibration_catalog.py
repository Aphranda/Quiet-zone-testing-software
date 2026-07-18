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


def test_link_cal_004_repeats_return_segment_for_independent_automation() -> None:
    item = default_calibration_catalog().get("LINK-CAL-004")
    outputs = tuple(output for step in item.steps for output in step.final_outputs)
    required = tuple(required for step in item.steps for required in step.required_inputs)
    assert "L_AUX_F" in outputs
    assert "L_DUT_VNA_F" in outputs
    assert "L_DUT_VNA_F_AMP1" in outputs
    assert "L_DUT_VNA" not in required
    assert "L_DUT_VNA_AMP1" not in required


def test_link_cal_003_is_only_dut_to_sa_outputs() -> None:
    item = default_calibration_catalog().get("LINK-CAL-003")
    assert item.name == "DUT 到 SA 校准"
    outputs = tuple(output for step in item.steps for output in step.final_outputs)
    assert outputs == ("L_AUX_E", "L_DUT_SA", "L_DUT_SA_AMP1")
    assert all("T_VNA1_SA" not in output for step in item.steps for output in step.raw_outputs)


def test_link_cal_005_amp2_output_matches_hv_to_sg_name() -> None:
    item = default_calibration_catalog().get("LINK-CAL-005")
    outputs = tuple(output for step in item.steps for output in step.final_outputs)
    assert "L_HV_SG_H/V_AMP2" in outputs
    assert "L_SG_DUT_H/V_AMP2" not in outputs


def test_link_cal_005_uses_aux_g_after_cal004_owns_aux_f() -> None:
    item = default_calibration_catalog().get("LINK-CAL-005")
    outputs = tuple(output for step in item.steps for output in step.final_outputs)
    required = tuple(required for step in item.steps for required in step.required_inputs)
    assert "L_AUX_G" in outputs
    assert "L_DUT_VNA_G" in outputs
    assert "L_DUT_VNA_G_AMP1" in outputs
    assert "L_DUT_VNA_F" not in required
