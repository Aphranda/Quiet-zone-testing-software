from __future__ import annotations

from catr_loss_calibrator.hardware.mock import MockLinkBox
from catr_loss_calibrator.link_management.lcd74000f_profile import Lcd74000fProfile
from catr_loss_calibrator.link_management.link_service import LinkService
from catr_loss_calibrator.link_management.link_templates import link_command, link_route
from catr_loss_calibrator.link_management.models import LinkPort


def test_lcd74000f_profile_contains_expected_routes() -> None:
    profile = Lcd74000fProfile()
    assert profile.get_route("DUT_SA").ports == (LinkPort.DUT, LinkPort.SA)
    assert profile.get_route("DUT_AMP1_VNA2").ports == (LinkPort.DUT, LinkPort.AMP1, LinkPort.VNA2)
    assert profile.get_route("H_AMP2_SA").ports == (LinkPort.H, LinkPort.AMP2, LinkPort.SA)


def test_link_service_can_apply_route_id() -> None:
    service = LinkService(MockLinkBox())
    service.link_box.connect()
    result = service.apply_route_id("DUT_AMP1_SA")
    assert result == "OK"
    assert service.link_box.commands == ["CONFigure:LINK DUT, AMP1, SA"]


def test_link_templates_generate_command_from_route() -> None:
    route = link_route(LinkPort.H, LinkPort.AMP2, LinkPort.SG)
    assert route.to_command().command == "CONFigure:LINK H, AMP2, SG"
    assert link_command("DUT", "VNA2") == "CONFigure:LINK DUT, VNA2"


def test_lcd74000f_profile_covers_required_route_matrix() -> None:
    profile = Lcd74000fProfile()
    expected_commands = {
        "DUT_SA": "CONFigure:LINK DUT, SA",
        "DUT_AMP1_SA": "CONFigure:LINK DUT, AMP1, SA",
        "DUT_VNA2": "CONFigure:LINK DUT, VNA2",
        "DUT_AMP1_VNA2": "CONFigure:LINK DUT, AMP1, VNA2",
        "H_VNA1": "CONFigure:LINK H, VNA1",
        "V_VNA1": "CONFigure:LINK V, VNA1",
        "H_AMP2_VNA1": "CONFigure:LINK H, AMP2, VNA1",
        "V_AMP2_VNA1": "CONFigure:LINK V, AMP2, VNA1",
        "H_SA": "CONFigure:LINK H, SA",
        "V_SA": "CONFigure:LINK V, SA",
        "H_AMP2_SA": "CONFigure:LINK H, AMP2, SA",
        "V_AMP2_SA": "CONFigure:LINK V, AMP2, SA",
        "H_SG": "CONFigure:LINK H, SG",
        "V_SG": "CONFigure:LINK V, SG",
        "H_AMP2_SG": "CONFigure:LINK H, AMP2, SG",
        "V_AMP2_SG": "CONFigure:LINK V, AMP2, SG",
    }

    for route_id, command in expected_commands.items():
        route = profile.get_route(route_id)
        profile.validate_route(route)
        assert route.to_command().command == command


def test_lcd74000f_profile_rejects_invalid_amplifier_direction() -> None:
    profile = Lcd74000fProfile()

    try:
        profile.validate_route(link_route(LinkPort.AMP1, LinkPort.DUT, LinkPort.SA))
    except ValueError as exc:
        assert "AMP1 must be used after DUT" in str(exc)
    else:
        raise AssertionError("Expected AMP1 direction error.")

    try:
        profile.validate_route(link_route(LinkPort.AMP2, LinkPort.H, LinkPort.SG))
    except ValueError as exc:
        assert "AMP2 must be used after H" in str(exc)
    else:
        raise AssertionError("Expected AMP2 direction error.")


def test_calibration_steps_expose_structured_route_and_ports() -> None:
    from catr_loss_calibrator.calibration.definitions import default_calibration_catalog

    cal003 = default_calibration_catalog().get("LINK-CAL-003")
    step = cal003.steps[1]
    assert step.input_port == "DUT_REF"
    assert step.output_port == "LB-SA"
    assert step.route_ids == ("DUT_SA", "DUT_AMP1_SA")

    cal004 = default_calibration_catalog().get("LINK-CAL-004")
    amp2_step = next(step for step in cal004.steps if step.id == "CAL004-SA-HV-AMP2")
    assert amp2_step.input_port == "LB-VNA2"
    assert amp2_step.output_port == "LB-SA"
    assert amp2_step.route_ids == ("H_AMP2_SA", "V_AMP2_SA")
