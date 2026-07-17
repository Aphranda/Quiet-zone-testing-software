import unittest

from quiet_zone_tester.domains.link_management import LinkService, LinkServiceError


class _SwitchBox:
    def __init__(self, connected: bool = True) -> None:
        self._connected = connected
        self.selected_parameters: list[str] = []
        self.sent_commands: list[str] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    def select_s_parameter(self, parameter: str) -> str:
        self.selected_parameters.append(parameter)
        return f"ROUTE {parameter}"

    def send_command(self, command: str) -> str:
        self.sent_commands.append(command)
        return f"OK {command}"


class LinkServiceTest(unittest.TestCase):
    def test_select_s_parameter_normalizes_parameter_and_returns_command(self) -> None:
        switch_box = _SwitchBox()

        command = LinkService(switch_box).select_s_parameter("s21")

        self.assertEqual(command, "ROUTE S21")
        self.assertEqual(switch_box.selected_parameters, ["S21"])

    def test_send_command_trims_command_and_returns_response(self) -> None:
        switch_box = _SwitchBox()

        response = LinkService(switch_box).send_command("  CONFigure:LINK H,VNA1  ")

        self.assertEqual(response, "OK CONFigure:LINK H,VNA1")
        self.assertEqual(switch_box.sent_commands, ["CONFigure:LINK H,VNA1"])

    def test_select_polarization_sends_link_command(self) -> None:
        switch_box = _SwitchBox()

        response = LinkService(switch_box).select_polarization("v")

        self.assertEqual(response, "OK CONFigure:LINK V, VNA1")
        self.assertEqual(switch_box.sent_commands, ["CONFigure:LINK V, VNA1"])
        self.assertEqual(switch_box.selected_parameters, [])

    def test_select_dut_path_sends_link_command(self) -> None:
        switch_box = _SwitchBox()

        response = LinkService(switch_box).select_dut_path("sa")

        self.assertEqual(response, "OK CONFigure:LINK DUT, AMP1, SA")
        self.assertEqual(switch_box.sent_commands, ["CONFigure:LINK DUT, AMP1, SA"])
        self.assertEqual(switch_box.selected_parameters, [])

    def test_select_dut_path_to_vna2_uses_direct_link(self) -> None:
        switch_box = _SwitchBox()

        response = LinkService(switch_box).select_dut_path("vna2")

        self.assertEqual(response, "OK CONFigure:LINK DUT, VNA2")
        self.assertEqual(switch_box.sent_commands, ["CONFigure:LINK DUT, VNA2"])
        self.assertEqual(switch_box.selected_parameters, [])

    def test_select_dut_path_to_vna2_amp1_uses_amplified_link(self) -> None:
        switch_box = _SwitchBox()

        response = LinkService(switch_box).select_dut_path("vna2_amp1")

        self.assertEqual(response, "OK CONFigure:LINK DUT, AMP1, VNA2")
        self.assertEqual(switch_box.sent_commands, ["CONFigure:LINK DUT, AMP1, VNA2"])
        self.assertEqual(switch_box.selected_parameters, [])

    def test_rejects_unconnected_controller(self) -> None:
        service = LinkService(_SwitchBox(connected=False))

        with self.assertRaises(LinkServiceError):
            service.select_s_parameter("S21")
        with self.assertRaises(LinkServiceError):
            service.send_command("PASSIVE")

    def test_rejects_invalid_parameter_and_empty_command(self) -> None:
        service = LinkService(_SwitchBox())

        with self.assertRaises(ValueError):
            service.select_s_parameter("S31")
        with self.assertRaises(LinkServiceError):
            service.send_command("  ")
        with self.assertRaises(LinkServiceError):
            service.select_polarization("X")
        with self.assertRaises(LinkServiceError):
            service.select_dut_path("VNA1")


if __name__ == "__main__":
    unittest.main()
