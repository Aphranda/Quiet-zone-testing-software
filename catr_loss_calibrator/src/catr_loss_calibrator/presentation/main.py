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

    def confirm(step, substep, phase: str, step_index: int, total: int, substep_index: int, substep_total: int) -> str:
        print(runner.format_step_status(step, step_index, total))
        print(f"  小步骤: [{substep_index}/{substep_total}] {substep.id} - {substep.name}")
        print(f"  确认阶段: {'开始前确认' if phase == 'start' else '数据保存完成确认'}")
        if substep.manual_instruction:
            print(f"  小步骤说明: {substep.manual_instruction}")
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
    from catr_loss_calibrator.project.config import ProjectConfig
    from catr_loss_calibrator.storage.loss_file_policy import FEED_HORN_BANDS

    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QAction, QCursor, QFont, QPainter, QPixmap, QTextCursor
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFormLayout,
        QFrame,
        QFileDialog,
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
        QSizePolicy,
        QSplitter,
        QSpinBox,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication.instance() or QApplication(sys.argv)
    vm = CalibrationViewModel()
    project_config = ProjectConfig()
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
            self.search_edit.setMaximumWidth(140)
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
        def __init__(
            self,
            device_key: str,
            title: str,
            presets: dict[str, str],
            resource_options: tuple[str, ...],
            model_options: tuple[str, ...],
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(title, parent)
            self.device_key = device_key
            self.presets = presets
            self.setMinimumWidth(0)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            layout = QVBoxLayout(self)
            self.mock_check = QCheckBox("Mock")
            self.real_check = QCheckBox("Real")
            self.mock_check.setChecked(True)
            self.mode_group = QButtonGroup(self)
            self.mode_group.setExclusive(True)
            self.mode_group.addButton(self.mock_check)
            self.mode_group.addButton(self.real_check)
            self.resource_input = QComboBox()
            self.resource_input.setEditable(True)
            self.resource_input.addItems(list(resource_options))
            self.resource_input.setMinimumWidth(0)
            self.resource_input.setMinimumContentsLength(8)
            self.resource_input.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.resource_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.model_input = QComboBox()
            self.model_input.setEditable(True)
            self.model_input.addItems(list(model_options))
            self.model_input.setMinimumWidth(0)
            self.model_input.setMinimumContentsLength(8)
            self.model_input.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.model_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.timeout_input = QSpinBox()
            self.timeout_input.setRange(1, 120_000)
            self.timeout_input.setValue(10_000)
            self.timeout_input.setSuffix(" ms")
            self.btn_search_visa = QPushButton("搜索")
            self.btn_search_visa.setToolTip("搜索 VISA 资源")
            self.btn_connect = QPushButton("连接")
            self.btn_disconnect = QPushButton("断开")
            self.connection_state = QLabel("未连接")

            self.preset_combo = QComboBox()
            self.preset_combo.setEditable(device_key == "link_box")
            self.preset_combo.addItems(list(presets.keys()))
            self.preset_combo.setMinimumContentsLength(8)
            self.preset_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.preset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.current_command_label = QLabel()
            self.current_command_label.setWordWrap(True)
            self.preset_combo.currentTextChanged.connect(self._sync_current_command_label)
            self.command_input = QLineEdit()
            self.command_input.setPlaceholderText("输入 SCPI / 控制命令")
            self.response_view = QPlainTextEdit()
            self.response_view.setReadOnly(True)
            self.response_view.setMaximumHeight(88)
            self.response_view.setPlaceholderText("响应")
            self.btn_preset = QPushButton("填充预设")
            self.btn_send = QPushButton("发送命令")
            self.vna_settings_group: QGroupBox | None = None
            self.btn_vna_configure: QPushButton | None = None
            self.btn_vna_trigger: QPushButton | None = None
            self.btn_vna_sample: QPushButton | None = None

            buttons = QHBoxLayout()
            buttons.addWidget(self.btn_preset)
            buttons.addWidget(self.btn_send)

            resource_row = QHBoxLayout()
            resource_row.addWidget(self.resource_input, 1)
            resource_row.addWidget(self.btn_search_visa)

            mode_row = QHBoxLayout()
            mode_row.addWidget(self.mock_check)
            mode_row.addWidget(self.real_check)
            mode_row.addStretch(1)
            button_row = QHBoxLayout()
            button_row.addWidget(self.btn_connect)
            button_row.addWidget(self.btn_disconnect)

            connection_form = QFormLayout()
            connection_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            connection_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            connection_form.addRow("连接模式", mode_row)
            connection_form.addRow("资源地址", resource_row)
            connection_form.addRow("型号", self.model_input)
            connection_form.addRow("超时", self.timeout_input)
            connection_form.addRow("操作", button_row)
            connection_form.addRow("状态", self.connection_state)
            layout.addLayout(connection_form)
            if device_key == "vna":
                layout.addWidget(self._build_vna_settings_group())

            command_form = QFormLayout()
            command_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            command_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            command_form.addRow("预设", self.preset_combo)
            if device_key == "link_box":
                command_form.addRow("当前命令", self.current_command_label)
            command_form.addRow("命令", self.command_input)
            command_form.addRow("操作", buttons)
            command_form.addRow("当前响应", self.response_view)
            layout.addLayout(command_form)
            self._sync_current_command_label(self.preset_combo.currentText())

        def selected_command(self) -> str:
            text = self.preset_combo.currentText().strip()
            return self.presets.get(text, text)

        def command_text(self) -> str:
            return self.command_input.text()

        def set_response(self, response: str) -> None:
            self.response_view.setPlainText(response)

        def set_resource_options(self, options: tuple[str, ...], selected: str | None = None) -> None:
            self._set_combo_options(self.resource_input, options, selected or self.resource_input.currentText())

        def set_model_options(self, options: tuple[str, ...], selected: str | None = None) -> None:
            self._set_combo_options(self.model_input, options, selected or self.model_input.currentText())

        def _sync_current_command_label(self, command: str) -> None:
            selected = self.presets.get(command.strip(), command.strip())
            if self.device_key != "link_box":
                return
            tokens = [
                token
                for token in ("DUT", "H", "V", "VNA1", "VNA2", "SG", "SA", "AMP1", "AMP2")
                if token in selected.upper()
            ]
            suffix = f" | 节点: {', '.join(tokens)}" if tokens else ""
            self.current_command_label.setText(f"当前命令: {selected}{suffix}")

        def set_connection_state(self, state: Any) -> None:
            self.set_resource_options((state.resource,), state.resource)
            self.set_model_options((state.model,), state.model)
            self.mock_check.setChecked(state.use_mock)
            self.real_check.setChecked(not state.use_mock)
            self.timeout_input.setValue(state.timeout_ms)
            self.connection_state.setText("已连接" if state.is_connected else "未连接")
            self.resource_input.setEnabled(not state.is_connected)
            self.model_input.setEnabled(not state.is_connected)
            self.mock_check.setEnabled(not state.is_connected)
            self.real_check.setEnabled(not state.is_connected)
            self.timeout_input.setEnabled(not state.is_connected)
            self.btn_search_visa.setEnabled(not state.is_connected and not state.use_mock)
            self.btn_connect.setEnabled(not state.is_connected)
            self.btn_disconnect.setEnabled(state.is_connected)
            self.preset_combo.setEnabled(state.is_connected)
            self.command_input.setEnabled(state.is_connected)
            self.btn_preset.setEnabled(state.is_connected)
            self.btn_send.setEnabled(state.is_connected)
            if self.vna_settings_group is not None:
                self.vna_settings_group.setEnabled(state.is_connected)

        def connection_config(self) -> dict[str, Any]:
            return {
                "resource": self.resource_input.currentText(),
                "model": self.model_input.currentText(),
                "use_mock": self.mock_check.isChecked(),
                "timeout_ms": self.timeout_input.value(),
            }

        @staticmethod
        def _set_combo_options(combo: QComboBox, options: tuple[str, ...], selected: str) -> None:
            current = str(selected).strip()
            values = []
            seen: set[str] = set()
            for value in (current, *options):
                text = str(value).strip()
                key = text.upper()
                if text and key not in seen:
                    seen.add(key)
                    values.append(text)
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(values)
            if current:
                combo.setCurrentText(current)
            combo.blockSignals(False)

        def vna_settings(self) -> dict[str, Any]:
            return {
                "start_ghz": self.vna_start_ghz.value(),
                "stop_ghz": self.vna_stop_ghz.value(),
                "frequency_step_mhz": self.vna_step_mhz.value(),
                "points": self._vna_sweep_points(),
                "vna_power_dbm": self.vna_power_dbm.value(),
                "if_bandwidth_hz": self.vna_ifbw_hz.value(),
                "sweep_mode": self.vna_sweep_mode.currentData(),
                "continuous_sweep": self.vna_sweep_mode.currentData() == "continuous",
                "parameter": self.vna_parameter.currentText(),
            }

        def _build_vna_settings_group(self) -> QGroupBox:
            self.vna_start_ghz = self._double_spin(10.0, 0.001, 110.0, 0.1, 3, " GHz")
            self.vna_stop_ghz = self._double_spin(17.0, 0.001, 110.0, 0.1, 3, " GHz")
            self.vna_step_mhz = self._double_spin(10.0, 0.001, 1_000_000.0, 1.0, 3, " MHz")
            self.vna_step_mhz.setMaximumWidth(150)
            self.vna_points_label = QLabel()
            self.vna_power_dbm = self._double_spin(-10.0, -90.0, 30.0, 1.0, 1, " dBm")
            self.vna_ifbw_hz = self._double_spin(1000.0, 1.0, 10_000_000.0, 100.0, 0, " Hz")
            self.vna_sweep_mode = QComboBox()
            self.vna_sweep_mode.addItem("Hold", "hold")
            self.vna_sweep_mode.addItem("Single", "single")
            self.vna_sweep_mode.addItem("Continuous", "continuous")
            self.vna_parameter = QComboBox()
            self.vna_parameter.addItems(["S21", "S11", "S12", "S22"])
            self.btn_vna_configure = QPushButton("配置")
            self.btn_vna_trigger = QPushButton("触发")
            self.btn_vna_sample = QPushButton("采样")

            for spinbox in (self.vna_start_ghz, self.vna_stop_ghz, self.vna_step_mhz):
                spinbox.valueChanged.connect(lambda _value: self._refresh_vna_points_label())

            button_row = QHBoxLayout()
            button_row.addWidget(self.btn_vna_configure)
            button_row.addWidget(self.btn_vna_trigger)
            button_row.addWidget(self.btn_vna_sample)

            step_field = QWidget()
            step_layout = QHBoxLayout(step_field)
            step_layout.setContentsMargins(0, 0, 0, 0)
            step_layout.setSpacing(8)
            step_layout.addWidget(self.vna_step_mhz)
            step_layout.addWidget(self.vna_points_label)
            step_layout.addStretch(1)

            group = QGroupBox("网分扫频配置")
            form = QFormLayout(group)
            form.addRow("起频", self.vna_start_ghz)
            form.addRow("止频", self.vna_stop_ghz)
            form.addRow("步进", step_field)
            form.addRow("输出功率", self.vna_power_dbm)
            form.addRow("中频带宽", self.vna_ifbw_hz)
            form.addRow("Sweep 模式", self.vna_sweep_mode)
            form.addRow("S 参数", self.vna_parameter)
            form.addRow(button_row)
            self.vna_settings_group = group
            self._refresh_vna_points_label()
            return group

        def _refresh_vna_points_label(self) -> None:
            self.vna_points_label.setText(f"{self._vna_sweep_points()} 点")

        def _vna_sweep_points(self) -> int:
            span_mhz = abs(self.vna_stop_ghz.value() - self.vna_start_ghz.value()) * 1000.0
            step_mhz = max(self.vna_step_mhz.value(), 1e-9)
            return max(2, int(span_mhz // step_mhz) + 1)

        @staticmethod
        def _double_spin(value: float, minimum: float, maximum: float, step: float, decimals: int, suffix: str) -> QDoubleSpinBox:
            spinbox = QDoubleSpinBox()
            spinbox.setRange(minimum, maximum)
            spinbox.setSingleStep(step)
            spinbox.setDecimals(decimals)
            spinbox.setValue(value)
            spinbox.setSuffix(suffix)
            return spinbox

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("CATR 路损校准操作台")
            self.resize(1180, 780)
            self._last_confirmation_prompt_key = ""

            self.item_list = QListWidget()
            self.item_list.setMinimumWidth(220)
            for item in vm.catalog.items:
                QListWidgetItem(f"{item.id}\n{item.name}", self.item_list)
            self.step_list = QListWidget()
            self.step_list.setMinimumWidth(220)

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
            self.feed_combo = QComboBox()
            self.feed_combo.addItems(sorted({feed for feed, _horn in FEED_HORN_BANDS}))
            self.feed_combo.setCurrentText(project_config.feed)
            self.feed_combo.setMinimumContentsLength(8)
            self.feed_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.feed_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.horn_combo = QComboBox()
            self.horn_combo.addItems(sorted({horn for _feed, horn in FEED_HORN_BANDS}))
            self.horn_combo.setCurrentText(project_config.horn)
            self.horn_combo.setMinimumContentsLength(10)
            self.horn_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.horn_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.horn_gain_file_input = QLineEdit()
            self.horn_gain_file_input.setPlaceholderText("选择标准增益喇叭增益文件")
            self.btn_browse_horn_gain = QPushButton("浏览")
            self.substep_list = QListWidget()
            self.substep_list.setMaximumHeight(132)
            self.substep_list.setMinimumHeight(72)

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

            self.global_log_panel = LogPanel()
            self.log_panels = [self.global_log_panel]

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

            command_presets = vm.device_command_presets()
            self.command_panels = [
                DeviceCommandPanel(
                    "link_box",
                    "链路箱",
                    command_presets["link_box"],
                    vm.device_mock_resource_options("link_box"),
                    vm.device_model_options("link_box"),
                ),
                DeviceCommandPanel(
                    "vna",
                    "网分",
                    command_presets["vna"],
                    vm.device_mock_resource_options("vna"),
                    vm.device_model_options("vna"),
                ),
                DeviceCommandPanel(
                    "signal_generator",
                    "信号源",
                    command_presets["signal_generator"],
                    vm.device_mock_resource_options("signal_generator"),
                    vm.device_model_options("signal_generator"),
                ),
                DeviceCommandPanel(
                    "spectrum_analyzer",
                    "频谱仪",
                    command_presets["spectrum_analyzer"],
                    vm.device_mock_resource_options("spectrum_analyzer"),
                    vm.device_model_options("spectrum_analyzer"),
                ),
            ]
            for panel in self.command_panels:
                state = vm.device_connection_state(panel.device_key)
                panel.set_connection_state(state)
                panel.set_model_options(vm.device_model_options(panel.device_key), state.model)
                panel.set_resource_options(vm.device_mock_resource_options(panel.device_key), state.resource)

            self.status_label = QLabel("Ready")
            self.connection_label = QLabel("VNA: disconnected | SG: disconnected | LinkBox: disconnected | SA: disconnected")

            self.btn_connect = QPushButton("连接全部设备")
            self.btn_disconnect = QPushButton("断开全部设备")
            self.btn_start = QPushButton("开始校准")

            self.btn_refresh = QPushButton("刷新结果")

            self.tabs = QTabWidget()
            self.calibration_page = self._build_calibration_page()
            self.command_page = self._build_command_page()
            self.result_page = self._build_result_page()
            self.tabs.addTab(self.command_page, "仪表配置")
            self.tabs.addTab(self.calibration_page, "校准执行")
            self.tabs.addTab(self.result_page, "结果")

            root = QWidget()
            self.setCentralWidget(root)
            root_layout = QVBoxLayout(root)
            root_layout.addWidget(self._build_header())
            main_splitter = QSplitter(Qt.Horizontal)
            main_splitter.addWidget(self.tabs)
            main_splitter.addWidget(self._build_global_log())
            main_splitter.setStretchFactor(0, 4)
            main_splitter.setStretchFactor(1, 1)
            main_splitter.setSizes([800, 380])
            main_splitter.setCollapsible(0, False)
            main_splitter.setCollapsible(1, False)
            root_layout.addWidget(main_splitter, 1)

            self.statusBar().addWidget(self.status_label, 1)
            self.statusBar().addPermanentWidget(self.connection_label)

            self._bind_events()
            self._sync_horn_options(project_config.feed, project_config.horn)
            self._refresh_item_list()
            self._sync_device_connection_panels()
            self.item_list.setCurrentRow(0)
            vm.refresh_overview()
            self._sync_overview()

        def _center_on_screen(self) -> None:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            if screen is None:
                return
            available_geometry = screen.availableGeometry()
            frame_geometry = self.frameGeometry()
            frame_geometry.moveCenter(available_geometry.center())
            self.move(frame_geometry.topLeft())

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

            center_stack = QWidget()
            center_stack_layout = QVBoxLayout(center_stack)
            center_stack_layout.setContentsMargins(0, 0, 0, 0)
            center_stack_layout.addWidget(self._build_band_config_group())

            center = QGroupBox("步骤执行")
            center_layout = QVBoxLayout(center)
            center_layout.addWidget(self.step_title)
            center_layout.addWidget(self.step_status)
            center_layout.addWidget(self.step_progress)
            self.step_hint = QLabel("选择左侧步骤以查看对应接线与命令。")
            self.step_hint.setStyleSheet("color: #64748B;")
            center_layout.addWidget(self.step_hint)
            center_layout.addWidget(QLabel("小步骤"))
            center_layout.addWidget(self.substep_list)
            center_layout.addWidget(QLabel("接线路径"))
            center_layout.addWidget(self.path_view)
            center_layout.addWidget(QLabel("命令 / 说明"))
            center_layout.addWidget(self.command_view)
            center_layout.addWidget(QLabel("步骤详情"))
            center_layout.addWidget(self.detail_view)

            button_row = QHBoxLayout()
            button_row.addWidget(self.btn_start)
            button_row.addStretch(1)
            center_layout.addLayout(button_row)
            center_stack_layout.addWidget(center, 1)

            splitter = QSplitter(Qt.Horizontal)
            splitter.addWidget(left)
            splitter.addWidget(center_stack)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 3)
            layout.addWidget(splitter)
            return page

        def _build_band_config_group(self) -> QGroupBox:
            group = QGroupBox("频段配置")
            form = QFormLayout(group)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

            band_row = QHBoxLayout()
            band_row.addWidget(QLabel("馈源型号"))
            band_row.addWidget(self.feed_combo, 1)
            band_row.addWidget(QLabel("喇叭型号"))
            band_row.addWidget(self.horn_combo, 1)
            band_row.addWidget(QLabel("喇叭增益文件"))
            band_row.addWidget(self.horn_gain_file_input, 3)
            band_row.addWidget(self.btn_browse_horn_gain)
            form.addRow("配置", band_row)
            return group

        def _build_command_page(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)

            device_grid = QGridLayout()
            device_grid.setHorizontalSpacing(6)
            device_grid.setVerticalSpacing(8)
            for column, panel in enumerate(self.command_panels):
                device_grid.addWidget(panel, 0, column)
                device_grid.setColumnMinimumWidth(column, 0)
                device_grid.setColumnStretch(column, 1)

            layout.addLayout(device_grid)
            layout.addWidget(self.btn_refresh)
            return page

        def _build_global_log(self) -> QWidget:
            box = QGroupBox("LOG")
            box.setMinimumWidth(340)
            box.setMaximumWidth(500)
            layout = QVBoxLayout(box)
            layout.addWidget(self.global_log_panel)
            return box

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
            self.btn_start.clicked.connect(self._confirm_start_calibration)
            self.btn_refresh.clicked.connect(self._sync_overview)
            self.feed_combo.currentTextChanged.connect(self._sync_horn_options)
            self.btn_browse_horn_gain.clicked.connect(self._browse_horn_gain_file)
            for panel in self.command_panels:
                panel.btn_preset.clicked.connect(lambda _checked=False, command_panel=panel: self._fill_preset(command_panel))
                panel.btn_send.clicked.connect(lambda _checked=False, command_panel=panel: self._send_command(command_panel))
                panel.btn_connect.clicked.connect(lambda _checked=False, command_panel=panel: self._connect_command_device(command_panel))
                panel.btn_disconnect.clicked.connect(lambda _checked=False, command_panel=panel: self._disconnect_command_device(command_panel))
                panel.btn_search_visa.clicked.connect(lambda _checked=False, command_panel=panel: self._search_visa_resources(command_panel))
                panel.mock_check.toggled.connect(lambda _checked=False, command_panel=panel: self._on_mock_mode_changed(command_panel))
                panel.real_check.toggled.connect(lambda _checked=False, command_panel=panel: self._on_mock_mode_changed(command_panel))
                panel.command_input.returnPressed.connect(lambda command_panel=panel: self._send_command(command_panel))
                if panel.device_key == "vna":
                    assert panel.btn_vna_configure is not None
                    assert panel.btn_vna_trigger is not None
                    assert panel.btn_vna_sample is not None
                    panel.btn_vna_configure.clicked.connect(lambda _checked=False, command_panel=panel: self._configure_vna(command_panel))
                    panel.btn_vna_trigger.clicked.connect(lambda _checked=False, command_panel=panel: self._trigger_vna(command_panel))
                    panel.btn_vna_sample.clicked.connect(lambda _checked=False, command_panel=panel: self._sample_vna(command_panel))
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
            vm.run_finished.connect(self._confirm_run_finished)

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
            completed_step_ids: set[str] = set()
            run_summary = vm.run_summary_for_item(item.id)
            if isinstance(run_summary, dict) and run_summary.get("item_id") == item.id:
                completed_step_ids = {str(step_id) for step_id in run_summary.get("completed_step_ids", ())}
            for index, step in enumerate(item.steps, start=1):
                if step.id in completed_step_ids:
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
                self._sync_substep_list()
                self.step_hint.setText(f"当前步骤：{current_step.id} · {current_step.name}")
            else:
                self.substep_list.clear()
                self.step_hint.setText("当前校准项暂无步骤。")

        def _sync_step_view(self, step: StepViewData) -> None:
            substep_text = ""
            if step.substep_id:
                substep_text = f" | 小步骤 {step.substep_index}/{step.substep_total}: {step.substep_name}"
            self.step_title.setText(f"[{step.step_index}/{step.step_total}] {step.step_id} - {step.step_name}{substep_text}")
            self.step_status.setText(f"状态：{step.status}")
            progress = int(step.step_index / max(step.step_total, 1) * 100)
            self.step_progress.setValue(progress)
            self._sync_substep_list(step)
            self.path_view.setPlainText(
                step.manual_instruction
                + ("\n\nRoute IDs: " + ", ".join(step.route_ids) if step.route_ids else "")
            )
            self.command_view.setPlainText("\n".join(step.link_commands) or "无链路命令")
            phase_text = ""
            if step.confirm_phase == "start":
                phase_text = "确认阶段: 开始前确认\n"
            elif step.confirm_phase == "saved":
                phase_text = "确认阶段: 数据保存完成确认\n"
            self.detail_view.setPlainText(
                phase_text
                + (f"小步骤: {step.substep_id} {step.substep_name}\n" if step.substep_id else "")
                + f"输入端口: {step.input_port}\n"
                f"输出端口: {step.output_port}\n"
                f"原始输出: {', '.join(step.raw_outputs) or '无'}\n"
                f"最终输出: {', '.join(step.final_outputs) or '无'}\n"
                f"所需输入: {', '.join(step.required_inputs) or '无'}\n"
                f"备注: {step.notes or '无'}"
            )
            self._show_substep_confirmation(step)

        def _sync_substep_list(self, active_step: StepViewData | None = None) -> None:
            step = vm.selected_step
            self.substep_list.blockSignals(True)
            self.substep_list.clear()
            if step is None:
                self.substep_list.blockSignals(False)
                return
            active_id = active_step.substep_id if active_step and active_step.step_id == step.id else ""
            active_index = active_step.substep_index if active_id else 0
            phase = active_step.confirm_phase if active_step and active_id else ""
            current_row = -1
            for index, substep in enumerate(vm.substep_view_data(step), start=1):
                if substep.id == active_id:
                    phase_text = "开始确认" if phase == "start" else "保存确认"
                    prefix = f"▶ 当前 {phase_text}"
                    current_row = index - 1
                elif active_id and index < active_index:
                    prefix = "✓ 已处理"
                else:
                    prefix = "○ 待处理"
                detail = substep.raw_output or substep.final_output or substep.name
                QListWidgetItem(f"{prefix}\n{index}. {substep.id} - {substep.name}\n{detail}", self.substep_list)
            if current_row >= 0:
                self.substep_list.setCurrentRow(current_row)
            self.substep_list.blockSignals(False)

        def _sync_logs(self, *_args: Any) -> None:
            for panel in self.log_panels:
                records = vm.filtered_logs(level=panel.current_level(), keyword=panel.current_keyword())
                panel.set_records(records, self._format_log_entry)

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

        def _sync_horn_options(self, feed: str, preferred_horn: str | None = None) -> None:
            _ = feed
            current = preferred_horn or self.horn_combo.currentText()
            horns = sorted({horn for _candidate_feed, horn in FEED_HORN_BANDS})
            self.horn_combo.blockSignals(True)
            self.horn_combo.clear()
            self.horn_combo.addItems(horns)
            if current in horns:
                self.horn_combo.setCurrentText(current)
            elif horns:
                self.horn_combo.setCurrentIndex(0)
            self.horn_combo.blockSignals(False)

        def _browse_horn_gain_file(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "选择喇叭增益文件",
                "",
                "Gain Files (*.csv *.txt *.s2p *.dat);;All Files (*)",
            )
            if path:
                self.horn_gain_file_input.setText(path)

        def _show_substep_confirmation(self, step: StepViewData) -> None:
            if not step.substep_id or step.confirm_phase not in {"start", "saved"}:
                return
            prompt_key = f"{step.step_id}:{step.substep_id}:{step.confirm_phase}:{step.substep_index}"
            if prompt_key == self._last_confirmation_prompt_key:
                return
            self._last_confirmation_prompt_key = prompt_key

            if step.confirm_phase == "start":
                message = (
                    f"请确认小步骤接线已完成。\n\n"
                    f"大步骤: {step.step_id} - {step.step_name}\n"
                    f"小步骤: {step.substep_index}/{step.substep_total} {step.substep_id} - {step.substep_name}\n"
                    f"输入端口: {step.input_port or '无'}\n"
                    f"输出端口: {step.output_port or '无'}\n\n"
                    f"{step.manual_instruction or '无接线说明'}"
                )
                self._show_prompt_action_dialog(
                    title="确认接线完成",
                    message=message,
                    actions=(
                        ("确认接线完成", "continue"),
                        ("下一步", "skip"),
                        ("取消校准", "cancel"),
                    ),
                    default_action="continue",
                )
                return

            message = (
                f"请确认小步骤数据已保存。\n\n"
                f"大步骤: {step.step_id} - {step.step_name}\n"
                f"小步骤: {step.substep_index}/{step.substep_total} {step.substep_id} - {step.substep_name}\n"
                f"原始输出: {', '.join(step.raw_outputs) or '无'}\n"
                f"最终输出: {', '.join(step.final_outputs) or '无'}"
            )
            self._show_prompt_action_dialog(
                title="确认数据保存完成",
                message=message,
                actions=(
                    ("完成并继续", "continue"),
                    ("上一步", "retry"),
                    ("下一步", "skip"),
                    ("取消校准", "cancel"),
                ),
                default_action="continue",
            )

        def _show_prompt_action_dialog(
            self,
            *,
            title: str,
            message: str,
            actions: tuple[tuple[str, str], ...],
            default_action: str,
        ) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle(title)
            dialog.setMinimumWidth(520)
            selected_action = {"value": "cancel"}

            layout = QVBoxLayout(dialog)
            message_label = QLabel(message)
            message_label.setWordWrap(True)
            layout.addWidget(message_label)

            left_actions = [(label, action) for label, action in actions if action == "retry"]
            right_actions = [(label, action) for label, action in actions if action == "skip"]
            center_actions = [(label, action) for label, action in actions if action not in {"retry", "skip"}]

            button_row = QHBoxLayout()

            def add_action_button(label: str, action: str) -> QPushButton:
                button = QPushButton(label)
                button.clicked.connect(lambda _checked=False, selected=action: self._finish_prompt_dialog(dialog, selected_action, selected))
                if action == default_action:
                    button.setDefault(True)
                    button.setAutoDefault(True)
                return button

            for label, action in left_actions:
                button_row.addWidget(add_action_button(label, action))
            button_row.addStretch(1)
            for label, action in center_actions:
                button_row.addWidget(add_action_button(label, action))
            button_row.addStretch(1)
            for label, action in right_actions:
                button_row.addWidget(add_action_button(label, action))

            layout.addLayout(button_row)
            dialog.exec()
            vm.submit_action(selected_action["value"])

        def _finish_prompt_dialog(self, dialog: QDialog, selected_action: dict[str, str], action: str) -> None:
            selected_action["value"] = action
            dialog.accept()

        def _confirm_start_calibration(self) -> None:
            item = vm.selected_item
            answer = QMessageBox.question(
                self,
                "开始校准确认",
                f"确认开始执行 {item.id} - {item.name}？\n\n步骤列表显示大步骤，步骤执行区会逐个小步骤等待确认。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                vm.start_selected()

        def _confirm_run_finished(self, summary: object) -> None:
            data = dict(summary) if isinstance(summary, dict) else {}
            QMessageBox.information(
                self,
                "校准完成确认",
                "校准执行已完成。\n\n"
                f"校准项: {data.get('item_id', '')}\n"
                f"状态: {data.get('state', '')}\n"
                f"完成小步骤: {data.get('completed_steps', '')}/{data.get('total_substeps', data.get('total_steps', ''))}\n"
                f"最后事件: {data.get('last_event', '')}",
            )

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

        def _configure_vna(self, panel: DeviceCommandPanel) -> None:
            try:
                response = vm.configure_vna(panel.vna_settings())
            except Exception as exc:
                QMessageBox.warning(self, "网分配置失败", str(exc))
                return
            panel.set_response(response)

        def _trigger_vna(self, panel: DeviceCommandPanel) -> None:
            try:
                response = vm.trigger_vna(panel.vna_settings())
            except Exception as exc:
                QMessageBox.warning(self, "网分触发失败", str(exc))
                return
            panel.set_response(response)

        def _sample_vna(self, panel: DeviceCommandPanel) -> None:
            try:
                response = vm.sample_vna(panel.vna_settings())
            except Exception as exc:
                QMessageBox.warning(self, "网分采样失败", str(exc))
                return
            panel.set_response(response)

        def _connect_devices(self) -> None:
            vm.connect_mock_devices()
            self._sync_device_connection_panels()

        def _disconnect_devices(self) -> None:
            vm.disconnect_mock_devices()
            self._sync_device_connection_panels()

        def _connect_command_device(self, panel: DeviceCommandPanel) -> None:
            try:
                vm.update_device_config(panel.device_key, **panel.connection_config())
                state = vm.connect_device(panel.device_key)
            except Exception as exc:
                QMessageBox.warning(self, "设备连接失败", str(exc))
                return
            panel.set_connection_state(state)
            self._sync_overview()

        def _disconnect_command_device(self, panel: DeviceCommandPanel) -> None:
            try:
                state = vm.disconnect_device(panel.device_key)
            except Exception as exc:
                QMessageBox.warning(self, "设备断开失败", str(exc))
                return
            panel.set_connection_state(state)
            self._sync_overview()

        def _search_visa_resources(self, panel: DeviceCommandPanel) -> None:
            if panel.mock_check.isChecked():
                panel.set_resource_options(vm.device_mock_resource_options(panel.device_key))
                return
            try:
                resources = vm.list_visa_resources()
            except Exception as exc:
                QMessageBox.warning(self, "VISA 资源搜索失败", str(exc))
                return
            if not resources:
                QMessageBox.information(self, "VISA 资源搜索", "未发现 VISA 资源。")
                return
            panel.set_resource_options(resources, resources[0])

        def _on_mock_mode_changed(self, panel: DeviceCommandPanel) -> None:
            if panel.mock_check.isChecked():
                resources = vm.device_mock_resource_options(panel.device_key)
                panel.set_resource_options(resources, resources[0] if resources else "")
            else:
                panel.btn_search_visa.setEnabled(True)
                try:
                    resources = vm.list_visa_resources()
                except Exception:
                    return
                if resources:
                    panel.set_resource_options(resources, resources[0])

        def _sync_device_connection_panels(self) -> None:
            for panel in self.command_panels:
                state = vm.device_connection_state(panel.device_key)
                panel.set_connection_state(state)
                panel.set_model_options(vm.device_model_options(panel.device_key), state.model)
                resources = vm.device_mock_resource_options(panel.device_key) if state.use_mock else (state.resource,)
                panel.set_resource_options(resources, state.resource)

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
    window._center_on_screen()
    window.show()
    return app.exec()
