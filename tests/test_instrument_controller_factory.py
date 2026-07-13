import unittest

from quiet_zone_tester.domains.instrument_management import (
    InstrumentControllerFactory,
    InstrumentControllerFactoryError,
)
from quiet_zone_tester.hardware import MockPositionerController, MockSwitchBoxController, MockVnaController, ScpiVnaController


class InstrumentControllerFactoryTest(unittest.TestCase):
    def test_creates_virtual_controllers(self) -> None:
        factory = InstrumentControllerFactory()

        vna = factory.create_vna({"virtual_enabled": True})
        positioner = factory.create_positioner({"virtual_enabled": True, "x_axis": 2, "y_axis": 3})
        switch_box = factory.create_switch_box({"virtual_enabled": True})

        self.assertIsInstance(vna, MockVnaController)
        self.assertIsInstance(positioner, MockPositionerController)
        self.assertIsInstance(switch_box, MockSwitchBoxController)

    def test_rejects_mock_resources_in_real_mode(self) -> None:
        factory = InstrumentControllerFactory()

        with self.assertRaises(InstrumentControllerFactoryError):
            factory.create_vna({"resource_name": "MOCK::VNA"})
        with self.assertRaises(InstrumentControllerFactoryError):
            factory.create_positioner({"port_name": "MOCK::POS"})
        with self.assertRaises(InstrumentControllerFactoryError):
            factory.create_switch_box({"connection_type": "SERIAL", "serial_port": "MOCK::SW"})

    def test_rejects_missing_real_connection_targets(self) -> None:
        factory = InstrumentControllerFactory()

        with self.assertRaises(InstrumentControllerFactoryError):
            factory.create_vna({})
        with self.assertRaises(InstrumentControllerFactoryError):
            factory.create_positioner({})
        with self.assertRaises(InstrumentControllerFactoryError):
            factory.create_switch_box({"connection_type": "TCP/IP"})

    def test_axis_and_scale_helpers_preserve_legacy_rules(self) -> None:
        factory = InstrumentControllerFactory()

        self.assertEqual(factory.axis_from_config({"x_axis": 2}, "x_axis", 1), 2)
        self.assertEqual(
            factory.positioner_scales_from_config(
                {
                    "pulses_per_mm": 100.0,
                    "x_units_per_turn": 2000.0,
                    "x_mm_per_turn": 2.0,
                    "y_pulses_per_mm": 120.0,
                }
            ),
            (1000.0, 1000.0, 120.0),
        )

        with self.assertRaises(InstrumentControllerFactoryError):
            factory.axis_from_config({"x_axis": 248}, "x_axis", 1)
        with self.assertRaises(InstrumentControllerFactoryError):
            factory.positioner_scales_from_config({"pulses_per_mm": 0.0})
        with self.assertRaises(InstrumentControllerFactoryError):
            factory.positioner_scales_from_config({"x_units_per_turn": 1.0, "x_mm_per_turn": 0.0})

    def test_virtual_enabled_accepts_legacy_string_values(self) -> None:
        factory = InstrumentControllerFactory()

        self.assertTrue(factory.virtual_enabled({"virtual_enabled": "虚拟连接"}))
        self.assertTrue(factory.virtual_enabled({"virtual_enabled": "yes"}))
        self.assertFalse(factory.virtual_enabled({"virtual_enabled": ""}))

    def test_creates_n5245b_controller_and_rejects_unknown_model(self) -> None:
        factory = InstrumentControllerFactory()

        vna = factory.create_vna({"model": "n5245b", "resource_name": "TCPIP0::HOST::inst0::INSTR"})

        self.assertIsInstance(vna, ScpiVnaController)
        self.assertEqual(vna._config.expected_model, "N5245B")
        with self.assertRaises(InstrumentControllerFactoryError):
            factory.create_vna({"model": "UNKNOWN", "resource_name": "TCPIP0::HOST::inst0::INSTR"})

    def test_create_vna_prefers_selected_visa_resource_over_ip_fields(self) -> None:
        factory = InstrumentControllerFactory()

        vna = factory.create_vna(
            {
                "model": "E5080B",
                "ip_address": "192.168.1.10",
                "port": 5025,
                "resource_name": "TCPIP0::NI-VISA::inst0::INSTR",
            }
        )

        self.assertEqual(vna._config.resource_name, "TCPIP0::NI-VISA::inst0::INSTR")


if __name__ == "__main__":
    unittest.main()
