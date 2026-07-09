import unittest

from quiet_zone_tester import drivers, instruments
from quiet_zone_tester.hardware import (
    InstrumentInfo,
    MockPositionerController,
    MockSwitchBoxController,
    MockVnaController,
    Position,
)
from quiet_zone_tester.hardware.interfaces import Position as HardwarePosition
from quiet_zone_tester.hardware.positioner import IclPositionerConfig
from quiet_zone_tester.hardware.switch_box import Lcd74000fSwitchBoxConfig, Tc500SwitchBoxConfig
from quiet_zone_tester.hardware.vna import VnaScpiConfig


class HardwareMigrationTest(unittest.TestCase):
    def test_hardware_exports_interfaces_and_mock_controllers(self) -> None:
        self.assertIs(Position, HardwarePosition)
        self.assertEqual(InstrumentInfo("R", "M", "S").model, "M")
        self.assertEqual(MockVnaController.__name__, "MockVnaController")
        self.assertEqual(MockPositionerController.__name__, "MockPositionerController")
        self.assertEqual(MockSwitchBoxController.__name__, "MockSwitchBoxController")

    def test_legacy_drivers_imports_reexport_hardware_classes(self) -> None:
        self.assertIs(drivers.Position, Position)
        self.assertIs(drivers.MockVnaController, MockVnaController)
        self.assertIs(drivers.MockPositionerController, MockPositionerController)
        self.assertIs(drivers.MockSwitchBoxController, MockSwitchBoxController)

    def test_legacy_instruments_imports_reexport_hardware_classes(self) -> None:
        self.assertIs(instruments.VnaScpiConfig, VnaScpiConfig)
        self.assertIs(instruments.IclPositionerConfig, IclPositionerConfig)
        self.assertIs(instruments.Lcd74000fSwitchBoxConfig, Lcd74000fSwitchBoxConfig)
        self.assertIs(instruments.Tc500SwitchBoxConfig, Tc500SwitchBoxConfig)


if __name__ == "__main__":
    unittest.main()
