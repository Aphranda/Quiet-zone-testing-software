import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quiet_zone_tester.presentation.modules.connection import (
    ConnectionState,
    ConnectionViewModel,
    PositionerFormState,
    SwitchBoxFormState,
    VnaFormState,
)
from quiet_zone_tester.ui.widgets.connection_panel import ConnectionPanel


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class ConnectionViewModelTest(unittest.TestCase):
    def test_build_config_preserves_legacy_dict_shape(self) -> None:
        view_model = ConnectionViewModel(serial_port_provider=lambda: ["COM3", "COM4"])

        config = view_model.build_config(
            vna=VnaFormState(
                virtual_enabled=True,
                model="N5245B",
                ip_address="192.168.1.10",
                port=5025,
                timeout_ms=5000,
            ),
            positioner=PositionerFormState(
                port_name="COM3",
                baudrate=115200,
                default_speed=50.0,
                timeout_ms=1000,
                pulses_per_mm=400.0,
            ),
            switch_box=SwitchBoxFormState(
                model="LCD74000F",
                connection_type="TCP/IP",
                ip_address="192.168.1.113",
                tcp_port=7,
                serial_port="COM4",
                baudrate=115200,
                timeout_ms=2000,
            ),
        )

        self.assertEqual(config["vna"]["resource_name"], "TCPIP0::192.168.1.10::5025::SOCKET")
        self.assertTrue(config["vna"]["virtual_enabled"])
        self.assertEqual(config["vna"]["model"], "N5245B")
        self.assertEqual(config["positioner"]["port_name"], "COM3")
        self.assertEqual(config["positioner"]["x_axis"], 2)
        self.assertEqual(config["positioner"]["x_pulses_per_mm"], 400.0)
        self.assertEqual(config["switch_box"]["model"], "LCD74000F")
        self.assertEqual(config["switch_box"]["tcp_port"], 7)

    def test_switch_box_model_defaults(self) -> None:
        lcd = ConnectionViewModel.switch_box_defaults("LCD74000F")
        tc500 = ConnectionViewModel.switch_box_defaults("TC500")

        self.assertEqual(lcd.connection_type, "TCP/IP")
        self.assertEqual(lcd.ip_address, "192.168.1.113")
        self.assertEqual(lcd.tcp_port, 7)
        self.assertEqual(tc500.connection_type, "Serial")
        self.assertEqual(tc500.ip_address, "192.168.1.120")
        self.assertEqual(tc500.tcp_port, 35)

    def test_serial_provider_failure_returns_empty_list(self) -> None:
        def fail() -> list[str]:
            raise RuntimeError("serial unavailable")

        with self.assertLogs("quiet_zone_tester.presentation.modules.connection.connection_view_model", level="ERROR"):
            self.assertEqual(ConnectionViewModel(serial_port_provider=fail).available_serial_ports(), [])

    def test_panel_state_describes_connection_status_and_buttons(self) -> None:
        disconnected = ConnectionViewModel.panel_state(
            connection=ConnectionState(),
            busy=False,
        )
        self.assertEqual(disconnected.state_text, "未连接")
        self.assertTrue(disconnected.connect_all_enabled)
        self.assertFalse(disconnected.disconnect_all_enabled)
        self.assertTrue(disconnected.connect_vna_enabled)

        partial = ConnectionViewModel.panel_state(
            connection=ConnectionState(vna_connected=True, positioner_connected=True),
            busy=False,
        )
        self.assertEqual(partial.state_text, "已连接：网分、扫描架")
        self.assertTrue(partial.connect_all_enabled)
        self.assertTrue(partial.disconnect_vna_enabled)
        self.assertFalse(partial.connect_vna_enabled)

        all_connected = ConnectionViewModel.panel_state(
            connection=ConnectionState(vna_connected=True, positioner_connected=True, switch_box_connected=True),
            busy=False,
        )
        self.assertEqual(all_connected.state_text, "全部已连接")
        self.assertFalse(all_connected.connect_all_enabled)
        self.assertTrue(all_connected.disconnect_all_enabled)

        busy = ConnectionViewModel.panel_state(
            connection=ConnectionState(vna_connected=True),
            busy=True,
        )
        self.assertEqual(busy.state_text, "处理中...")
        self.assertFalse(busy.connect_all_enabled)
        self.assertFalse(busy.disconnect_all_enabled)

    def test_connection_panel_current_config_still_returns_dict(self) -> None:
        _app()
        panel = ConnectionPanel()

        config = panel.current_config()

        self.assertIn("vna", config)
        self.assertIn("positioner", config)
        self.assertIn("switch_box", config)
        self.assertEqual(config["vna"]["resource_name"], "TCPIP0::192.168.1.10::5025::SOCKET")
        self.assertEqual(config["vna"]["model"], "E5080B")
        self.assertEqual(config["switch_box"]["model"], "LCD74000F")


if __name__ == "__main__":
    unittest.main()
