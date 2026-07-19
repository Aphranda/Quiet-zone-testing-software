from catr_loss_calibrator.calibration.definitions import default_calibration_catalog, legacy_python_calibration_catalog
from catr_loss_calibrator.calibration.config_loader import DEFAULT_CONFIG_PATH, load_calibration_catalog
from catr_loss_calibrator.calibration.models import OutputRole, classify_output_parameter
from catr_loss_calibrator.storage.loss_file_policy import default_feed_horn_from_config


def test_default_catalog_contains_five_calibration_items() -> None:
    catalog = default_calibration_catalog()
    assert [item.id for item in catalog.items] == [
        "LINK-CAL-001",
        "LINK-CAL-002",
        "LINK-CAL-003",
        "LINK-CAL-004",
        "LINK-CAL-005",
    ]
    assert catalog.schema_version == "catr-link-config.v1"
    assert catalog.source_path.endswith("catr_chamber_loss_calibration.json")


def test_builtin_json_catalog_matches_legacy_python_catalog() -> None:
    imported = load_calibration_catalog(DEFAULT_CONFIG_PATH)
    legacy = legacy_python_calibration_catalog()

    assert [item.id for item in imported.items] == [item.id for item in legacy.items]
    for imported_item, legacy_item in zip(imported.items, legacy.items):
        assert imported_item.name == legacy_item.name
        assert [step.id for step in imported_item.steps] == [step.id for step in legacy_item.steps]
        for imported_step, legacy_step in zip(imported_item.steps, legacy_item.steps):
            assert imported_step.role == legacy_step.role
            assert imported_step.link_commands == legacy_step.link_commands
            assert imported_step.raw_outputs == legacy_step.raw_outputs
            assert imported_step.final_outputs == legacy_step.final_outputs
            assert imported_step.required_inputs == legacy_step.required_inputs
            assert [substep.id for substep in imported_step.substeps] == [
                substep.id for substep in legacy_step.substeps
            ]


def test_builtin_json_catalog_contains_path_node_templates() -> None:
    catalog = load_calibration_catalog(DEFAULT_CONFIG_PATH)
    assert catalog.node_catalog["PORT1"]["label"] == "网分 PORT1"
    assert catalog.path_templates["CAL001-AUX:AUX-B"]["routes"][0]["nodes"] == [
        "PORT1",
        "AUX-B",
        "PORT2",
    ]
    assert catalog.path_templates["CAL002-MAIN:V-AMP2"]["routes"][0]["nodes"][-3:] == [
        "AMP2",
        "LB-VNA1",
        "PORT2",
    ]


def test_builtin_json_catalog_contains_band_config() -> None:
    catalog = load_calibration_catalog(DEFAULT_CONFIG_PATH)

    assert default_feed_horn_from_config(catalog.band_config) == ("F10_17G", "H10_15G")
    first_entry = catalog.band_config["feed_horn_bands"][0]
    assert first_entry == {
        "feed": "F10_17G",
        "horn": "H10_15G",
        "band": "10_15G",
        "start_ghz": 10.0,
        "stop_ghz": 15.0,
        "horn_gain_file": "../../../../resources/10_15G_horn_gain_10MHz.csv",
    }
    assert any(
        entry["horn"] == "H14P5_22G" and entry["horn_gain_file"].endswith("fabricated.csv")
        for entry in catalog.band_config["feed_horn_bands"]
    )


def test_builtin_json_steps_reference_path_templates() -> None:
    catalog = load_calibration_catalog(DEFAULT_CONFIG_PATH)
    existing_templates = set(catalog.path_templates)

    expected_refs = {
        "CAL001-AUX:AUX-B",
        "CAL001-V",
        "CAL002-MAIN:V-AMP2",
        "CAL004-SA-HV-AMP2:V-AMP2-SA",
        "CAL005-SG:V-AMP2-SG",
    }
    actual_refs = {
        step.path_template
        for item in catalog.items
        for step in item.steps
        if step.path_template
    } | {
        substep.path_template
        for item in catalog.items
        for step in item.steps
        for substep in step.substeps
        if substep.path_template
    }

    assert expected_refs <= actual_refs
    assert actual_refs <= existing_templates


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


def test_link_cal_003_dut_sa_is_split_into_substeps() -> None:
    item = default_calibration_catalog().get("LINK-CAL-003")
    step = next(step for step in item.steps if step.id == "CAL003-DUT-SA")

    assert [substep.id for substep in step.substeps] == ["DUT-SA", "DUT-AMP1-SA"]
    assert [substep.link_commands for substep in step.substeps] == [
        ("CONFigure:LINK DUT, SA",),
        ("CONFigure:LINK DUT, AMP1, SA",),
    ]
    assert [substep.path_template for substep in step.substeps] == [
        "CAL003-DUT-SA:DUT-SA",
        "CAL003-DUT-SA:DUT-AMP1-SA",
    ]


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


def test_output_parameter_roles_distinguish_raw_temporary_and_final_outputs() -> None:
    assert classify_output_parameter("S21_AUX_A") == OutputRole.RAW_S21
    assert classify_output_parameter("T_SYS_TX_SA_H") == OutputRole.TEMPORARY
    assert classify_output_parameter("L_CH_INT_H") == OutputRole.FINAL

    item = default_calibration_catalog().get("LINK-CAL-002")
    main_step = next(step for step in item.steps if step.id == "CAL002-MAIN")

    assert main_step.outputs_by_role(OutputRole.RAW_S21) == ()
    assert "L_VNA_H" in main_step.outputs_by_role(OutputRole.TEMPORARY)
    assert "L_VNA_FEED_H" in main_step.outputs_by_role(OutputRole.FINAL)
