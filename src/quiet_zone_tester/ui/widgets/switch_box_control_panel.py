from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from quiet_zone_tester.presentation.modules.link_control import DEFAULT_LINK_COMMANDS, LinkControlViewModel
from quiet_zone_tester.resources import resource_path


class SwitchBoxDiagramWidget(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source_pixmap = QPixmap(str(resource_path("原始链路图.png")))
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: #ffffff;")
        self.setMinimumSize(720, 420)
        self._refresh_pixmap()

    def set_link_state(self, *, selected_command: str, highlighted_tokens: frozenset[str]) -> None:
        del selected_command, highlighted_tokens

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override.
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            self.setText("链路图加载失败")
            return
        available_size = self.size() * self.devicePixelRatioF()
        scaled = self._source_pixmap.scaled(
            available_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(self.devicePixelRatioF())
        self.setPixmap(scaled)

class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class SwitchBoxControlPanel(QGroupBox):
    command_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("开关箱控制", parent)
        self._view_model = LinkControlViewModel()
        self._busy = False
        self._connected = False

        self._command = NoWheelComboBox()
        self._command.setEditable(True)
        self._command.addItems(DEFAULT_LINK_COMMANDS)
        self._diagram = SwitchBoxDiagramWidget()
        self._current_command = QLabel()
        self._current_command.setWordWrap(True)
        self._command.currentTextChanged.connect(self._set_current_command)

        self._last_result = QLabel("-")
        self._last_result.setWordWrap(True)

        self._send_button = QPushButton("发送链路命令")
        self._send_button.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self._send_button.clicked.connect(
            lambda: self.command_requested.emit(self._view_model.send_command(self._command.currentText()))
        )

        self._input_widgets: list[QWidget] = [
            self._command,
            self._send_button,
        ]

        command_group = QGroupBox("链路命令")
        command_form = QFormLayout(command_group)
        command_form.addRow("命令", self._command)
        command_form.addRow("", self._send_button)

        result_group = QGroupBox("执行结果")
        result_layout = QVBoxLayout(result_group)
        result_layout.addWidget(self._last_result)

        layout = QVBoxLayout(self)
        layout.addWidget(self._diagram)
        layout.addWidget(self._current_command)
        layout.addWidget(command_group)
        layout.addWidget(result_group)
        layout.addStretch(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._set_current_command(self._command.currentText())
        self._refresh_enabled_state()

    def set_switch_box_connected(self, connected: bool) -> None:
        self._connected = connected
        if not connected:
            self._last_result.setText("-")
        self._refresh_enabled_state()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh_enabled_state()

    def set_result(self, message: str) -> None:
        self._last_result.setText(self._view_model.result_text(message))

    def _set_current_command(self, command: str) -> None:
        state = self._view_model.diagram_state(command)
        self._diagram.set_link_state(
            selected_command=state.selected_command,
            highlighted_tokens=state.highlighted_tokens,
        )
        self._current_command.setText(self._view_model.current_command_text(state.selected_command))

    def _refresh_enabled_state(self) -> None:
        state = self._view_model.ui_state(connected=self._connected, busy=self._busy)
        for widget in self._input_widgets:
            widget.setEnabled(state.inputs_enabled)
