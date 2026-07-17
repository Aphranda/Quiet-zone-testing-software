from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lcd_link.controller import InstrumentInfo, Lcd74000fSwitchBoxConfig, Lcd74000fSwitchBoxController
from lcd_link.routing import DEFAULT_LINK_COMMANDS


@dataclass(frozen=True)
class LinkDiagramState:
    selected_command: str
    highlighted_tokens: frozenset[str]


class LinkControlViewModel:
    def link_commands(self) -> tuple[str, ...]:
        return DEFAULT_LINK_COMMANDS

    def selected_command(self, command: str) -> str:
        command = str(command).strip()
        return command or DEFAULT_LINK_COMMANDS[0]

    def current_command_text(self, command: str) -> str:
        return f"当前命令：{self.selected_command(command)}"

    def diagram_state(self, command: str) -> LinkDiagramState:
        selected_command = self.selected_command(command)
        command_upper = selected_command.upper()
        return LinkDiagramState(
            selected_command=selected_command,
            highlighted_tokens=frozenset(
                token
                for token in ("DUT", "H", "V", "VNA1", "VNA2", "SG", "SA", "AMP1", "AMP2")
                if token in command_upper
            ),
        )


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class OperationWorker(QRunnable):
    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.result.emit(self.operation())
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class LinkDiagramWidget(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_pixmap = QPixmap(str(files("lcd_link.resources").joinpath("link_diagram.png")))
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: #ffffff; border: 1px solid #d6dbe1;")
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
        scaled = self._source_pixmap.scaled(
            self.size() * self.devicePixelRatioF(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(self.devicePixelRatioF())
        self.setPixmap(scaled)


class LcdLinkControlWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LCD74000F 链路箱独立控制")
        self._view_model = LinkControlViewModel()
        self._thread_pool = QThreadPool.globalInstance()
        self._controller: Lcd74000fSwitchBoxController | None = None
        self._connected = False
        self._busy = False

        self._connection_type = QComboBox()
        self._connection_type.addItems(["TCP/IP", "Serial"])
        self._ip_address = QLineEdit("192.168.1.113")
        self._tcp_port = QSpinBox()
        self._tcp_port.setRange(1, 65535)
        self._tcp_port.setValue(7)
        self._serial_port = QLineEdit("COM3")
        self._baudrate = QSpinBox()
        self._baudrate.setRange(1200, 921600)
        self._baudrate.setValue(115200)
        self._timeout_ms = QSpinBox()
        self._timeout_ms.setRange(100, 60000)
        self._timeout_ms.setValue(2000)

        self._connect_button = QPushButton("连接")
        self._disconnect_button = QPushButton("断开")
        self._disconnect_button.setEnabled(False)
        self._connect_button.clicked.connect(self._connect)
        self._disconnect_button.clicked.connect(self._disconnect)

        self._command = QComboBox()
        self._command.setEditable(True)
        self._command.addItems(self._view_model.link_commands())
        self._current_command = QLabel()
        self._current_command.setWordWrap(True)
        self._command.currentTextChanged.connect(self._set_current_command)
        self._send_button = QPushButton("发送链路命令")
        self._send_button.setEnabled(False)
        self._send_button.clicked.connect(self._send_command)

        self._query_command = QComboBox()
        self._query_command.setEditable(True)
        self._query_command.addItems(["READ:LINK:STATe?", "*IDN?", "SYSTem:ERRor:COUNt?", "SYSTem:ERRor:NEXT?"])
        self._query_button = QPushButton("查询")
        self._query_button.setEnabled(False)
        self._query_button.clicked.connect(self._query)

        self._diagram = LinkDiagramWidget()
        self._result = QTextEdit()
        self._result.setReadOnly(True)
        self._result.setMinimumHeight(130)

        self._build_layout()
        self.setStatusBar(QStatusBar())
        self._connection_type.currentTextChanged.connect(self._refresh_connection_fields)
        self._refresh_connection_fields()
        self._set_current_command(self._command.currentText())
        self._refresh_enabled_state()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override.
        if self._controller is not None and self._controller.is_connected:
            self._controller.disconnect()
        super().closeEvent(event)

    def _build_layout(self) -> None:
        connection_group = QGroupBox("连接")
        connection_form = QFormLayout(connection_group)
        connection_form.addRow("连接方式", self._connection_type)
        connection_form.addRow("IP 地址", self._ip_address)
        connection_form.addRow("TCP 端口", self._tcp_port)
        connection_form.addRow("串口", self._serial_port)
        connection_form.addRow("波特率", self._baudrate)
        connection_form.addRow("超时 ms", self._timeout_ms)
        buttons = QHBoxLayout()
        buttons.addWidget(self._connect_button)
        buttons.addWidget(self._disconnect_button)
        connection_form.addRow("", buttons)

        command_group = QGroupBox("链路命令")
        command_form = QFormLayout(command_group)
        command_form.addRow("命令", self._command)
        command_form.addRow("", self._send_button)

        query_group = QGroupBox("查询")
        query_form = QFormLayout(query_group)
        query_form.addRow("命令", self._query_command)
        query_form.addRow("", self._query_button)

        result_group = QGroupBox("执行结果")
        result_layout = QVBoxLayout(result_group)
        result_layout.addWidget(self._result)

        side = QVBoxLayout()
        side.addWidget(connection_group)
        side.addWidget(command_group)
        side.addWidget(query_group)
        side.addWidget(result_group)
        side.addStretch(1)

        main = QHBoxLayout()
        main.addWidget(self._diagram, 1)
        side_widget = QWidget()
        side_widget.setLayout(side)
        side_widget.setMinimumWidth(340)
        side_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        main.addWidget(side_widget)

        root = QVBoxLayout()
        root.addLayout(main)
        root.addWidget(self._current_command)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

    def _connect(self) -> None:
        config = self._config_from_fields()
        controller = Lcd74000fSwitchBoxController(config)
        self._controller = controller

        def operation() -> InstrumentInfo:
            return controller.connect()

        self._run_operation(operation, self._on_connected, "连接失败")

    def _disconnect(self) -> None:
        controller = self._controller
        if controller is None:
            return

        def operation() -> str:
            controller.disconnect()
            return "已断开"

        self._run_operation(operation, self._on_disconnected, "断开失败")

    def _send_command(self) -> None:
        controller = self._controller
        if controller is None:
            return
        command = self._view_model.selected_command(self._command.currentText())

        def operation() -> str:
            return controller.send_command(command)

        self._run_operation(operation, lambda response: self._append_result(f"发送成功：{response}"), "发送失败")

    def _query(self) -> None:
        controller = self._controller
        if controller is None:
            return
        command = str(self._query_command.currentText()).strip()
        if not command:
            QMessageBox.warning(self, "查询命令为空", "请输入查询命令。")
            return

        def operation() -> str:
            return controller.query_command(command)

        self._run_operation(operation, lambda response: self._append_result(f"{command} -> {response}"), "查询失败")

    def _run_operation(self, operation: Callable[[], object], on_result: Callable[[object], None], error_title: str) -> None:
        self._set_busy(True)
        worker = OperationWorker(operation)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(lambda message: self._show_error(error_title, message))
        worker.signals.finished.connect(lambda: self._set_busy(False))
        self._thread_pool.start(worker)

    def _on_connected(self, info: object) -> None:
        self._connected = True
        self._append_result(f"连接成功：{info}")
        self.statusBar().showMessage("LCD74000F 已连接")
        self._refresh_enabled_state()

    def _on_disconnected(self, message: object) -> None:
        self._connected = False
        self._append_result(str(message))
        self.statusBar().showMessage("LCD74000F 已断开")
        self._refresh_enabled_state()

    def _show_error(self, title: str, message: str) -> None:
        self._append_result(f"{title}：{message}")
        QMessageBox.critical(self, title, message)

    def _append_result(self, message: str) -> None:
        self._result.append(str(message))

    def _set_current_command(self, command: str) -> None:
        state = self._view_model.diagram_state(command)
        self._diagram.set_link_state(
            selected_command=state.selected_command,
            highlighted_tokens=state.highlighted_tokens,
        )
        self._current_command.setText(self._view_model.current_command_text(state.selected_command))

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh_enabled_state()

    def _refresh_enabled_state(self) -> None:
        can_use_link = self._connected and not self._busy
        can_connect = not self._connected and not self._busy
        self._connect_button.setEnabled(can_connect)
        self._disconnect_button.setEnabled(can_use_link)
        self._send_button.setEnabled(can_use_link)
        self._query_button.setEnabled(can_use_link)
        for widget in (
            self._connection_type,
            self._ip_address,
            self._tcp_port,
            self._serial_port,
            self._baudrate,
            self._timeout_ms,
        ):
            widget.setEnabled(can_connect)

    def _refresh_connection_fields(self) -> None:
        is_serial = self._connection_type.currentText().strip().upper() == "SERIAL"
        self._ip_address.setVisible(not is_serial)
        self._tcp_port.setVisible(not is_serial)
        self._serial_port.setVisible(is_serial)
        self._baudrate.setVisible(is_serial)

    def _config_from_fields(self) -> Lcd74000fSwitchBoxConfig:
        return Lcd74000fSwitchBoxConfig(
            connection_type=self._connection_type.currentText(),
            ip_address=self._ip_address.text().strip(),
            tcp_port=self._tcp_port.value(),
            serial_port=self._serial_port.text().strip(),
            baudrate=self._baudrate.value(),
            timeout_ms=self._timeout_ms.value(),
        )
