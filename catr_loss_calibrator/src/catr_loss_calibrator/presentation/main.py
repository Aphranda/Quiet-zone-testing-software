from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from catr_loss_calibrator.calibration.definitions import default_calibration_catalog
from catr_loss_calibrator.calibration.mock_runner import MockCalibrationRunner
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna
from catr_loss_calibrator.presentation.viewmodels import CalibrationViewModel, LogEntry, StepViewData


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
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFormLayout,
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

    def _svg_to_pixmap(path: Path, width: int = 88, height: int = 44) -> QPixmap:
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)
        renderer = QSvgRenderer(str(path))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return pixmap

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
            self.logo_badge.setFixedSize(88, 44)
            self.logo_badge.setPixmap(_svg_to_pixmap(style_dir / "LOGO2 NO Words.svg"))
            self.logo_badge.setScaledContents(True)
            self.logo_title = QLabel("CATR 路损校准操作台")
            self.logo_title.setObjectName("appTitle")
            self.logo_title.setStyleSheet("font-size: 26px; font-weight: 800; color: #102033;")
            self.logo_subtitle = QLabel("工业化校准操作台 · PySide6 / MVVM")
            self.logo_subtitle.setStyleSheet("color: #64748B; font-size: 13px;")

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

            self.log_view = QPlainTextEdit()
            self.log_view.setReadOnly(True)
            self.log_view.setMaximumBlockCount(500)
            self.log_level_filter = QComboBox()
            self.log_level_filter.addItems(["ALL", "INFO", "WARNING", "ERROR"])
            self.log_keyword_filter = QLineEdit()
            self.log_keyword_filter.setPlaceholderText("筛选日志关键字")
            self.log_clear_button = QPushButton("清空筛选")

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

            self.command_input = QLineEdit()
            self.command_input.setPlaceholderText("输入 CONFigure:LINK ... 命令")
            self.route_selector = QComboBox()
            self.route_selector.addItems(
                [
                    "H_TO_VNA1",
                    "V_TO_VNA1",
                    "DUT_TO_VNA2",
                    "DUT_AMP1_VNA2",
                    "DUT_TO_SA",
                    "HV_AMP2_SA",
                ]
            )

            self.response_view = QPlainTextEdit()
            self.response_view.setReadOnly(True)
            self.history_view = QPlainTextEdit()
            self.history_view.setReadOnly(True)

            self.status_label = QLabel("Ready")
            self.connection_label = QLabel("LinkBox: disconnected | VNA: disconnected")

            self.btn_connect = QPushButton("连接 Mock 设备")
            self.btn_disconnect = QPushButton("断开 Mock 设备")
            self.btn_start = QPushButton("开始校准")
            self.btn_continue = QPushButton("下一步")
            self.btn_skip = QPushButton("跳过")
            self.btn_retry = QPushButton("重试")
            self.btn_cancel = QPushButton("取消")

            self.btn_send = QPushButton("发送命令")
            self.btn_preset = QPushButton("填充预设")
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
            box.setMinimumHeight(100)
            layout = QHBoxLayout(box)
            left = QVBoxLayout()
            title_row = QHBoxLayout()
            title_row.addWidget(self.logo_badge)
            title_row.addWidget(self.logo_title)
            title_row.addStretch(1)
            left.addLayout(title_row)
            left.addWidget(self.logo_subtitle)
            hint = QLabel("建议先连接 Mock 设备，再选择校准项。")
            hint.setStyleSheet("color: #6b7280;")
            left.addWidget(hint)
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
            log_filter_row = QHBoxLayout()
            log_filter_row.addWidget(QLabel("级别"))
            log_filter_row.addWidget(self.log_level_filter)
            log_filter_row.addWidget(QLabel("关键字"))
            log_filter_row.addWidget(self.log_keyword_filter)
            log_filter_row.addWidget(self.log_clear_button)
            right_log_layout.addLayout(log_filter_row)
            right_log_layout.addWidget(self.log_view)
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

            form = QGroupBox("命令台")
            form_layout = QFormLayout(form)
            form_layout.addRow("route_id", self.route_selector)
            form_layout.addRow("命令", self.command_input)
            cmd_buttons = QHBoxLayout()
            cmd_buttons.addWidget(self.btn_preset)
            cmd_buttons.addWidget(self.btn_send)
            form_layout.addRow(cmd_buttons)

            layout.addWidget(form)
            layout.addWidget(QLabel("当前响应"))
            layout.addWidget(self.response_view)
            layout.addWidget(QLabel("历史命令"))
            layout.addWidget(self.history_view)
            layout.addWidget(self.btn_refresh)
            return page

        def _build_log_page(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            filter_row = QHBoxLayout()
            filter_row.addWidget(QLabel("级别"))
            filter_row.addWidget(self.log_level_filter)
            filter_row.addWidget(QLabel("关键字"))
            filter_row.addWidget(self.log_keyword_filter)
            filter_row.addWidget(self.log_clear_button)
            layout.addLayout(filter_row)
            layout.addWidget(self.log_view)
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
            self.btn_send.clicked.connect(self._send_command)
            self.btn_preset.clicked.connect(self._fill_preset)
            self.btn_refresh.clicked.connect(self._sync_overview)
            self.log_level_filter.currentTextChanged.connect(self._sync_logs)
            self.log_keyword_filter.textChanged.connect(self._sync_logs)
            self.log_clear_button.clicked.connect(self._clear_log_filters)

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
            level = self.log_level_filter.currentText()
            keyword = self.log_keyword_filter.text()
            records = vm.filtered_logs(level=level, keyword=keyword)
            self.log_view.setPlainText("\n".join(self._format_log_entry(record) for record in records))
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
            self.connection_label.setText(f"LinkBox: {link_box} | VNA: {vna}")
            self.status_label.setText(str(overview.get("status", "Ready")))

        def _on_state_changed(self, state: str) -> None:
            self.step_status.setText(f"状态：{state}")

        def _sync_command_response(self, response: str) -> None:
            self.response_view.setPlainText(response)

        def _clear_log_filters(self) -> None:
            self.log_level_filter.setCurrentText("ALL")
            self.log_keyword_filter.clear()
            self._sync_logs()

        def _fill_preset(self) -> None:
            try:
                command = vm.preset_command(self.route_selector.currentText())
            except Exception as exc:
                QMessageBox.warning(self, "预设命令失败", str(exc))
                return
            self.command_input.setText(command)

        def _send_command(self) -> None:
            try:
                response = vm.send_command(self.command_input.text())
            except Exception as exc:
                QMessageBox.warning(self, "命令发送失败", str(exc))
                return
            self.response_view.setPlainText(response)

        def _connect_devices(self) -> None:
            vm.connect_mock_devices()

        def _disconnect_devices(self) -> None:
            vm.disconnect_mock_devices()

        def _format_log_entry(self, record: LogEntry) -> str:
            return f"{record.timestamp} [{record.level}] {record.source}/{record.name} - {record.message}"

        def _format_overview_summary(self, overview: dict[str, Any]) -> str:
            run_summary = overview.get("run_summary") or {}
            lines = [
                f"项目: {overview.get('item_name', '')}",
                f"当前步骤: {overview.get('selected_step_id', '')}",
                f"状态: {overview.get('status', '')}",
                f"校准步数: {overview.get('steps', '')}",
                f"连接: {'OK' if overview.get('link_box_connected') and overview.get('vna_connected') else '待连接'}",
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
