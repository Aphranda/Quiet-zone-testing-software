import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from quiet_zone_tester.presentation.modules.link_control import DEFAULT_LINK_COMMANDS, LinkControlViewModel
from quiet_zone_tester.ui.widgets.switch_box_control_panel import SwitchBoxControlPanel


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class LinkControlViewModelTest(unittest.TestCase):
    def test_default_commands_and_command_normalization(self) -> None:
        view_model = LinkControlViewModel()

        self.assertEqual(view_model.link_commands(), DEFAULT_LINK_COMMANDS)
        self.assertEqual(view_model.route_parameter("s21"), "S21")
        self.assertEqual(view_model.send_command("  CONFigure:LINK H,VNA1  "), "CONFigure:LINK H,VNA1")
        self.assertEqual(view_model.send_command(""), DEFAULT_LINK_COMMANDS[0])
        self.assertEqual(view_model.current_command_text("CONFigure:LINK V,VNA1"), "当前命令：CONFigure:LINK V,VNA1")

    def test_diagram_state_derives_highlighted_tokens(self) -> None:
        state = LinkControlViewModel().diagram_state(" CONFigure:LINK DUT, AMP1, SA ")

        self.assertEqual(state.selected_command, "CONFigure:LINK DUT, AMP1, SA")
        self.assertEqual(state.highlighted_tokens, frozenset({"DUT", "AMP1", "SA"}))

    def test_invalid_parameter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LinkControlViewModel().route_parameter("S31")

    def test_result_text_and_ui_state(self) -> None:
        view_model = LinkControlViewModel()

        self.assertEqual(view_model.result_text(""), "-")
        self.assertEqual(view_model.result_text(" done "), "done")
        self.assertTrue(view_model.ui_state(connected=True, busy=False).inputs_enabled)
        self.assertFalse(view_model.ui_state(connected=True, busy=True).inputs_enabled)
        self.assertFalse(view_model.ui_state(connected=False, busy=False).inputs_enabled)

    def test_switch_box_control_panel_emits_command_payloads_only(self) -> None:
        _app()
        panel = SwitchBoxControlPanel()
        command_payloads: list[str] = []
        panel.command_requested.connect(command_payloads.append)
        panel.set_switch_box_connected(True)

        panel._command.setCurrentText(" CONFigure:LINK V,VNA1 ")

        panel._send_button.click()

        self.assertFalse(hasattr(panel, "parameter_requested"))
        self.assertEqual(command_payloads, ["CONFigure:LINK V,VNA1"])

    def test_switch_box_control_panel_result_and_command_labels(self) -> None:
        _app()
        panel = SwitchBoxControlPanel()

        panel.set_result("")
        panel._set_current_command("")

        texts = [label.text() for label in panel.findChildren(QLabel)]
        self.assertIn("-", texts)
        self.assertIn(f"当前命令：{DEFAULT_LINK_COMMANDS[0]}", texts)


if __name__ == "__main__":
    unittest.main()
