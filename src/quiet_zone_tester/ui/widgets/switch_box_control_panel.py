from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
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


class SwitchBoxDiagramWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_command = DEFAULT_LINK_COMMANDS[0]
        self._highlighted_tokens: frozenset[str] = frozenset()
        self.setMinimumSize(720, 420)

    def set_link_state(self, *, selected_command: str, highlighted_tokens: frozenset[str]) -> None:
        self._selected_command = selected_command
        self._highlighted_tokens = highlighted_tokens
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override.
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#ffffff"))

        margin = 12.0
        logical_w = 760.0
        logical_h = 420.0
        scale = min((self.width() - margin * 2.0) / logical_w, (self.height() - margin * 2.0) / logical_h)
        offset_x = (self.width() - logical_w * scale) / 2.0
        offset_y = (self.height() - logical_h * scale) / 2.0

        def pt(x: float, y: float) -> QPointF:
            return QPointF(offset_x + x * scale, offset_y + y * scale)

        def rect(x: float, y: float, w: float, h: float) -> QRectF:
            return QRectF(offset_x + x * scale, offset_y + y * scale, w * scale, h * scale)

        painter.setFont(QFont("Microsoft YaHei UI", max(9, int(13 * scale)), QFont.Bold))
        painter.setPen(QColor("#000000"))
        painter.drawText(rect(0, 0, logical_w, 24), Qt.AlignCenter, "开关切换箱")

        border_pen = QPen(QColor("#000000"), max(1.0, scale))
        border_pen.setStyle(Qt.DashLine)
        painter.setPen(border_pen)
        painter.drawRect(rect(70, 48, 620, 282))

        line_pen = QPen(QColor("#000000"), max(1.0, scale))
        painter.setPen(line_pen)
        self._draw_topology(painter, pt, rect, scale)

    def _draw_topology(self, painter: QPainter, pt, rect, scale: float) -> None:
        highlighted = self._highlighted_tokens
        line_pen = QPen(QColor("#101828"), max(1.4, 1.4 * scale))
        muted_pen = QPen(QColor("#667085"), max(1.0, 1.0 * scale))
        active_pen = QPen(QColor("#e11d25"), max(2.4, 3.0 * scale))

        def line(x1: float, y1: float, x2: float, y2: float, active: bool = False) -> None:
            painter.setPen(active_pen if active else line_pen)
            painter.drawLine(pt(x1, y1), pt(x2, y2))

        def wire(points: list[tuple[float, float]], active: bool = False) -> None:
            for first, second in zip(points, points[1:]):
                line(first[0], first[1], second[0], second[1], active)

        def port(label: str, x: float, y: float, side: str = "bottom") -> None:
            active = label.upper() in highlighted
            painter.setPen(QPen(QColor("#000000"), max(1.0, scale)))
            painter.setBrush(QColor("#e11d25") if active else QColor("#22b8cf"))
            painter.drawRect(rect(x - 5, y - 5, 10, 10))
            painter.setBrush(Qt.NoBrush)
            painter.setFont(QFont("Microsoft YaHei UI", max(8, int(10 * scale)), QFont.Bold))
            text_rect = {
                "left": rect(x - 48, y - 12, 36, 22),
                "top": rect(x - 28, y - 32, 56, 22),
                "bottom": rect(x - 28, y + 10, 56, 22),
            }.get(side, rect(x + 10, y - 12, 48, 22))
            painter.drawText(text_rect, Qt.AlignCenter, label)

        def switch(label: str, x: float, y: float, active: bool = False) -> None:
            painter.setPen(active_pen if active else muted_pen)
            painter.setBrush(QColor("#ff4d4f") if active else QColor("#ffffff"))
            painter.drawRect(rect(x, y, 44, 36))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(line_pen)
            painter.setFont(QFont("Microsoft YaHei UI", max(8, int(10 * scale)), QFont.Bold))
            painter.drawText(rect(x - 4, y + 38, 52, 20), Qt.AlignCenter, label)
            line(x + 8, y + 12, x + 36, y + (14 if active else 26), active)
            line(x + 8, y + 26, x + 36, y + 12, False)

        def amp(label: str, x: float, y: float, color: str) -> None:
            active = label.upper() in highlighted
            painter.setPen(active_pen if active else line_pen)
            painter.setBrush(QColor(color))
            painter.drawPolygon(QPolygonF([pt(x, y), pt(x + 36, y), pt(x + 18, y + 48)]))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(line_pen)
            painter.setFont(QFont("Microsoft YaHei UI", max(8, int(10 * scale)), QFont.Bold))
            painter.drawText(rect(x - 12, y + 52, 60, 22), Qt.AlignCenter, label)

        port("H", 58, 112, "left")
        port("V", 58, 152, "left")
        port("DUT", 590, 52, "top")
        port("VNA1", 170, 362, "bottom")
        port("VNA2", 230, 362, "bottom")
        port("SG", 290, 362, "bottom")
        port("SA", 620, 362, "bottom")

        h_active = "H" in highlighted
        v_active = "V" in highlighted
        dut_active = "DUT" in highlighted
        vna1_active = "VNA1" in highlighted
        vna2_active = "VNA2" in highlighted
        sg_active = "SG" in highlighted
        sa_active = "SA" in highlighted
        amp1_active = "AMP1" in highlighted
        amp2_active = "AMP2" in highlighted

        wire([(58, 112), (126, 112)], h_active)
        wire([(58, 152), (126, 152)], v_active)
        switch("SW1", 126, 104, h_active or v_active)
        wire([(170, 122), (230, 122), (230, 156)], h_active or v_active)
        switch("SW2", 230, 100, False)
        wire([(274, 118), (380, 118), (380, 170)], amp1_active)
        amp("AMP1", 360, 170, "#f4a261")
        wire([(396, 194), (552, 194), (552, 154)], amp1_active or amp2_active)

        switch("SW3", 230, 238, False)
        wire([(252, 136), (252, 238)], False)
        wire([(274, 256), (320, 256), (320, 300)], False)

        switch("SW6", 150, 296, False)
        wire([(172, 332), (172, 362)], vna1_active)
        wire([(208, 332), (230, 332), (230, 362)], vna2_active)
        wire([(244, 332), (290, 332), (290, 362)], sg_active)
        wire([(194, 314), (552, 314)], vna1_active or vna2_active or sg_active)

        amp("AMP2", 572, 130, "#2ecc71")
        wire([(590, 52), (590, 130)], dut_active)
        switch("SW4", 572, 214, False)
        wire([(590, 178), (590, 214)], amp2_active or dut_active)
        wire([(590, 250), (590, 292)], False)
        switch("SW5", 572, 292, False)
        wire([(590, 328), (620, 328), (620, 362)], sa_active)
        wire([(552, 194), (590, 194), (590, 214)], amp1_active or amp2_active)
        wire([(320, 300), (572, 300)], False)

class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override.
        event.ignore()


class SwitchBoxControlPanel(QGroupBox):
    parameter_requested = Signal(str)
    command_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("开关箱控制", parent)
        self._view_model = LinkControlViewModel()
        self._busy = False
        self._connected = False

        self._parameter = NoWheelComboBox()
        self._parameter.addItems(["S21", "S11", "S12", "S22"])

        self._command = NoWheelComboBox()
        self._command.setEditable(True)
        self._command.addItems(DEFAULT_LINK_COMMANDS)
        self._diagram = SwitchBoxDiagramWidget()
        self._current_command = QLabel()
        self._current_command.setWordWrap(True)
        self._command.currentTextChanged.connect(self._set_current_command)

        self._last_result = QLabel("-")
        self._last_result.setWordWrap(True)

        self._route_button = QPushButton("按 S 参数切换")
        self._route_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self._route_button.clicked.connect(
            lambda: self.parameter_requested.emit(self._view_model.route_parameter(self._parameter.currentText()))
        )

        self._send_button = QPushButton("发送链路命令")
        self._send_button.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self._send_button.clicked.connect(
            lambda: self.command_requested.emit(self._view_model.send_command(self._command.currentText()))
        )

        self._input_widgets: list[QWidget] = [
            self._parameter,
            self._route_button,
            self._command,
            self._send_button,
        ]

        parameter_group = QGroupBox("快速切换")
        parameter_form = QFormLayout(parameter_group)
        parameter_form.addRow("S 参数", self._parameter)
        parameter_form.addRow("", self._route_button)

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
        layout.addWidget(parameter_group)
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
