from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from catr_loss_calibrator.calibration.definitions import default_calibration_catalog
from catr_loss_calibrator.calibration.mock_runner import MockCalibrationRunner
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna


def run() -> int:
    args = set(sys.argv[1:])
    if "--cli" in args:
        return run_cli()
    if "--interactive" in args:
        return run_interactive()
    try:
        return run_gui()
    except Exception as exc:
        print(f"GUI unavailable: {exc}")
        return run_cli()


def run_cli() -> int:
    catalog = default_calibration_catalog()
    print("CATR 路损校准操作台")
    print("Available calibration items:")
    for item in catalog.items:
        print(f"- {item.id}: {item.name} ({len(item.steps)} steps)")
    first_item = catalog.items[0]
    runner = MockCalibrationRunner(first_item, MockVna(), MockLinkBox(), Path("catr_loss_calibrator_output"))
    runner.link_box.connect()
    runner.vna.connect()
    print("Runner overview before run:")
    print(runner.overview())
    runner.run()
    print("Runner overview after run:")
    print(runner.overview())
    print(f"Mock runner state: {runner.state_machine.state.value}")
    print(f"Mock runner events: {len(runner.events)}")
    return 0


def run_interactive() -> int:
    catalog = default_calibration_catalog()
    print("CATR 路损校准操作台 - Interactive")
    for index, item in enumerate(catalog.items, start=1):
        print(f"{index}. {item.id}: {item.name}")
    selection = input("Select calibration item number: ").strip()
    try:
        item = catalog.items[int(selection) - 1]
    except Exception:
        print("Invalid selection.")
        return 1

    def confirm(step, step_index: int, total: int) -> str:
        print(runner.format_step_status(step, step_index, total))
        action = input("Continue / Skip / Retry / Cancel ? [c/s/r/x]: ").strip().lower()
        return {"c": "continue", "s": "skip", "r": "retry", "x": "cancel"}.get(action, "continue")

    runner = MockCalibrationRunner(item, MockVna(), MockLinkBox(), Path("catr_loss_calibrator_output"), confirm_step=confirm)
    runner.link_box.connect()
    runner.vna.connect()
    print("Runner overview before run:")
    print(runner.overview())
    runner.run()
    print("Runner overview after run:")
    print(runner.overview())
    print(f"State: {runner.state_machine.state.value}")
    print(f"Events: {len(runner.events)}")
    return 0


def run_gui() -> int:
    from catr_loss_calibrator.presentation.viewmodels import CalibrationViewModel

    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QAction, QFont, QPainter, QPixmap, QTextCursor
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QPlainTextEdit,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QSplitter,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication.instance() or QApplication(sys.argv)
    vm = CalibrationViewModel()
    base_dir = Path(__file__).resolve().parents[1]
    style_dir = base_dir / "style"

    def _load_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _svg_to_pixmap(
        path: Path,
        width: int = 88,
        height: int = 44,
        view_box: tuple[float, float, float, float] | None = None,
    ) -> QPixmap:
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)
        renderer = QSvgRenderer(str(path))
        if view_box is not None:
            renderer.setViewBox(QRectF(*view_box))
        painter = QPainter(pixmap)
        target = QRectF(0, 0, width, height)
        source = renderer.viewBoxF()
        if source.isValid() and source.width() > 0 and source.height() > 0:
            source_ratio = source.width() / source.height()
            target_ratio = width / height
            if target_ratio > source_ratio:
                target.setWidth(height * source_ratio)
                target.moveLeft((width - target.width()) / 2)
            else:
                target.setHeight(width / source_ratio)
                target.moveTop((height - target.height()) / 2)
        renderer.render(painter, target)
        painter.end()
        return pixmap

    class LogPanel(QWidget):
        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)

            self.toolbar = QToolBar()
            self.toolbar.setObjectName("logToolbar")
            self.toolbar.setMovable(False)

            self.level_combo = QComboBox()
            self.level_combo.addItems(["ALL", "INFO", "WARNING", "ERROR"])
            self.level_combo.setMinimumWidth(96)
            self.toolbar.addWidget(QLabel("级别:"))
            self.toolbar.addWidget(self.level_combo)

            self.font_combo = QComboBox()
            self.font_combo.addItems([str(size) for size in range(8, 16)])
            self.font_combo.setCurrentText("10")
            self.font_combo.setMaximumWidth(72)
            self.toolbar.addWidget(QLabel("字体:"))
            self.toolbar.addWidget(self.font_combo)

            self.wrap_action = QAction("自动换行", self)
            self.wrap_action.setCheckable(True)
            self.toolbar.addAction(self.wrap_action)

            self.timestamp_action = QAction("时间戳", self)
            self.timestamp_action.setCheckable(True)
            self.timestamp_action.setChecked(True)
            self.toolbar.addAction(self.timestamp_action)

            self.search_edit = QLineEdit()
            self.search_edit.setPlaceholderText("搜索...")
            self.search_edit.setMaximumWidth(220)
            self.toolbar.addWidget(self.search_edit)

            self.clear_filter_action = QAction("清空筛选", self)
            self.toolbar.addAction(self.clear_filter_action)

            self.text_edit = QTextEdit()
            self.text_edit.setObjectName("logText")
            self.text_edit.setReadOnly(True)
            self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
            self.text_edit.setFont(QFont("Consolas", 10))

            self.font_combo.currentTextChanged.connect(self._apply_font_size)
            self.wrap_action.toggled.connect(self._set_word_wrap)

            layout.addWidget(self.toolbar)
            layout.addWidget(self.text_edit)

        def current_level(self) -> str:
            return self.level_combo.currentText()

        def current_keyword(self) -> str:
            return self.search_edit.text()

        def show_timestamp(self) -> bool:
            return self.timestamp_action.isChecked()

        def clear_filters(self) -> None:
            self.level_combo.setCurrentText("ALL")
            self.search_edit.clear()

        def set_records(self, records: list[LogEntry], formatter: Any) -> None:
            self.text_edit.setPlainText("\n".join(formatter(record, self.show_timestamp()) for record in records))
            self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

        def _apply_font_size(self, value: str) -> None:
            try:
                size = int(value)
            except ValueError:
                return
            self.text_edit.setFont(QFont("Consolas", size))

        def _set_word_wrap(self, enabled: bool) -> None:
            mode = QTextEdit.LineWrapMode.WidgetWidth if enabled else QTextEdit.LineWrapMode.NoWrap
            self.text_edit.setLineWrapMode(mode)

    class DeviceCommandPanel(QGroupBox):
        def __init__(self, device_key: str, title: str, presets: dict[str, str], parent: QWidget | None = None) -> None:
            super().__init__(title, parent)
            self.device_key = device_key
            self.presets = presets

            layout = QVBoxLayout(self)
            self.preset_combo = QComboBox()
            self.preset_combo.addItems(list(presets.keys()))
            self.command_input = QLineEdit()
            self.command_input.setPlaceholderText("输入 SCPI / 控制命令")
            self.response_view = QPlainTextEdit()
            self.response_view.setReadOnly(True)
            self.response_view.setMaximumHeight(120)
            self.response_view.setPlaceholderText("响应")
            self.btn_preset = QPushButton("填充预设")
            self.btn_send = QPushButton("发送命令")

            buttons = QHBoxLayout()
            buttons.addWidget(self.btn_preset)
            buttons.addWidget(self.btn_send)

            layout.addWidget(QLabel("预设"))
            layout.addWidget(self.preset_combo)
            layout.addWidget(QLabel("命令"))
            layout.addWidget(self.command_input)
            layout.addLayout(buttons)
            layout.addWidget(QLabel("当前响应"))
            layout.addWidget(self.response_view)

        def selected_command(self) -> str:
            return self.presets[self.preset_combo.currentText()]

        def command_text(self) -> str:
            return self.command_input.text()

        def set_response(self, response: str) -> None:
            self.response_view.setPlainText(response)

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("CATR 路损校准操作台")
            self.resize(1400, 900)

            self.item_list = QListWidget()
            self.item_list.setMinimumWidth(260)
            for item in vm.catalog.items:
                QListWidgetItem(f"{item.id}\n{item.name}", self.item_list)
            self.step_list = QListWidget()
            self.step_list.setMinimumWidth(260)

            self.item_summary = QLabel()
            self.item_summary.setWordWrap(True)

            self.logo_badge = QLabel()
            self.logo_badge.setFixedSize(56, 44)
            self.logo_badge.setPixmap(
                _svg_to_pixmap(
                    style_dir / "LOGO2 NO Words.svg",
                    width=56,
                    height=44,
                    view_box=(4600, 6750, 3100, 3400),
                )
            )
            self.logo_title = QLabel("CATR 路损校准操作台")
            self.logo_title.setObjectName("appTitle")
            self.logo_title.setStyleSheet("font-size: 26px; font-weight: 800; color: #102033;")

            self.step_title = QLabel("未开始")
            self.step_title.setStyleSheet("font-size: 18px; font-weight: 600;")
            self.step_status = QLabel("状态：IDLE")
            self.step_progress = QProgressBar()
            self.step_progress.setRange(0, 100)

            self.path_view = QPlainTextEdit()
            self.path_view.setReadOnly(True)
            self.path_view.setMaximumBlockCount(200)
            self.path_view.setPlaceholderText("接线路径将显示在这里")

            self.command_view = QPlainTextEdit()
            self.command_view.setReadOnly(True)
            self.command_view.setMaximumBlockCount(200)

            self.detail_view = QPlainTextEdit()
            self.detail_view.setReadOnly(True)
            self.detail_view.setMaximumBlockCount(200)

            self.calibration_log_panel = LogPanel()
            self.full_log_panel = LogPanel()
            self.log_panels = [self.calibration_log_panel, self.full_log_panel]

            self.result_view = QPlainTextEdit()
            self.result_view.setReadOnly(True)
            self.result_view.setMaximumHeight(180)
            self.result_view.setPlaceholderText("结果文件与状态详情")
            self.result_summary = QPlainTextEdit()
            self.result_summary.setReadOnly(True)
            self.result_summary.setMaximumHeight(92)
            self.result_summary.setPlaceholderText("运行摘要将在这里显示")
            self.result_session = QPlainTextEdit()
            self.result_session.setReadOnly(True)
            self.result_session.setMaximumHeight(150)
            self.result_session.setPlaceholderText("会话与运行记录")

            self.history_view = QPlainTextEdit()
            self.history_view.setReadOnly(True)
            self.history_view.setPlaceholderText("四类设备的命令历史")

            command_presets = vm.device_command_presets()
            self.command_panels = [
                DeviceCommandPanel("vna", "网分", command_presets["vna"]),
                DeviceCommandPanel("signal_generator", "信号源", command_presets["signal_generator"]),
                DeviceCommandPanel("link_box", "链路箱", command_presets["link_box"]),
                DeviceCommandPanel("spectrum_analyzer", "频谱仪", command_presets["spectrum_analyzer"]),
            ]

            self.status_label = QLabel("Ready")
            self.connection_label = QLabel("VNA: disconnected | SG: disconnected | LinkBox: disconnected | SA: disconnected")

            self.btn_connect = QPushButton("连接 Mock 设备")
            self.btn_disconnect = QPushButton("断开 Mock 设备")
            self.btn_start = QPushButton("开始校准")
            self.btn_continue = QPushButton("下一步")
            self.btn_skip = QPushButton("跳过")
            self.btn_retry = QPushButton("重试")
            self.btn_cancel = QPushButton("取消")

            self.btn_refresh = QPushButton("刷新结果")

            self.tabs = QTabWidget()
            self.calibration_page = self._build_calibration_page()
            self.command_page = self._build_command_page()
            self.log_page = self._build_log_page()
            self.result_page = self._build_result_page()
            self.tabs.addTab(self.calibration_page, "校准执行")
            self.tabs.addTab(self.command_page, "指令测试")
            self.tabs.addTab(self.log_page, "日志")
            self.tabs.addTab(self.result_page, "结果")

            root = QWidget()
            self.setCentralWidget(root)
            root_layout = QVBoxLayout(root)
            root_layout.addWidget(self._build_header())
            root_layout.addWidget(self.tabs)

            self.statusBar().addWidget(self.status_label, 1)
            self.statusBar().addPermanentWidget(self.connection_label)

            self._bind_events()
            self._refresh_item_list()
            vm.connect_mock_devices()
            self.item_list.setCurrentRow(0)
            vm.refresh_overview()
            self._sync_overview()

        def _build_header(self) -> QWidget:
            box = QFrame()
            box.setObjectName("headerBanner")
            box.setObjectName("appHeader")
            box.setMinimumHeight(72)
            layout = QHBoxLayout(box)
            left = QVBoxLayout()
            title_row = QHBoxLayout()
            title_row.addWidget(self.logo_badge)
            title_row.addWidget(self.logo_title)
            title_row.addStretch(1)
            left.addLayout(title_row)
            layout.addLayout(left, 1)
            meta = QVBoxLayout()
            self.project_label = QLabel("项目：CATR 路损校准")
            self.version_label = QLabel("版本：0.1.0")
            self.connection_hint = QLabel("状态区会显示连接、步骤和运行摘要。")
            meta.addWidget(self.project_label)
            meta.addWidget(self.version_label)
            meta.addWidget(self.connection_hint)
            layout.addLayout(meta)
            return box

        def _build_calibration_page(self) -> QWidget:
            page = QWidget()
            layout = QHBoxLayout(page)

            left = QGroupBox("校准项")
            left_layout = QVBoxLayout(left)
            left_layout.addWidget(self.item_list)
            left_layout.addWidget(QLabel("步骤列表"))
            left_layout.addWidget(self.step_list)
            left_layout.addWidget(self.item_summary)
            left_layout.addWidget(self.btn_connect)
            left_layout.addWidget(self.btn_disconnect)

            center = QGroupBox("步骤执行")
            center_layout = QVBoxLayout(center)
            center_layout.addWidget(self.step_title)
            center_layout.addWidget(self.step_status)
            center_layout.addWidget(self.step_progress)
            self.step_hint = QLabel("选择左侧步骤以查看对应接线与命令。")
            self.step_hint.setStyleSheet("color: #64748B;")
            center_layout.addWidget(self.step_hint)
            center_layout.addWidget(QLabel("接线路径"))
            center_layout.addWidget(self.path_view)
            center_layout.addWidget(QLabel("命令 / 说明"))
            center_layout.addWidget(self.command_view)
            center_layout.addWidget(QLabel("步骤详情"))
            center_layout.addWidget(self.detail_view)

            button_row = QHBoxLayout()
            button_row.addWidget(self.btn_start)
            button_row.addWidget(self.btn_continue)
            button_row.addWidget(self.btn_skip)
            button_row.addWidget(self.btn_retry)
            button_row.addWidget(self.btn_cancel)
            center_layout.addLayout(button_row)

            right_tabs = QTabWidget()
            right_log = QWidget()
            right_log_layout = QVBoxLayout(right_log)
            right_log_layout.addWidget(self.calibration_log_panel)
            right_tabs.addTab(right_log, "日志")

            right_result = QWidget()
            right_result_layout = QVBoxLayout(right_result)
            right_result_layout.addWidget(QLabel("运行摘要"))
            right_result_layout.addWidget(self.result_summary)
            right_result_layout.addWidget(QLabel("文件与状态"))
            right_result_layout.addWidget(self.result_view)
            right_result_layout.addWidget(QLabel("会话记录"))
            right_result_layout.addWidget(self.result_session)
            right_tabs.addTab(right_result, "结果")

            splitter = QSplitter(Qt.Horizontal)
            splitter.addWidget(left)
            splitter.addWidget(center)
            splitter.addWidget(right_tabs)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 3)
            splitter.setStretchFactor(2, 2)
            layout.addWidget(splitter)
            return page

        def _build_command_page(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)

            device_grid = QGridLayout()
            for column, panel in enumerate(self.command_panels):
                device_grid.addWidget(panel, 0, column)

            layout.addLayout(device_grid)
            layout.addWidget(QLabel("历史命令"))
            layout.addWidget(self.history_view)
            layout.addWidget(self.btn_refresh)
            return page

        def _build_log_page(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.addWidget(self.full_log_panel)
            return page

        def _build_result_page(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.addWidget(QLabel("运行摘要"))
            layout.addWidget(self.result_summary)
            layout.addWidget(QLabel("最终输出与会话结果"))
            layout.addWidget(self.result_view)
            layout.addWidget(QLabel("会话记录"))
            layout.addWidget(self.result_session)
            return page

        def _bind_events(self) -> None:
            self.item_list.currentRowChanged.connect(vm.select_item)
            self.step_list.currentRowChanged.connect(vm.select_step)
            self.btn_connect.clicked.connect(self._connect_devices)
            self.btn_disconnect.clicked.connect(self._disconnect_devices)
            self.btn_start.clicked.connect(vm.start_selected)
            self.btn_continue.clicked.connect(lambda: vm.submit_action("continue"))
            self.btn_skip.clicked.connect(lambda: vm.submit_action("skip"))
            self.btn_retry.clicked.connect(lambda: vm.submit_action("retry"))
            self.btn_cancel.clicked.connect(lambda: vm.submit_action("cancel"))
            self.btn_refresh.clicked.connect(self._sync_overview)
            for panel in self.command_panels:
                panel.btn_preset.clicked.connect(lambda _checked=False, command_panel=panel: self._fill_preset(command_panel))
                panel.btn_send.clicked.connect(lambda _checked=False, command_panel=panel: self._send_command(command_panel))
                panel.command_input.returnPressed.connect(lambda command_panel=panel: self._send_command(command_panel))
            for panel in self.log_panels:
                panel.level_combo.currentTextChanged.connect(self._sync_logs)
                panel.search_edit.textChanged.connect(self._sync_logs)
                panel.timestamp_action.toggled.connect(self._sync_logs)
                panel.clear_filter_action.triggered.connect(lambda _checked=False, log_panel=panel: self._clear_log_filters(log_panel))

            vm.selected_item_changed.connect(self._sync_item_detail)
            vm.selected_step_changed.connect(self._sync_step_list)
            vm.step_view_changed.connect(self._sync_step_view)
            vm.logs_changed.connect(self._sync_logs)
            vm.status_changed.connect(self.status_label.setText)
            vm.overview_changed.connect(self._sync_overview)
            vm.run_state_changed.connect(self._on_state_changed)
            vm.command_response_changed.connect(self._sync_command_response)

        def _refresh_item_list(self) -> None:
            self.item_list.blockSignals(True)
            self.item_list.setCurrentRow(0)
            self.item_list.blockSignals(False)
            self._sync_item_detail()

        def _sync_item_detail(self) -> None:
            item = vm.selected_item
            self.item_summary.setText(
                f"ID: {item.id}\n"
                f"名称: {item.name}\n"
                f"步骤数: {len(item.steps)}\n"
                f"用途: {item.purpose}"
            )
            self._sync_step_list()
            self._sync_overview()

        def _sync_step_list(self) -> None:
            item = vm.selected_item
            self.step_list.blockSignals(True)
            self.step_list.clear()
            completed_count = 0
            run_summary = vm.overview.get("run_summary") if isinstance(vm.overview.get("run_summary"), dict) else {}
            if isinstance(run_summary, dict):
                completed_count = int(run_summary.get("completed_steps", 0) or 0)
            for index, step in enumerate(item.steps, start=1):
                if index <= completed_count:
                    prefix = "✓ 已完成"
                elif index == vm.selected_step_index + 1:
                    prefix = "▶ 当前"
                else:
                    prefix = "○ 未开始"
                QListWidgetItem(f"{prefix}\n{index}. {step.id}\n{step.name}", self.step_list)
            if item.steps:
                self.step_list.setCurrentRow(vm.selected_step_index)
            self.step_list.blockSignals(False)
            current_step = vm.selected_step
            if current_step:
                self._sync_step_view(
                    vm._step_view_data(current_step, vm.selected_step_index + 1, len(item.steps))
                )
                self.step_hint.setText(f"当前步骤：{current_step.id} · {current_step.name}")
            else:
                self.step_hint.setText("当前校准项暂无步骤。")

        def _sync_step_view(self, step: StepViewData) -> None:
            self.step_title.setText(f"[{step.step_index}/{step.step_total}] {step.step_id} - {step.step_name}")
            self.step_status.setText(f"状态：{step.status}")
            progress = int(step.step_index / max(step.step_total, 1) * 100)
            self.step_progress.setValue(progress)
            self.path_view.setPlainText(
                step.manual_instruction
                + ("\n\nRoute IDs: " + ", ".join(step.route_ids) if step.route_ids else "")
            )
            self.command_view.setPlainText("\n".join(step.link_commands) or "无链路命令")
            self.detail_view.setPlainText(
                f"输入端口: {step.input_port}\n"
                f"输出端口: {step.output_port}\n"
                f"原始输出: {', '.join(step.raw_outputs) or '无'}\n"
                f"最终输出: {', '.join(step.final_outputs) or '无'}\n"
                f"所需输入: {', '.join(step.required_inputs) or '无'}\n"
                f"备注: {step.notes or '无'}"
            )

        def _sync_logs(self, *_args: Any) -> None:
            for panel in self.log_panels:
                records = vm.filtered_logs(level=panel.current_level(), keyword=panel.current_keyword())
                panel.set_records(records, self._format_log_entry)
            self.history_view.setPlainText("\n".join(vm.command_history))

        def _sync_overview(self, *_args: Any) -> None:
            overview = vm.overview
            if not overview:
                return
            self.result_summary.setPlainText(self._format_overview_summary(overview))
            self.result_view.setPlainText(self._format_overview_detail(overview))
            self.result_session.setPlainText(self._format_session_detail(overview))
            link_box = "connected" if overview.get("link_box_connected") else "disconnected"
            vna = "connected" if overview.get("vna_connected") else "disconnected"
            sg = "connected" if overview.get("signal_generator_connected") else "disconnected"
            sa = "connected" if overview.get("spectrum_analyzer_connected") else "disconnected"
            self.connection_label.setText(f"VNA: {vna} | SG: {sg} | LinkBox: {link_box} | SA: {sa}")
            self.status_label.setText(str(overview.get("status", "Ready")))

        def _on_state_changed(self, state: str) -> None:
            self.step_status.setText(f"状态：{state}")

        def _sync_command_response(self, response: str) -> None:
            self.status_label.setText(f"命令响应: {response}")

        def _clear_log_filters(self, panel: LogPanel) -> None:
            panel.clear_filters()
            self._sync_logs()

        def _fill_preset(self, panel: DeviceCommandPanel) -> None:
            panel.command_input.setText(panel.selected_command())

        def _send_command(self, panel: DeviceCommandPanel) -> None:
            try:
                response = vm.send_device_command(panel.device_key, panel.command_text())
            except Exception as exc:
                QMessageBox.warning(self, "命令发送失败", str(exc))
                return
            panel.set_response(response)
            self.history_view.setPlainText("\n\n".join(vm.command_history))

        def _connect_devices(self) -> None:
            vm.connect_mock_devices()

        def _disconnect_devices(self) -> None:
            vm.disconnect_mock_devices()

        def _format_log_entry(self, record: LogEntry, show_timestamp: bool = True) -> str:
            prefix = f"{record.timestamp} " if show_timestamp else ""
            return f"{prefix}[{record.level}] {record.source}/{record.name} - {record.message}"

        def _format_overview_summary(self, overview: dict[str, Any]) -> str:
            run_summary = overview.get("run_summary") or {}
            lines = [
                f"项目: {overview.get('item_name', '')}",
                f"当前步骤: {overview.get('selected_step_id', '')}",
                f"状态: {overview.get('status', '')}",
                f"校准步数: {overview.get('steps', '')}",
                f"连接: {'OK' if self._all_command_devices_connected(overview) else '待连接'}",
                f"已完成步骤: {run_summary.get('completed_steps', 0) if isinstance(run_summary, dict) else 0}",
                f"最后事件: {run_summary.get('last_event', '') if isinstance(run_summary, dict) else ''}",
            ]
            return "\n".join(lines)

        def _format_overview_detail(self, overview: dict[str, Any]) -> str:
            run_summary = overview.get("run_summary") or {}
            lines = [
                f"item_id: {overview.get('item_id', '')}",
                f"purpose: {overview.get('purpose', '')}",
                f"link_box_connected: {overview.get('link_box_connected', False)}",
                f"vna_connected: {overview.get('vna_connected', False)}",
                f"signal_generator_connected: {overview.get('signal_generator_connected', False)}",
                f"spectrum_analyzer_connected: {overview.get('spectrum_analyzer_connected', False)}",
                f"selected_step_id: {overview.get('selected_step_id', '')}",
            ]
            if isinstance(run_summary, dict) and run_summary:
                lines.append("")
                lines.append("run_summary:")
                for key, value in run_summary.items():
                    lines.append(f"  {key}: {value}")
            return "\n".join(lines)

        def _format_session_detail(self, overview: dict[str, Any]) -> str:
            run_summary = overview.get("run_summary") or {}
            lines = [
                f"session_status: {overview.get('status', '')}",
                f"selected_item: {overview.get('item_name', '')}",
                f"step_count: {overview.get('steps', '')}",
                f"selected_step_id: {overview.get('selected_step_id', '')}",
            ]
            if isinstance(run_summary, dict) and run_summary:
                lines.append(f"completed_steps: {run_summary.get('completed_steps', '')}")
                lines.append(f"last_event: {run_summary.get('last_event', '')}")
                lines.append(f"link_box_connected: {run_summary.get('link_box_connected', '')}")
                lines.append(f"vna_connected: {run_summary.get('vna_connected', '')}")
            return "\n".join(lines)

        def _all_command_devices_connected(self, overview: dict[str, Any]) -> bool:
            return bool(
                overview.get("vna_connected")
                and overview.get("signal_generator_connected")
                and overview.get("link_box_connected")
                and overview.get("spectrum_analyzer_connected")
            )

    app.setStyleSheet(
        """
        """
    )
    style_text = _load_text(style_dir / "style.css")
    style_text = style_text.replace('image: url("__COMBOBOX_ARROW_ICON__");', f'image: url("{(style_dir / "chevron-down.svg").as_posix()}");')
    style_text = style_text.replace('image: url("__SPINBOX_UP_ICON__");', f'image: url("{(style_dir / "chevron-up-small.svg").as_posix()}");')
    style_text = style_text.replace('image: url("__SPINBOX_DOWN_ICON__");', f'image: url("{(style_dir / "chevron-down-small.svg").as_posix()}");')
    app.setStyleSheet(style_text)

    window = MainWindow()
    window.show()
    return app.exec()
