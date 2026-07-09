import unittest

from quiet_zone_tester.domains.instrument_management import (
    InstrumentConnectionConfig,
    PositionerConnectionConfig,
    SwitchBoxConnectionConfig,
    VnaConnectionConfig,
)


class ConnectionConfigTest(unittest.TestCase):
    def test_instrument_connection_config_accepts_current_ui_dict(self) -> None:
        config = InstrumentConnectionConfig.from_dict(
            {
                "vna": {
                    "virtual_enabled": "true",
                    "ip_address": "192.168.1.10",
                    "port": 5025,
                    "resource_name": "TCPIP0::192.168.1.10::5025::SOCKET",
                    "timeout_ms": 6000,
                },
                "positioner": {
                    "port_name": "COM7",
                    "resource_name": "COM7",
                    "baudrate": 115200,
                    "x_axis": 2,
                    "y_axis": 3,
                    "pulses_per_mm": 1000.0,
                    "x_pulses_per_mm": 1000.0,
                    "y_pulses_per_mm": 1001.0,
                    "default_speed": 25.0,
                },
                "switch_box": {
                    "model": "LCD74000F",
                    "connection_type": "TCP/IP",
                    "ip_address": "192.168.1.113",
                    "tcp_port": 7,
                    "serial_port": "COM8",
                    "baudrate": 115200,
                    "timeout_ms": 2000,
                },
            }
        )

        self.assertTrue(config.vna.virtual_enabled)
        self.assertEqual(config.vna.ip_address, "192.168.1.10")
        self.assertEqual(config.positioner.port_name, "COM7")
        self.assertEqual(config.positioner.y_pulses_per_mm, 1001.0)
        self.assertEqual(config.switch_box.model, "LCD74000F")
        self.assertEqual(config.switch_box.tcp_port, 7)

    def test_vna_config_round_trips_legacy_dict_keys(self) -> None:
        config = VnaConnectionConfig.from_dict({"resource_name": "TCPIP0::HOST::inst0::INSTR", "timeout_ms": 3000})

        self.assertEqual(
            config.to_dict(),
            {
                "virtual_enabled": False,
                "ip_address": "",
                "port": 5025,
                "resource_name": "TCPIP0::HOST::inst0::INSTR",
                "timeout_ms": 3000,
                "retries": 2,
                "retry_delay_s": 0.2,
            },
        )

    def test_positioner_config_uses_resource_name_as_port_fallback(self) -> None:
        config = PositionerConnectionConfig.from_dict({"resource_name": "COM5", "pulses_per_degree": 500.0})

        self.assertEqual(config.port_name, "COM5")
        self.assertEqual(config.resource_name, "COM5")
        self.assertEqual(config.pulses_per_mm, 500.0)
        self.assertEqual(config.to_dict()["pulses_per_degree"], 500.0)

    def test_switch_box_config_uses_model_specific_defaults(self) -> None:
        tc500 = SwitchBoxConnectionConfig.from_dict({"model": "TC500"})
        lcd74000f = SwitchBoxConnectionConfig.from_dict({"model": "LCD74000F"})

        self.assertEqual(tc500.tcp_port, 35)
        self.assertEqual(tc500.timeout_ms, 1500)
        self.assertEqual(lcd74000f.tcp_port, 7)
        self.assertEqual(lcd74000f.timeout_ms, 2000)


if __name__ == "__main__":
    unittest.main()
