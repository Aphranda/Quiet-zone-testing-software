import unittest

from quiet_zone_tester.domains.link_management import (
    LCD74000F_PROFILE,
    LinkRouter,
    TC500_PROFILE,
    switch_box_profile_from_commands,
)


class LinkRouterTest(unittest.TestCase):
    def test_lcd74000f_profile_routes_horizontal_and_vertical_parameters(self) -> None:
        router = LinkRouter(LCD74000F_PROFILE)

        self.assertEqual(router.resolve("s21").command, "CONFigure:LINK H,VNA1")
        self.assertEqual(router.resolve("S11").command, "CONFigure:LINK H,VNA1")
        self.assertEqual(router.resolve("S12").command, "CONFigure:LINK V,VNA1")
        self.assertEqual(router.resolve("S22").command, "CONFigure:LINK V,VNA1")

    def test_tc500_profile_routes_all_parameters_to_passive(self) -> None:
        router = LinkRouter(TC500_PROFILE)

        for parameter in ("S11", "S21", "S12", "S22"):
            route = router.resolve(parameter)
            self.assertEqual(route.parameter, parameter)
            self.assertEqual(route.command, "PASSIVE")

    def test_custom_profile_commands_override_defaults(self) -> None:
        profile = switch_box_profile_from_commands(
            "LCD74000F",
            s11_command="CONFigure:LINK H,VNA1",
            s21_command="CONFigure:LINK H,AMP2,VNA1",
            s12_command="CONFigure:LINK V,VNA1",
            s22_command="CONFigure:LINK V,AMP2,VNA1",
        )
        router = LinkRouter(profile)

        self.assertEqual(router.resolve("S21").command, "CONFigure:LINK H,AMP2,VNA1")
        self.assertEqual(router.resolve("S22").command, "CONFigure:LINK V,AMP2,VNA1")

    def test_unsupported_parameter_is_rejected(self) -> None:
        router = LinkRouter(TC500_PROFILE)

        with self.assertRaises(ValueError):
            router.resolve("S31")


if __name__ == "__main__":
    unittest.main()
