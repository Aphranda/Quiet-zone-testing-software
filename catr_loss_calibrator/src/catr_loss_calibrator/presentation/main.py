from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np

from catr_loss_calibrator.calibration.config_loader import load_calibration_catalog
from catr_loss_calibrator.calibration.calibration_runner import CalibrationRunner
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna
from catr_loss_calibrator.project.config import DEFAULT_VNA_POWER_DBM
from catr_loss_calibrator.runtime_resources import default_output_root, initialize_runtime_files, runtime_default_config_path
from catr_loss_calibrator.storage.resume import CurveQuality, analyze_curve_csv
from catr_loss_calibrator.storage.workspace import (
    CalibrationRunContext,
    create_session_context,
    list_session_summaries,
    list_session_summaries_from_project_root,
    list_session_summaries_from_workspace_root,
    load_legacy_output_summary,
    load_latest_summary,
    load_latest_summary_from_index,
    load_session_summary_from_manifest,
    workspace_config_snapshot_path,
    workspace_for_catalog,
    write_workspace_manifest,
)


def run() -> int:
    args = set(sys.argv[1:])
    if "--cli" in args:
        return run_cli()
    if "--interactive" in args:
        return run_interactive()
    if "--gui-smoke" in args:
        return run_gui()
    try:
        return run_gui()
    except Exception as exc:
        print(f"GUI unavailable: {exc}")
        return run_cli()


def run_cli() -> int:
    initialize_runtime_files()
    catalog = load_calibration_catalog(runtime_default_config_path())
    print("通用路损校准控制台")
    print("Available calibration items:")
    for item in catalog.items:
        print(f"- {item.id}: {item.name} ({len(item.steps)} steps)")
    first_item = catalog.items[0]
    runner = CalibrationRunner(first_item, MockVna(), MockLinkBox(), default_output_root() / "cli")
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
    initialize_runtime_files()
    catalog = load_calibration_catalog(runtime_default_config_path())
    print("通用路损校准控制台 - Interactive")
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

    runner = CalibrationRunner(item, MockVna(), MockLinkBox(), default_output_root() / "interactive", confirm_step=confirm)
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
    from catr_loss_calibrator.presentation.viewmodels import CalibrationViewModel, StepViewData
    from catr_loss_calibrator.project.config import ProjectConfig
    from catr_loss_calibrator.runtime_resources import resolve_data_file
    from catr_loss_calibrator.storage.loss_file_policy import band_entries_from_config, default_feed_horn_from_config

    try:
        import pyqtgraph as pg
    except ImportError:
        pg = None

    from PySide6.QtCore import QUrl, QRectF, Qt
    from PySide6.QtGui import QAction, QBrush, QColor, QCursor, QDesktopServices, QFont, QIcon, QPainter, QPixmap, QTextCursor
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import (
        QAbstractItemView,
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
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QPlainTextEdit,
        QPushButton,
        QProgressBar,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QSpinBox,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
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
    app_icon_path = style_dir / "icons" / "icon_calibration.png"
    app_icon = QIcon(str(app_icon_path)) if app_icon_path.exists() else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    _DISPLAY_TEXT_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\bVNA1\b"), "网分1"),
        (re.compile(r"\bVNA2\b"), "网分2"),
        (re.compile(r"\bVNA\b"), "网分"),
        (re.compile(r"\bSG\b"), "信号源"),
        (re.compile(r"\bSA\b"), "频谱仪"),
        (re.compile(r"\bLB\b"), "链路箱"),
        (re.compile(r"\bTD\b"), "转台 DUT 接口"),
        (re.compile(r"\bCP\b"), "暗室接口板"),
        (re.compile(r"\bAMP1\b"), "放大器1"),
        (re.compile(r"\bAMP2\b"), "放大器2"),
    )

    _NODE_LABELS: dict[str, str] = {
        "PORT1": "网分 PORT1",
        "PORT2": "网分 PORT2",
        "P1": "网分 PORT1",
        "P2": "网分 PORT2",
        "CP-H": "暗室接口板 H",
        "CP-V": "暗室接口板 V",
        "CP-DUT": "暗室接口板 DUT",
        "TD": "转台 DUT 接口",
        "转台DUT接口": "转台 DUT 接口",
        "DUT_REF": "DUT 参考面",
        "FH": "馈源 H",
        "FV": "馈源 V",
        "LB-H": "链路箱 H",
        "LB-V": "链路箱 V",
        "LB-DUT": "链路箱 DUT",
        "LB-VNA1": "链路箱 网分1",
        "LB-VNA2": "链路箱 网分2",
        "LB-SG": "链路箱 信号源",
        "LB-SA": "链路箱 频谱仪",
        "VNA1": "网分1",
        "VNA2": "网分2",
        "VNA": "网分",
        "SG": "信号源",
        "SA": "频谱仪",
        "AMP1": "放大器1",
        "AMP2": "放大器2",
        "POL-H": "H 极化",
        "POL-V": "V 极化",
    }

    _COMMAND_TOKEN_LABELS: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\bDUT_REF\b"), "被测件参考面"),
        (re.compile(r"\bCP-DUT\b"), "暗室接口板-被测件"),
        (re.compile(r"\bCP-H\b"), "暗室接口板-水平极化"),
        (re.compile(r"\bCP-V\b"), "暗室接口板-垂直极化"),
        (re.compile(r"\bLB\b"), "链路箱"),
        (re.compile(r"\bTD\b"), "转台DUT接口"),
        (re.compile(r"\bDUT\b"), "被测件"),
        (re.compile(r"\bFH\b"), "馈源H"),
        (re.compile(r"\bFV\b"), "馈源V"),
        (re.compile(r"\bPORT1\b"), "网分PORT1"),
        (re.compile(r"\bPORT2\b"), "网分PORT2"),
        (re.compile(r"\bP1\b"), "网分PORT1"),
        (re.compile(r"\bP2\b"), "网分PORT2"),
        (re.compile(r"\bVNA1\b"), "网分1"),
        (re.compile(r"\bVNA2\b"), "网分2"),
        (re.compile(r"\bSG\b"), "信号源"),
        (re.compile(r"\bSA\b"), "频谱仪"),
        (re.compile(r"\bAMP1\b"), "放大器1"),
        (re.compile(r"\bAMP2\b"), "放大器2"),
        (re.compile(r"(?<![A-Za-z0-9_/])H(?![A-Za-z0-9_/])"), "水平极化"),
        (re.compile(r"(?<![A-Za-z0-9_/])V(?![A-Za-z0-9_/])"), "垂直极化"),
    )

    def _friendly_text(value: Any) -> str:
        text = str(value)
        for pattern, replacement in _DISPLAY_TEXT_REPLACEMENTS:
            text = pattern.sub(replacement, text)
        return text

    def _friendly_join(values: tuple[str, ...], *, empty: str = "无") -> str:
        if not values:
            return empty
        return ", ".join(_friendly_text(value) for value in values)

    def _plain_join(values: tuple[str, ...], *, empty: str = "无") -> str:
        return ", ".join(values) if values else empty

    def _stage_display(value: Any) -> str:
        text = str(value).strip()
        labels = {
            "initial": "初始校准",
            "retest": "复测",
            "after_repair": "维修后",
            "after_change": "变更后",
            "pre_delivery": "交付前",
            "debug": "调试",
        }
        return labels.get(text, text)

    def _friendly_node_text(value: str) -> str:
        text = value.strip()
        catalog_entry = _node_catalog_entry(text)
        if catalog_entry:
            label = str(catalog_entry.get("label", "")).strip()
            if label:
                return label
        exact = _NODE_LABELS.get(text.upper())
        if exact:
            return exact
        if "/" in text:
            return "/".join(_friendly_node_text(part) for part in text.split("/"))
        return _friendly_text(text)

    def _node_catalog_entry(key: str) -> dict[str, Any]:
        node_catalog = vm.catalog.node_catalog
        raw_key = str(key).strip()
        entry = node_catalog.get(raw_key) or node_catalog.get(raw_key.upper())
        return entry if isinstance(entry, dict) else {}

    def _route_nodes_from_instruction(instruction: str) -> list[list[str]]:
        routes: list[list[str]] = []
        for segment in re.split(r"[；;\n]+", instruction):
            segment = segment.strip(" 。.\t")
            if not re.search(r"(?:->|→)", segment):
                continue
            nodes = [node.strip(" 。.\t") for node in re.split(r"\s*(?:->|→)\s*", segment)]
            nodes = [node for node in nodes if node]
            if len(nodes) >= 2:
                routes.append(nodes)
        return routes

    def _path_data_for_step(step: StepViewData) -> dict[str, Any]:
        if step.path:
            return step.path
        template_id = step.path_template.strip()
        if not template_id:
            return {}
        template = vm.catalog.path_templates.get(template_id)
        return template if isinstance(template, dict) else {}

    def _path_routes_from_data(path_data: dict[str, Any]) -> list[list[tuple[str, str]]]:
        routes_payload = path_data.get("routes", ())
        if not isinstance(routes_payload, (list, tuple)):
            return []
        routes: list[list[tuple[str, str]]] = []
        for route_payload in routes_payload:
            if isinstance(route_payload, dict):
                nodes_payload = route_payload.get("nodes", ())
            else:
                nodes_payload = route_payload
            if not isinstance(nodes_payload, (list, tuple)):
                continue
            route: list[tuple[str, str]] = []
            for node_key in nodes_payload:
                raw_node = str(node_key).strip()
                if not raw_node:
                    continue
                entry = _node_catalog_entry(raw_node)
                label = str(entry.get("label", "")).strip() if entry else ""
                style_role = str(entry.get("style", "")).strip() if entry else ""
                route.append((label or _friendly_node_text(raw_node), style_role))
            if len(route) >= 2:
                routes.append(route)
        return routes

    def _node_style(node: str, style_role: str = "") -> str:
        styles = {
            "vna": "border-color:#9fb3d4;color:#294566;background:#fbfdff;",
            "aux": "border-color:#e7b284;color:#8b4a1f;background:#fff9f3;",
            "panel": "border-color:#a9bbd8;color:#324f72;background:#f8fbff;",
            "dut": "border-color:#9cc79f;color:#376c3a;background:#f8fcf8;",
            "feed": "border-color:#a9c7a7;color:#3d6f42;background:#f7fcf7;",
            "space": "border-color:#c2cbd6;color:#455a64;background:#ffffff;",
            "reference": "border-color:#9fcba7;color:#3a7446;background:#f6fbf7;",
            "link_box": "border-color:#b4bfd0;color:#3f5268;background:#fbfcfe;",
            "amp": "border-color:#d7b589;color:#735225;background:#fffaf2;",
        }
        if style_role in styles:
            return styles[style_role]
        normalized = node.upper()
        if "AUX-" in normalized or "辅助线" in node:
            return "border-color:#f2a56b;color:#c45113;background:#fff7ed;"
        if "标准增益喇叭" in node or "标准喇叭" in node:
            return "border-color:#88c999;color:#2f7d45;background:#f3fbf4;"
        if "暗室接口板" in node or "CP-" in normalized:
            return "border-color:#8ea8ce;color:#1f3f68;background:#f8fbff;"
        if "PORT" in normalized or re.search(r"\bP[12]\b", normalized) or "VNA" in normalized or "网分" in node:
            return "border-color:#7c95bb;color:#18375f;background:#fbfdff;"
        if "转台" in node or "DUT" in normalized:
            return "border-color:#82b584;color:#2f6f3b;background:#f7fcf7;"
        return "border-color:#9eb2ca;color:#263238;background:#ffffff;"

    def _format_path_html(step: StepViewData) -> str:
        title = f"步骤 {step.step_index}: {_friendly_text(step.step_name)}"
        if step.substep_id:
            title = f"步骤 {step.step_index}.{step.substep_index}: {_friendly_text(step.substep_name)}"

        path_data = _path_data_for_step(step)
        routes = _path_routes_from_data(path_data)
        if not routes:
            routes = [[(_friendly_node_text(node), "") for node in route] for route in _route_nodes_from_instruction(step.manual_instruction)]
        route_html: list[str] = []
        for nodes in routes:
            parts: list[str] = []
            for index, (node, style_role) in enumerate(nodes):
                label = html.escape(node)
                style = _node_style(node, style_role)
                parts.append(
                    "<span style='display:inline-block;border:1px solid "
                    "#9eb2ca;border-radius:5px;padding:5px 11px;margin:3px 4px 3px 0;"
                    f"{style}'>{label}</span>"
                )
                if index < len(nodes) - 1:
                    parts.append("<span style='color:#64748b;margin:0 6px;'>→</span>")
            route_html.append("<div style='margin-top:5px;'>" + "".join(parts) + "</div>")

        instruction = html.escape(step.manual_instruction or "无接线说明")
        caption = ""
        if path_data:
            caption_text = str(path_data.get("caption", "")).strip()
            if caption_text:
                caption = f"<div style='margin-top:6px;color:#607d8b;font-size:12px;'>{html.escape(caption_text)}</div>"
        route_ids = ""
        if step.route_ids:
            route_ids = (
                "<div style='margin-top:6px;color:#78909c;font-size:12px;'>路线标识: "
                + html.escape(", ".join(step.route_ids))
                + "</div>"
            )
        body = "".join(route_html) if route_html else f"<div style='margin-top:6px;color:#455a64;'>{instruction}</div>"
        return (
            "<div style='font-family:Microsoft YaHei UI, Segoe UI, sans-serif;font-size:13px;color:#263238;'>"
            f"<div style='font-weight:700;color:#1f3f68;margin-bottom:4px;'>{html.escape(title)}</div>"
            f"{body}"
            f"{caption}"
            f"<div style='margin-top:7px;color:#607d8b;font-size:12px;'>{instruction}</div>"
            f"{route_ids}"
            "</div>"
        )

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

    def _style_button(button: QPushButton, *, role: str, state: str | None = None) -> None:
        button.setProperty("buttonRole", role)
        if state is not None:
            button.setProperty("buttonState", state)
        style = button.style()
        style.unpolish(button)
        style.polish(button)
        button.update()

    class LogPanel(QWidget):
        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setObjectName("logPanel")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)

            self.toolbar = QToolBar()
            self.toolbar.setObjectName("logToolbar")
            self.toolbar.setMovable(False)

            self.level_combo = QComboBox()
            self.level_combo.addItems(["ALL", "INFO", "WARN", "ERROR"])
            self.level_combo.setFixedWidth(82)
            self.toolbar.addWidget(QLabel("级别:"))
            self.toolbar.addWidget(self.level_combo)

            self.font_combo = QComboBox()
            self.font_combo.addItems([str(size) for size in range(8, 16)])
            self.font_combo.setCurrentText("10")
            self.font_combo.setFixedWidth(58)
            self.toolbar.addWidget(QLabel("字体:"))
            self.toolbar.addWidget(self.font_combo)

            self.wrap_action = QAction("自动换行", self)
            self.wrap_action.setCheckable(True)
            self.toolbar.addAction(self.wrap_action)

            self.timestamp_action = QAction("时间戳", self)
            self.timestamp_action.setCheckable(True)
            self.timestamp_action.setChecked(True)
            self.toolbar.addAction(self.timestamp_action)

            self.copy_selection_action = QAction("复制选中", self)
            self.toolbar.addAction(self.copy_selection_action)

            self.copy_all_action = QAction("复制全部", self)
            self.toolbar.addAction(self.copy_all_action)

            self.clear_log_action = QAction("清空LOG", self)
            self.toolbar.addAction(self.clear_log_action)

            for action, width in (
                (self.wrap_action, 78),
                (self.timestamp_action, 64),
                (self.copy_selection_action, 72),
                (self.copy_all_action, 68),
                (self.clear_log_action, 68),
            ):
                button = self.toolbar.widgetForAction(action)
                if button is not None:
                    button.setMinimumWidth(width)
                    button.setFixedHeight(30)

            self.text_edit = QTextEdit()
            self.text_edit.setObjectName("logText")
            self.text_edit.setReadOnly(True)
            self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
            self.text_edit.setFont(QFont("Consolas", 10))

            self.font_combo.currentTextChanged.connect(self._apply_font_size)
            self.wrap_action.toggled.connect(self._set_word_wrap)
            self.copy_selection_action.triggered.connect(self.copy_selected_text)
            self.copy_all_action.triggered.connect(self.copy_all_text)

            layout.addWidget(self.toolbar)
            layout.addWidget(self.text_edit)

        def current_level(self) -> str:
            return self.level_combo.currentText()

        def show_timestamp(self) -> bool:
            return self.timestamp_action.isChecked()

        def set_records(self, records: list[LogEntry], formatter: Any) -> None:
            self.text_edit.setHtml("<br>".join(formatter(record, self.show_timestamp()) for record in records))
            self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

        def copy_selected_text(self) -> str:
            text = self.text_edit.textCursor().selectedText().replace("\u2029", "\n")
            if text:
                QApplication.clipboard().setText(text)
            return text

        def copy_all_text(self) -> str:
            text = self.text_edit.toPlainText()
            if text:
                QApplication.clipboard().setText(text)
            return text

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
            self.resource_input.setMinimumWidth(0)
            self.resource_input.setMinimumContentsLength(8)
            self.resource_input.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.resource_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.model_input = QComboBox()
            self.model_input.setEditable(True)
            self.model_input.setMinimumWidth(0)
            self.model_input.setMinimumContentsLength(8)
            self.model_input.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.model_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._set_combo_options(self.resource_input, resource_options, resource_options[0] if resource_options else "")
            self._set_combo_options(self.model_input, model_options, model_options[0] if model_options else "")
            self.resource_input.currentTextChanged.connect(lambda text: self._sync_combo_tooltip(self.resource_input, text))
            self.model_input.currentTextChanged.connect(self._on_model_changed)
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
            self.signal_generator_settings_group: QGroupBox | None = None
            self.btn_sg_configure: QPushButton | None = None
            self.spectrum_analyzer_settings_group: QGroupBox | None = None
            self.btn_sa_configure: QPushButton | None = None
            self.link_box_ip_input: QLineEdit | None = None
            self.link_box_port_input: QSpinBox | None = None
            if device_key == "link_box":
                self.link_box_ip_input = QLineEdit()
                self.link_box_ip_input.setPlaceholderText("192.168.1.113")
                self.link_box_ip_input.setText("192.168.1.113")
                self.link_box_port_input = QSpinBox()
                self.link_box_port_input.setRange(1, 65535)
                self.link_box_port_input.setValue(7)

            _style_button(self.btn_search_visa, role="secondary")
            _style_button(self.btn_connect, role="success")
            _style_button(self.btn_disconnect, role="danger")
            _style_button(self.btn_preset, role="secondary")
            _style_button(self.btn_send, role="primary")

            buttons = QHBoxLayout()
            buttons.addWidget(self.btn_preset)
            buttons.addWidget(self.btn_send)

            resource_row = QHBoxLayout()
            resource_row.addWidget(self.resource_input, 1)
            resource_row.addWidget(self.btn_search_visa)
            self.btn_search_visa.setVisible(device_key != "link_box")

            mode_row = QHBoxLayout()
            mode_row.addWidget(self.mock_check)
            mode_row.addWidget(self.real_check)
            mode_row.addStretch(1)
            button_row = QHBoxLayout()
            button_row.addWidget(self.btn_connect)
            button_row.addWidget(self.btn_disconnect)

            connection_group = QGroupBox("资源连接")
            connection_form = QFormLayout(connection_group)
            connection_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            connection_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            connection_form.addRow("连接模式", mode_row)
            if device_key == "link_box":
                connection_form.addRow("IP地址", self.link_box_ip_input)
                connection_form.addRow("端口", self.link_box_port_input)
            else:
                connection_form.addRow("资源地址", resource_row)
            connection_form.addRow("型号", self.model_input)
            connection_form.addRow("超时", self.timeout_input)
            connection_form.addRow("操作", button_row)
            connection_form.addRow("状态", self.connection_state)
            layout.addWidget(connection_group)
            if device_key == "vna":
                layout.addWidget(self._build_vna_settings_group())
            elif device_key == "signal_generator":
                layout.addWidget(self._build_signal_generator_settings_group())
            elif device_key == "spectrum_analyzer":
                layout.addWidget(self._build_spectrum_analyzer_settings_group())

            command_group = QGroupBox("指令控制")
            command_form = QFormLayout(command_group)
            command_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            command_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            command_form.addRow("预设", self.preset_combo)
            if device_key == "link_box":
                command_form.addRow("当前命令", self.current_command_label)
            command_form.addRow("命令", self.command_input)
            command_form.addRow("操作", buttons)
            command_form.addRow("当前响应", self.response_view)
            layout.addWidget(command_group)
            layout.addStretch(1)
            self._sync_current_command_label(self.preset_combo.currentText())

        def selected_command(self) -> str:
            text = self.preset_combo.currentText().strip()
            return self.presets.get(text, text)

        def set_presets(self, presets: dict[str, str]) -> None:
            current = self.preset_combo.currentText().strip()
            self.presets = dict(presets)
            self.preset_combo.blockSignals(True)
            self.preset_combo.clear()
            self.preset_combo.addItems(list(self.presets.keys()))
            if current in self.presets:
                self.preset_combo.setCurrentText(current)
            self.preset_combo.blockSignals(False)
            self._sync_current_command_label(self.preset_combo.currentText())

        def command_text(self) -> str:
            return self.command_input.text()

        def set_response(self, response: str) -> None:
            self.response_view.setPlainText(response)

        def set_resource_options(self, options: tuple[str, ...], selected: str | None = None) -> None:
            self._set_combo_options(self.resource_input, options, selected or self.resource_input.currentText())

        def set_model_options(self, options: tuple[str, ...], selected: str | None = None) -> None:
            self._set_combo_options(self.model_input, options, selected or self.model_input.currentText())

        def select_matching_resource_for_model(self) -> bool:
            if self.mock_check.isChecked():
                return False
            model = self.model_input.currentText().strip()
            if not model:
                return False
            current = self.resource_input.currentText().strip()
            if self._resource_matches_model(current, model):
                return False
            for index in range(self.resource_input.count()):
                resource = self.resource_input.itemText(index).strip()
                if self._resource_matches_model(resource, model):
                    self.resource_input.setCurrentText(resource)
                    return True
            return False

        def _on_model_changed(self, text: str) -> None:
            self._sync_combo_tooltip(self.model_input, text)
            self.select_matching_resource_for_model()

        def _sync_current_command_label(self, command: str) -> None:
            selected = self.presets.get(command.strip(), command.strip())
            if self.device_key != "link_box":
                return
            tokens = [label for pattern, label in self._COMMAND_TOKEN_LABELS if pattern.search(selected)]
            tokens = list(dict.fromkeys(tokens))
            suffix = f" | 节点: {', '.join(tokens)}" if tokens else ""
            self.current_command_label.setText(f"当前命令: {selected}{suffix}")

        def set_connection_state(self, state: Any) -> None:
            self.set_resource_options((state.resource,), state.resource)
            self.set_model_options((state.model,), state.model)
            if self.device_key == "link_box" and self.link_box_ip_input is not None and self.link_box_port_input is not None:
                ip_address, tcp_port = self._link_box_ip_port_from_state(state)
                self.link_box_ip_input.setText(ip_address)
                self.link_box_port_input.setValue(tcp_port)
            self.mock_check.setChecked(state.use_mock)
            self.real_check.setChecked(not state.use_mock)
            self.timeout_input.setValue(state.timeout_ms)
            self.connection_state.setText("已连接" if state.is_connected else "未连接")
            self.resource_input.setEnabled(not state.is_connected)
            self.model_input.setEnabled(not state.is_connected)
            self.mock_check.setEnabled(not state.is_connected)
            self.real_check.setEnabled(not state.is_connected)
            self.timeout_input.setEnabled(not state.is_connected)
            self.btn_search_visa.setEnabled(not state.is_connected and not state.use_mock and self.device_key != "link_box")
            if self.link_box_ip_input is not None:
                self.link_box_ip_input.setEnabled(not state.is_connected)
            if self.link_box_port_input is not None:
                self.link_box_port_input.setEnabled(not state.is_connected)
            self.btn_connect.setEnabled(not state.is_connected)
            self.btn_disconnect.setEnabled(state.is_connected)
            self.preset_combo.setEnabled(state.is_connected)
            self.command_input.setEnabled(state.is_connected)
            self.btn_preset.setEnabled(state.is_connected)
            self.btn_send.setEnabled(state.is_connected)
            if self.vna_settings_group is not None:
                self.vna_settings_group.setEnabled(state.is_connected)
            if self.signal_generator_settings_group is not None:
                self.signal_generator_settings_group.setEnabled(state.is_connected)
            if self.spectrum_analyzer_settings_group is not None:
                self.spectrum_analyzer_settings_group.setEnabled(state.is_connected)

        def connection_config(self) -> dict[str, Any]:
            if self.device_key == "link_box" and self.link_box_ip_input is not None and self.link_box_port_input is not None:
                ip_address = self.link_box_ip_input.text().strip()
                tcp_port = self.link_box_port_input.value()
                return {
                    "resource": f"{ip_address}:{tcp_port}" if ip_address else "",
                    "model": self.model_input.currentText(),
                    "use_mock": self.mock_check.isChecked(),
                    "timeout_ms": self.timeout_input.value(),
                    "ip_address": ip_address,
                    "tcp_port": tcp_port,
                }
            return {
                "resource": self.resource_input.currentText(),
                "model": self.model_input.currentText(),
                "use_mock": self.mock_check.isChecked(),
                "timeout_ms": self.timeout_input.value(),
            }

        @staticmethod
        def _link_box_ip_port_from_state(state: Any) -> tuple[str, int]:
            ip_address = str(getattr(state, "ip_address", "") or "").strip()
            tcp_port = getattr(state, "tcp_port", None)
            if not ip_address:
                match = re.match(r"^(?P<host>[^:\s]+):(?P<port>\d+)$", str(getattr(state, "resource", "") or "").strip())
                if match is not None:
                    ip_address = match.group("host")
                    tcp_port = int(match.group("port"))
            return ip_address or "192.168.1.113", int(tcp_port or 7)

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
            for index, text in enumerate(values):
                combo.setItemData(index, text, Qt.ItemDataRole.ToolTipRole)
            if current:
                combo.setCurrentText(current)
            combo.blockSignals(False)
            DeviceCommandPanel._sync_combo_tooltip(combo, combo.currentText())

        @staticmethod
        def _sync_combo_tooltip(combo: QComboBox, text: str) -> None:
            tooltip = str(text).strip()
            combo.setToolTip(tooltip)
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.setToolTip(tooltip)

        @staticmethod
        def _resource_matches_model(resource: str, model: str) -> bool:
            model_key = DeviceCommandPanel._match_key(model)
            if len(model_key) < 3 or model_key == "MOCK":
                return False
            resource_key = DeviceCommandPanel._match_key(resource)
            return bool(resource_key and model_key in resource_key)

        @staticmethod
        def _match_key(text: str) -> str:
            return re.sub(r"[^A-Z0-9]", "", str(text).upper()).replace("MOCK", "")


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

        def signal_generator_settings(self) -> dict[str, Any]:
            return {
                "frequency_ghz": self.sg_frequency_ghz.value(),
                "power_dbm": self.sg_power_dbm.value(),
                "output_enabled": self.sg_output_enabled.isChecked(),
            }

        def spectrum_analyzer_settings(self) -> dict[str, Any]:
            return {
                "center_ghz": self.sa_center_ghz.value(),
                "span_mhz": self.sa_span_mhz.value(),
                "points": self.sa_points.value(),
                "rbw_hz": self.sa_rbw_hz.value(),
                "vbw_hz": self.sa_vbw_hz.value(),
                "reference_level_dbm": self.sa_reference_level_dbm.value(),
                "attenuation_db": self.sa_attenuation_db.value(),
            }

        def _build_vna_settings_group(self) -> QGroupBox:
            self.vna_start_ghz = self._double_spin(10.0, 0.001, 110.0, 0.1, 3, " GHz")
            self.vna_stop_ghz = self._double_spin(17.0, 0.001, 110.0, 0.1, 3, " GHz")
            self.vna_step_mhz = self._double_spin(10.0, 0.001, 1_000_000.0, 1.0, 3, " MHz")
            self.vna_step_mhz.setMaximumWidth(150)
            self.vna_points_label = QLabel()
            self.vna_power_dbm = self._double_spin(DEFAULT_VNA_POWER_DBM, -90.0, 30.0, 1.0, 1, " dBm")
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
            _style_button(self.btn_vna_configure, role="primary")
            _style_button(self.btn_vna_trigger, role="warning")
            _style_button(self.btn_vna_sample, role="success")

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

            group = QGroupBox("仪表配置")
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

        def _build_signal_generator_settings_group(self) -> QGroupBox:
            self.sg_frequency_ghz = self._double_spin(10.0, 0.001, 110.0, 0.1, 6, " GHz")
            self.sg_power_dbm = self._double_spin(-10.0, -120.0, 30.0, 1.0, 1, " dBm")
            self.sg_output_enabled = QCheckBox("输出 ON")
            self.sg_output_enabled.setChecked(False)
            self.btn_sg_configure = QPushButton("配置")
            _style_button(self.btn_sg_configure, role="primary")

            group = QGroupBox("仪表配置")
            form = QFormLayout(group)
            form.addRow("频率", self.sg_frequency_ghz)
            form.addRow("功率", self.sg_power_dbm)
            form.addRow("输出", self.sg_output_enabled)
            form.addRow(self.btn_sg_configure)
            self.signal_generator_settings_group = group
            return group

        def _build_spectrum_analyzer_settings_group(self) -> QGroupBox:
            self.sa_center_ghz = self._double_spin(10.0, 0.001, 110.0, 0.1, 6, " GHz")
            self.sa_span_mhz = self._double_spin(100.0, 0.001, 100_000.0, 10.0, 3, " MHz")
            self.sa_points = QSpinBox()
            self.sa_points.setRange(2, 100_001)
            self.sa_points.setSingleStep(100)
            self.sa_points.setValue(1001)
            self.sa_rbw_hz = self._double_spin(1_000_000.0, 1.0, 100_000_000.0, 1000.0, 0, " Hz")
            self.sa_vbw_hz = self._double_spin(1_000_000.0, 1.0, 100_000_000.0, 1000.0, 0, " Hz")
            self.sa_reference_level_dbm = self._double_spin(0.0, -150.0, 60.0, 1.0, 1, " dBm")
            self.sa_attenuation_db = self._double_spin(10.0, 0.0, 70.0, 1.0, 1, " dB")
            self.btn_sa_configure = QPushButton("配置")
            _style_button(self.btn_sa_configure, role="primary")

            group = QGroupBox("仪表配置")
            form = QFormLayout(group)
            form.addRow("中心频率", self.sa_center_ghz)
            form.addRow("Span", self.sa_span_mhz)
            form.addRow("点数", self.sa_points)
            form.addRow("RBW", self.sa_rbw_hz)
            form.addRow("VBW", self.sa_vbw_hz)
            form.addRow("参考电平", self.sa_reference_level_dbm)
            form.addRow("衰减", self.sa_attenuation_db)
            form.addRow(self.btn_sa_configure)
            self.spectrum_analyzer_settings_group = group
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

    DeviceCommandPanel._COMMAND_TOKEN_LABELS = _COMMAND_TOKEN_LABELS

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("通用路损校准控制台")
            if not app_icon.isNull():
                self.setWindowIcon(app_icon)
            self._current_step_view: StepViewData | None = None
            self._active_prompt_view: StepViewData | None = None

            self.item_list = QListWidget()
            self.item_list.setMinimumWidth(220)
            self._sync_item_list()
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
            self.logo_title = QLabel("通用路损校准控制台")
            self.logo_title.setObjectName("appTitle")
            self.logo_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #23405c;")

            self.step_title = QLabel("未开始")
            self.step_title.setStyleSheet("font-size: 15px; font-weight: 600;")
            self.step_status = QLabel("状态：IDLE")
            self.step_progress = QProgressBar()
            self.step_progress.setRange(0, 100)
            default_feed, default_horn = default_feed_horn_from_config(vm.catalog.band_config)
            band_entries = band_entries_from_config(vm.catalog.band_config)
            self.feed_combo = QComboBox()
            self.feed_combo.addItems(sorted({str(entry["feed"]) for entry in band_entries}))
            self.feed_combo.setCurrentText(project_config.feed or default_feed)
            self.feed_combo.setMinimumContentsLength(8)
            self.feed_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.feed_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.horn_combo = QComboBox()
            self.horn_combo.addItems(sorted({str(entry["horn"]) for entry in band_entries}))
            self.horn_combo.setCurrentText(project_config.horn or default_horn)
            self.horn_combo.setMinimumContentsLength(10)
            self.horn_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.horn_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.horn_gain_file_input = QLineEdit()
            self.horn_gain_file_input.setPlaceholderText("选择标准增益喇叭增益文件")
            self.btn_browse_horn_gain = QPushButton("浏览")
            self.project_code_input = QLineEdit("DEFAULT_PROJECT")
            self.project_code_input.setPlaceholderText("项目代号 / 样机 / 任务")
            self.project_code_input.setMinimumWidth(220)
            self.calibration_stage_combo = QComboBox()
            self.calibration_stage_combo.setEditable(True)
            for label, code in (
                ("初始校准", "initial"),
                ("复测", "retest"),
                ("维修后", "after_repair"),
                ("变更后", "after_change"),
                ("交付前", "pre_delivery"),
                ("调试", "debug"),
            ):
                self.calibration_stage_combo.addItem(label, code)
            self.calibration_stage_combo.setMinimumWidth(150)
            self.run_label_input = QLineEdit("R01")
            self.run_label_input.setPlaceholderText("R01")
            self.run_label_input.setMinimumWidth(120)
            self.btn_import_history_data = QPushButton("导入历史数据")
            _style_button(self.btn_import_history_data, role="secondary")
            self.history_data_status = QLabel("未导入历史数据")
            self.history_data_status.setObjectName("hintLabel")
            self.history_data_status.setStyleSheet("color: #64748B;")
            self.history_data_status.setMinimumWidth(0)
            self.history_data_status.setMaximumWidth(260)
            self.history_data_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            self.substep_list = QListWidget()
            self.substep_list.setMinimumWidth(220)
            self.substep_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            self.path_view = QTextEdit()
            self.path_view.setReadOnly(True)
            self.path_view.setPlaceholderText("接线路径将显示在这里")
            self.path_view.setMinimumHeight(150)
            self.path_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            self.command_view = QPlainTextEdit()
            self.command_view.setReadOnly(True)
            self.command_view.setMaximumBlockCount(200)
            self.command_view.setMinimumHeight(92)
            self.command_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            self.detail_view = QPlainTextEdit()
            self.detail_view.setReadOnly(True)
            self.detail_view.setMaximumBlockCount(200)
            self.detail_view.setMinimumHeight(92)
            self.detail_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            self.saved_curve_status = QLabel("选择细分步骤后显示可用曲线")
            self.saved_curve_status.setWordWrap(True)
            self.saved_curve_column = QComboBox()
            self.saved_curve_column.setEnabled(False)
            self.saved_curve_column.setMinimumWidth(0)
            self.saved_curve_column.setMaximumWidth(140)
            self.saved_curve_column.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            self.manual_curve_judgment_combo = QComboBox()
            self.manual_curve_judgment_combo.addItem("未判定", "")
            self.manual_curve_judgment_combo.addItem("人工判定：正常可沿用", "accept")
            self.manual_curve_judgment_combo.addItem("人工判定：异常需重测", "retest")
            self.manual_curve_judgment_combo.setEnabled(False)
            self.manual_curve_judgment_combo.setMinimumWidth(0)
            self.manual_curve_judgment_combo.setMaximumWidth(190)
            self.manual_curve_judgment_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            self.btn_use_history_curve = QPushButton("沿用历史")
            self.btn_retest_substep = QPushButton("重测当前")
            self.btn_generate_resume_results = QPushButton("生成/更新结果")
            self.btn_use_history_curve.setEnabled(False)
            self.btn_retest_substep.setEnabled(False)
            self.btn_generate_resume_results.setEnabled(False)
            self.btn_use_history_curve.setFixedWidth(82)
            self.btn_retest_substep.setFixedWidth(82)
            self.btn_generate_resume_results.setFixedWidth(112)
            _style_button(self.btn_use_history_curve, role="success")
            _style_button(self.btn_retest_substep, role="warning")
            _style_button(self.btn_generate_resume_results, role="primary")
            self.btn_saved_curve_autorange = QPushButton("自适应")
            self.btn_saved_curve_autorange.setEnabled(False)
            self.btn_saved_curve_autorange.setFixedWidth(74)
            _style_button(self.btn_saved_curve_autorange, role="secondary")
            if pg is not None:
                self.saved_curve_plot = pg.PlotWidget()
                self.saved_curve_plot.setBackground("#ffffff")
                self.saved_curve_plot.showGrid(x=True, y=True, alpha=0.25)
                self.saved_curve_plot.setLabel("bottom", "频率", units="GHz")
                self.saved_curve_plot.setLabel("left", "幅度", units="dB")
                self.saved_curve_plot.setMinimumWidth(0)
                self.saved_curve_plot.setMinimumHeight(320)
                self.saved_curve_plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            else:
                self.saved_curve_plot = QPlainTextEdit()
                self.saved_curve_plot.setReadOnly(True)
                self.saved_curve_plot.setPlainText("未安装 pyqtgraph，无法显示曲线。")
                self.saved_curve_plot.setMinimumWidth(0)
                self.saved_curve_plot.setMinimumHeight(320)
                self.saved_curve_plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            self.global_log_panel = LogPanel()
            self.log_panels = [self.global_log_panel]

            self.result_summary = QPlainTextEdit()
            self.result_summary.setReadOnly(True)
            self.result_summary.setMaximumHeight(118)
            self.result_summary.setPlaceholderText("运行摘要将在这里显示")
            self.result_view_combo = QComboBox()
            self.result_view_combo.addItem("当前Session", "current")
            self.result_view_combo.addItem("最新成功", "latest")
            self.result_view_combo.addItem("历史Session", "history")
            self.result_view_combo.addItem("旧版目录", "legacy")
            self.result_view_combo.setFixedWidth(116)
            self.result_history_combo = QComboBox()
            self.result_history_combo.setEnabled(False)
            self.result_history_combo.setMinimumContentsLength(26)
            self.result_history_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.result_history_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.result_workspace_input = QLineEdit()
            self.result_workspace_input.setPlaceholderText("校准工作空间或旧版输出目录路径")
            self.result_workspace_input.setMinimumWidth(320)
            self.btn_result_browse_workspace = QPushButton("浏览Workspace")
            self.btn_result_load_workspace = QPushButton("加载历史")
            self.btn_result_open_history_dir = QPushButton("打开历史目录")
            self.result_file_table = QTableWidget(0, 5)
            self.result_file_table.setObjectName("resultFileTable")
            self.result_file_table.setHorizontalHeaderLabels(["类型", "文件名", "大小", "修改时间", "路径"])
            self.result_file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.result_file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.result_file_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            self.result_file_table.verticalHeader().setVisible(False)
            self.result_file_table.horizontalHeader().setStretchLastSection(True)
            self.result_file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.result_file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            self.result_file_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            self.result_file_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            self.result_file_table.setMinimumHeight(190)
            self.result_file_table.setAlternatingRowColors(True)
            self.btn_result_refresh = QPushButton("刷新结果")
            self.btn_result_copy_path = QPushButton("复制路径")
            self.btn_result_open_dir = QPushButton("打开目录")
            self.btn_result_open_session = QPushButton("打开Session")
            self.btn_result_open_project = QPushButton("打开项目")
            self.btn_result_open_workspace = QPushButton("打开Workspace")
            self.btn_result_generate_resume_results = QPushButton("重新计算")
            self.btn_result_export_summary = QPushButton("导出摘要")
            self.btn_result_generate_resume_results.setEnabled(False)
            _style_button(self.btn_result_browse_workspace, role="secondary")
            _style_button(self.btn_result_load_workspace, role="secondary")
            _style_button(self.btn_result_open_history_dir, role="primary")
            _style_button(self.btn_result_refresh, role="secondary")
            _style_button(self.btn_result_copy_path, role="secondary")
            _style_button(self.btn_result_open_dir, role="primary")
            _style_button(self.btn_result_open_session, role="primary")
            _style_button(self.btn_result_open_project, role="primary")
            _style_button(self.btn_result_open_workspace, role="primary")
            _style_button(self.btn_result_generate_resume_results, role="success")
            _style_button(self.btn_result_export_summary, role="success")
            self.result_curve_status = QLabel("选择 CSV 结果文件后显示曲线")
            self.result_curve_status.setWordWrap(True)
            self.result_curve_column = QComboBox()
            self.result_curve_column.setEnabled(False)
            self.btn_result_curve_autorange = QPushButton("自适应")
            self.btn_result_curve_autorange.setEnabled(False)
            _style_button(self.btn_result_curve_autorange, role="secondary")
            if pg is not None:
                self.result_curve_plot = pg.PlotWidget()
                self.result_curve_plot.setBackground("#ffffff")
                self.result_curve_plot.showGrid(x=True, y=True, alpha=0.25)
                self.result_curve_plot.setLabel("bottom", "频率", units="GHz")
                self.result_curve_plot.setLabel("left", "幅度", units="dB")
                self.result_curve_plot.setMinimumHeight(240)
            else:
                self.result_curve_plot = QPlainTextEdit()
                self.result_curve_plot.setReadOnly(True)
                self.result_curve_plot.setPlainText("未安装 pyqtgraph，无法显示曲线。")
                self.result_curve_plot.setMinimumHeight(240)
            self.result_session = QPlainTextEdit()
            self.result_session.setReadOnly(True)
            self.result_session.setMaximumHeight(150)
            self.result_session.setPlaceholderText("会话与运行记录")
            self._result_rows: list[dict[str, str]] = []
            self._current_curve_data: dict[str, tuple[np.ndarray, np.ndarray]] = {}
            self._saved_curve_data: dict[str, tuple[np.ndarray, np.ndarray]] = {}
            self._saved_curve_path: Path | None = None
            self._history_data_summary: dict[str, object] = {}
            self._curve_quality_cache: dict[str, CurveQuality] = {}
            self._manual_curve_judgments: dict[str, str] = {}
            self._current_curve_step_key = ""
            self._history_session_summaries: tuple[dict[str, object], ...] = ()

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
            self.connection_label = QLabel("网分: disconnected | 信号源: disconnected | 链路箱: disconnected | 频谱仪: disconnected")
            self.header_config_label = QLabel("配置: 未加载链路配置")
            self.header_run_label = QLabel("项目: DEFAULT_PROJECT / 初始校准 / R01")
            self.header_connection_label = QLabel("设备: 待连接")
            self.header_status_label = QLabel("状态: Ready")
            for label in (
                self.header_config_label,
                self.header_run_label,
                self.header_connection_label,
                self.header_status_label,
            ):
                label.setObjectName("headerInfoLabel")
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            self.btn_connect = QPushButton("连接全部设备")
            self.btn_disconnect = QPushButton("断开全部设备")
            self.btn_start = QPushButton("开始校准")
            self.btn_start.setFixedWidth(120)
            self.btn_start.setProperty("recalibrateAction", False)
            self.btn_import_config = QPushButton("导入链路配置")
            self.btn_import_default_config = QPushButton("导入默认配置")
            self.inline_confirm_panel: QFrame | None = None
            self.inline_confirm_label: QLabel | None = None
            self.btn_inline_retry: QPushButton | None = None
            self.btn_inline_continue: QPushButton | None = None
            self.btn_inline_skip: QPushButton | None = None
            self.btn_inline_cancel: QPushButton | None = None
            self.config_path_input = QLineEdit()
            self.config_path_input.setReadOnly(True)
            self.config_path_input.setPlaceholderText("当前配置路径")
            self.config_path_input.setMinimumWidth(320)

            self.btn_refresh = QPushButton("刷新结果")
            _style_button(self.btn_connect, role="success")
            _style_button(self.btn_disconnect, role="danger")
            _style_button(self.btn_start, role="primary", state="idle")
            _style_button(self.btn_import_config, role="secondary")
            _style_button(self.btn_import_default_config, role="secondary")
            _style_button(self.btn_refresh, role="secondary")

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
            main_splitter.setSizes([760, 480])
            main_splitter.setCollapsible(0, False)
            main_splitter.setCollapsible(1, False)
            root_layout.addWidget(main_splitter, 1)

            self.statusBar().addWidget(self.status_label, 1)
            self.statusBar().addPermanentWidget(self.connection_label)

            self._bind_events()
            self._sync_horn_options(project_config.feed, project_config.horn)
            self._refresh_item_list()
            self._sync_device_connection_panels()
            self._sync_catalog_path_field()
            self.item_list.setCurrentRow(0)
            vm.refresh_overview()
            self._sync_overview()
            self._apply_initial_window_size()

        def _apply_initial_window_size(self) -> None:
            target_width = 1180
            target_height = 720
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            if screen is None:
                self.resize(target_width, target_height)
                return
            available = screen.availableGeometry()
            width = min(target_width, max(320, available.width() - 80))
            height = min(target_height, max(320, available.height() - 80))
            self.resize(width, height)

        def _center_on_screen(self) -> None:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            if screen is None:
                return
            available_geometry = screen.availableGeometry()
            frame_geometry = self.frameGeometry()
            frame_geometry.moveCenter(available_geometry.center())
            top_left = frame_geometry.topLeft()
            offset_x = 200
            offset_y = 120
            self.move(
                max(available_geometry.left(), top_left.x() - offset_x),
                max(available_geometry.top(), top_left.y() - offset_y),
            )

        def _build_header(self) -> QWidget:
            box = QFrame()
            box.setObjectName("headerBanner")
            box.setObjectName("appHeader")
            box.setMinimumHeight(72)
            layout = QHBoxLayout(box)
            brand_panel = QFrame()
            brand_panel.setObjectName("brandPanel")
            brand_panel.setMinimumWidth(360)
            brand_layout = QHBoxLayout(brand_panel)
            brand_layout.setContentsMargins(14, 10, 16, 10)
            brand_layout.setSpacing(12)
            brand_layout.addWidget(self.logo_badge)
            brand_layout.addWidget(self.logo_title)
            brand_layout.addStretch(1)
            layout.addWidget(brand_panel, 0)
            context_panel = QFrame()
            context_panel.setObjectName("headerContextPanel")
            context_layout = QGridLayout(context_panel)
            context_layout.setContentsMargins(12, 8, 12, 8)
            context_layout.setHorizontalSpacing(16)
            context_layout.setVerticalSpacing(4)
            context_layout.addWidget(self.header_config_label, 0, 0)
            context_layout.addWidget(self.header_run_label, 0, 1)
            context_layout.addWidget(self.header_connection_label, 1, 0)
            context_layout.addWidget(self.header_status_label, 1, 1)
            context_layout.setColumnStretch(0, 2)
            context_layout.setColumnStretch(1, 1)
            layout.addWidget(context_panel, 1)
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
            center_stack_layout.addWidget(self._build_link_config_group())
            center_stack_layout.addWidget(self._build_run_context_group())

            center = QGroupBox("步骤执行")
            center_layout = QVBoxLayout(center)
            center_layout.addWidget(self.step_title)
            center_layout.addWidget(self.step_status)
            center_layout.addWidget(self.step_progress)
            self.step_hint = QLabel("选择左侧步骤后，在细分步骤框中查看 STEP1、STEP2、STEP3。")
            self.step_hint.setStyleSheet("color: #64748B;")
            center_layout.addWidget(self.step_hint)

            execution_body = QSplitter(Qt.Horizontal)

            substep_box = QGroupBox("细分步骤")
            substep_box.setMinimumWidth(240)
            substep_layout = QVBoxLayout(substep_box)
            substep_layout.setContentsMargins(8, 8, 8, 8)
            substep_layout.addWidget(self.substep_list)

            detail_box = QWidget()
            detail_box.setMinimumWidth(0)
            detail_layout = QVBoxLayout(detail_box)
            detail_layout.setContentsMargins(0, 0, 0, 0)
            self.step_detail_stack = QTabWidget()
            self.step_detail_stack.setMinimumWidth(0)
            self.step_detail_stack.setMinimumHeight(430)
            self.step_detail_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            instruction_page = QWidget()
            instruction_page.setMinimumHeight(400)
            instruction_page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            instruction_layout = QVBoxLayout(instruction_page)
            instruction_layout.setContentsMargins(0, 0, 0, 0)
            instruction_layout.addWidget(QLabel("接线路径"))
            instruction_layout.addWidget(self.path_view, 3)
            instruction_layout.addWidget(QLabel("命令 / 说明"))
            instruction_layout.addWidget(self.command_view, 2)
            instruction_layout.addWidget(QLabel("步骤详情"))
            instruction_layout.addWidget(self.detail_view, 2)
            saved_curve_page = QWidget()
            saved_curve_page.setMinimumWidth(0)
            saved_curve_page.setMinimumHeight(400)
            saved_curve_page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            saved_curve_layout = QVBoxLayout(saved_curve_page)
            saved_curve_layout.setContentsMargins(0, 0, 0, 0)
            saved_curve_tools = QGridLayout()
            saved_curve_tools.setContentsMargins(0, 0, 0, 0)
            saved_curve_tools.setHorizontalSpacing(6)
            saved_curve_tools.setVerticalSpacing(6)
            saved_curve_tools.addWidget(QLabel("曲线"), 0, 0)
            saved_curve_tools.addWidget(self.saved_curve_column, 0, 1)
            saved_curve_tools.addWidget(self.btn_saved_curve_autorange, 0, 2)
            saved_curve_tools.addWidget(QLabel("人工判断"), 1, 0)
            saved_curve_tools.addWidget(self.manual_curve_judgment_combo, 1, 1, 1, 2)
            action_row = QHBoxLayout()
            action_row.setContentsMargins(0, 0, 0, 0)
            action_row.setSpacing(6)
            action_row.addWidget(self.btn_use_history_curve)
            action_row.addWidget(self.btn_retest_substep)
            action_row.addWidget(self.btn_generate_resume_results)
            action_row.addStretch(1)
            saved_curve_tools.addLayout(action_row, 1, 3)
            saved_curve_tools.setColumnStretch(3, 1)
            saved_curve_layout.addLayout(saved_curve_tools)
            saved_curve_layout.addWidget(self.saved_curve_status)
            saved_curve_layout.addWidget(self.saved_curve_plot, 1)
            self.step_detail_stack.addTab(instruction_page, "链路说明")
            self.step_detail_stack.addTab(saved_curve_page, "数据展示")
            detail_layout.addWidget(self.step_detail_stack, 1)

            execution_body.addWidget(substep_box)
            execution_body.addWidget(detail_box)
            execution_body.setStretchFactor(0, 1)
            execution_body.setStretchFactor(1, 3)
            center_layout.addWidget(execution_body, 1)
            prompt_row = QHBoxLayout()
            prompt_row.setContentsMargins(0, 0, 0, 0)
            prompt_row.setSpacing(8)
            prompt_row.addWidget(self._build_run_action_panel(), 0)
            prompt_row.addWidget(self._build_inline_confirmation_panel(), 1)
            center_layout.addLayout(prompt_row)
            center_stack_layout.addWidget(center, 1)

            page_splitter = QSplitter(Qt.Horizontal)
            page_splitter.addWidget(left)
            page_splitter.addWidget(center_stack)
            page_splitter.setStretchFactor(0, 1)
            page_splitter.setStretchFactor(1, 3)
            layout.addWidget(page_splitter)
            return page

        def _build_inline_confirmation_panel(self) -> QFrame:
            panel = QFrame()
            panel.setObjectName("inlineConfirmPanel")
            panel.setMinimumWidth(0)
            panel.setMinimumHeight(62)
            panel.setMaximumHeight(78)
            panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout = QHBoxLayout(panel)
            layout.setContentsMargins(12, 8, 12, 8)
            layout.setSpacing(8)
            self.inline_confirm_panel = panel

            self.inline_confirm_label = QLabel("等待校准确认")
            self.inline_confirm_label.setWordWrap(True)
            layout.addWidget(self.inline_confirm_label, 1)

            self.btn_inline_retry = QPushButton("上一步")
            self.btn_inline_continue = QPushButton("确认")
            self.btn_inline_skip = QPushButton("下一步")
            self.btn_inline_cancel = QPushButton("取消")
            self.btn_inline_retry.setToolTip("重复当前小步骤")
            self.btn_inline_continue.setToolTip("确认当前小步骤并继续执行")
            self.btn_inline_skip.setToolTip("跳过当前小步骤，进入下一个小步骤")
            self.btn_inline_cancel.setToolTip("取消本次校准")
            _style_button(self.btn_inline_retry, role="warning")
            _style_button(self.btn_inline_continue, role="success")
            _style_button(self.btn_inline_skip, role="primary")
            _style_button(self.btn_inline_cancel, role="danger")

            self.btn_inline_retry.clicked.connect(lambda _checked=False: self._submit_inline_prompt_action("retry"))
            self.btn_inline_continue.clicked.connect(lambda _checked=False: self._submit_inline_prompt_action("continue"))
            self.btn_inline_skip.clicked.connect(lambda _checked=False: self._submit_inline_prompt_action("skip"))
            self.btn_inline_cancel.clicked.connect(lambda _checked=False: self._submit_inline_prompt_action("cancel"))

            layout.addWidget(self.btn_inline_retry)
            layout.addWidget(self.btn_inline_continue)
            layout.addWidget(self.btn_inline_skip)
            layout.addWidget(self.btn_inline_cancel)
            self._set_inline_confirmation_idle(panel)
            return panel

        def _build_run_action_panel(self) -> QFrame:
            panel = QFrame()
            panel.setObjectName("startControlPanel")
            panel.setMinimumHeight(62)
            panel.setMaximumHeight(78)
            panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            layout = QHBoxLayout(panel)
            layout.setContentsMargins(12, 8, 12, 8)
            layout.setSpacing(8)
            layout.addWidget(self.btn_start)
            return panel

        def _build_link_config_group(self) -> QGroupBox:
            group = QGroupBox("链路配置")
            form = QFormLayout(group)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

            config_row = QHBoxLayout()
            config_row.addWidget(QLabel("配置文件"))
            config_row.addWidget(self.config_path_input, 1)
            config_row.addWidget(self.btn_import_config)
            config_row.addWidget(self.btn_import_default_config)
            form.addRow(config_row)

            band_row = QHBoxLayout()
            band_row.addWidget(QLabel("馈源型号"))
            band_row.addWidget(self.feed_combo, 1)
            band_row.addWidget(QLabel("喇叭型号"))
            band_row.addWidget(self.horn_combo, 1)
            band_row.addWidget(QLabel("喇叭增益文件"))
            band_row.addWidget(self.horn_gain_file_input, 3)
            band_row.addWidget(self.btn_browse_horn_gain)
            form.addRow(band_row)
            return group

        def _build_run_context_group(self) -> QGroupBox:
            group = QGroupBox("校准批次")
            row = QHBoxLayout(group)
            row.setContentsMargins(12, 12, 12, 12)
            row.setSpacing(10)
            row.addWidget(QLabel("项目代号"))
            row.addWidget(self.project_code_input, 2)
            row.addWidget(QLabel("校准阶段"))
            row.addWidget(self.calibration_stage_combo, 1)
            row.addWidget(QLabel("批次/轮次"))
            row.addWidget(self.run_label_input, 1)
            row.addWidget(self.btn_import_history_data)
            row.addWidget(self.history_data_status, 0)
            row.addStretch(1)
            return group

        def _build_command_page(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)

            device_container = QWidget()
            device_grid = QGridLayout()
            device_container.setLayout(device_grid)
            device_grid.setHorizontalSpacing(6)
            device_grid.setVerticalSpacing(8)
            for column, panel in enumerate(self.command_panels):
                device_grid.addWidget(panel, 0, column)
                device_grid.setColumnMinimumWidth(column, 0)
                device_grid.setColumnStretch(column, 1)

            device_scroll = QScrollArea()
            device_scroll.setWidgetResizable(True)
            device_scroll.setFrameShape(QFrame.Shape.NoFrame)
            device_scroll.setMinimumWidth(0)
            device_scroll.setWidget(device_container)
            layout.addWidget(device_scroll, 1)
            layout.addWidget(self.btn_refresh)
            return page

        def _build_global_log(self) -> QWidget:
            box = QGroupBox("LOG")
            box.setMinimumWidth(420)
            box.setMaximumWidth(650)
            layout = QVBoxLayout(box)
            layout.addWidget(self.global_log_panel)
            return box

        def _build_result_page(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.addWidget(QLabel("运行摘要"))
            layout.addWidget(self.result_summary)
            workspace_row = QHBoxLayout()
            workspace_row.addWidget(QLabel("校准工作空间"))
            workspace_row.addWidget(self.result_workspace_input, 1)
            workspace_row.addWidget(self.btn_result_browse_workspace)
            workspace_row.addWidget(self.btn_result_load_workspace)
            workspace_row.addWidget(self.btn_result_open_history_dir)
            layout.addLayout(workspace_row)
            action_row = QHBoxLayout()
            action_row.addWidget(QLabel("生成文件"))
            action_row.addWidget(QLabel("结果视图"))
            action_row.addWidget(self.result_view_combo)
            action_row.addWidget(QLabel("历史"))
            action_row.addWidget(self.result_history_combo, 1)
            action_row.addStretch(1)
            action_row.addWidget(self.btn_result_refresh)
            action_row.addWidget(self.btn_result_copy_path)
            action_row.addWidget(self.btn_result_open_dir)
            action_row.addWidget(self.btn_result_open_session)
            action_row.addWidget(self.btn_result_open_project)
            action_row.addWidget(self.btn_result_open_workspace)
            action_row.addWidget(self.btn_result_generate_resume_results)
            action_row.addWidget(self.btn_result_export_summary)
            layout.addLayout(action_row)
            layout.addWidget(self.result_file_table)
            curve_row = QHBoxLayout()
            curve_row.addWidget(QLabel("曲线预览"))
            curve_row.addWidget(self.result_curve_column)
            curve_row.addWidget(self.btn_result_curve_autorange)
            curve_row.addStretch(1)
            layout.addLayout(curve_row)
            layout.addWidget(self.result_curve_status)
            layout.addWidget(self.result_curve_plot)
            layout.addWidget(QLabel("会话记录"))
            layout.addWidget(self.result_session)
            return page

        def _bind_events(self) -> None:
            self.item_list.currentRowChanged.connect(vm.select_item)
            self.step_list.currentRowChanged.connect(vm.select_step)
            self.btn_connect.clicked.connect(self._connect_devices)
            self.btn_disconnect.clicked.connect(self._disconnect_devices)
            self.btn_start.clicked.connect(self._confirm_start_button)
            self.btn_import_config.clicked.connect(self._import_link_config)
            self.btn_import_default_config.clicked.connect(self._import_default_link_config)
            self.btn_refresh.clicked.connect(self._sync_overview)
            self.feed_combo.currentTextChanged.connect(self._sync_horn_options)
            self.horn_combo.currentTextChanged.connect(lambda _text: self._apply_band_sweep_range())
            self.project_code_input.textChanged.connect(lambda _text: self._sync_header_context())
            self.calibration_stage_combo.currentTextChanged.connect(lambda _text: self._sync_header_context())
            self.run_label_input.textChanged.connect(lambda _text: self._sync_header_context())
            self.btn_import_history_data.clicked.connect(self._import_history_data)
            self.btn_browse_horn_gain.clicked.connect(self._browse_horn_gain_file)
            self.btn_result_refresh.clicked.connect(self._sync_overview)
            self.btn_result_browse_workspace.clicked.connect(self._browse_result_workspace)
            self.btn_result_load_workspace.clicked.connect(self._load_result_workspace)
            self.btn_result_open_history_dir.clicked.connect(self._open_history_sessions_dir)
            self.btn_result_copy_path.clicked.connect(self._copy_selected_result_path)
            self.btn_result_open_dir.clicked.connect(self._open_selected_result_dir)
            self.btn_result_open_session.clicked.connect(lambda _checked=False: self._open_result_context_dir("session_root"))
            self.btn_result_open_project.clicked.connect(lambda _checked=False: self._open_result_context_dir("project_root"))
            self.btn_result_open_workspace.clicked.connect(lambda _checked=False: self._open_result_context_dir("workspace_root"))
            self.btn_result_generate_resume_results.clicked.connect(self._generate_resume_results)
            self.btn_result_export_summary.clicked.connect(self._export_result_summary)
            self.result_view_combo.currentIndexChanged.connect(lambda _index: self._sync_overview())
            self.result_history_combo.currentIndexChanged.connect(lambda _index: self._sync_overview())
            self.result_file_table.itemSelectionChanged.connect(self._sync_result_curve)
            self.result_curve_column.currentTextChanged.connect(self._plot_selected_result_curve)
            self.btn_result_curve_autorange.clicked.connect(self._autorange_result_curve)
            self.saved_curve_column.currentTextChanged.connect(self._plot_saved_step_curve)
            self.btn_saved_curve_autorange.clicked.connect(self._autorange_saved_step_curve)
            self.manual_curve_judgment_combo.currentIndexChanged.connect(lambda _index: self._on_manual_curve_judgment_changed())
            self.btn_use_history_curve.clicked.connect(self._use_selected_history_curve)
            self.btn_retest_substep.clicked.connect(self._retest_selected_substep)
            self.btn_generate_resume_results.clicked.connect(self._generate_resume_results)
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
                elif panel.device_key == "signal_generator":
                    assert panel.btn_sg_configure is not None
                    panel.btn_sg_configure.clicked.connect(lambda _checked=False, command_panel=panel: self._configure_signal_generator(command_panel))
                elif panel.device_key == "spectrum_analyzer":
                    assert panel.btn_sa_configure is not None
                    panel.btn_sa_configure.clicked.connect(lambda _checked=False, command_panel=panel: self._configure_spectrum_analyzer(command_panel))
            for panel in self.log_panels:
                panel.level_combo.currentTextChanged.connect(self._sync_logs)
                panel.timestamp_action.toggled.connect(self._sync_logs)
                panel.clear_log_action.triggered.connect(self._clear_logs)

            vm.selected_item_changed.connect(self._sync_item_detail)
            vm.selected_step_changed.connect(self._sync_step_list_colored)
            vm.catalog_changed.connect(self._sync_after_catalog_changed)
            vm.step_view_changed.connect(self._sync_step_view)
            vm.step_view_changed.connect(self._sync_step_list_colored)
            self.substep_list.currentRowChanged.connect(self._on_substep_selected)
            vm.overview_changed.connect(self._sync_item_list)
            vm.logs_changed.connect(self._sync_logs)
            vm.status_changed.connect(self.status_label.setText)
            vm.overview_changed.connect(self._sync_overview)
            vm.run_state_changed.connect(self._on_state_changed)
            vm.command_response_changed.connect(self._sync_command_response)
            vm.run_finished.connect(self._confirm_run_finished)

        def _refresh_item_list(self) -> None:
            self._sync_item_list()
            self._sync_item_detail()

        def _sync_after_catalog_changed(self) -> None:
            self._history_data_summary = {}
            self._curve_quality_cache.clear()
            self._manual_curve_judgments.clear()
            self._current_curve_step_key = ""
            self.btn_generate_resume_results.setEnabled(False)
            self.btn_result_generate_resume_results.setEnabled(False)
            self.history_data_status.setText("未导入历史数据")
            self.history_data_status.setToolTip("")
            self._sync_catalog_path_field()
            self._sync_command_presets()
            self._sync_band_options()
            self._refresh_item_list()
            self._sync_device_connection_panels()

        def _sync_catalog_path_field(self) -> None:
            source_path = vm.catalog.source_path or "未加载链路配置"
            self.config_path_input.setText(source_path)
            self.config_path_input.setToolTip(source_path)
            config_name = vm.catalog.display_name or vm.catalog.name or Path(source_path).stem if source_path != "未加载链路配置" else source_path
            self.header_config_label.setText(f"配置: {_friendly_text(config_name)}")
            self.header_config_label.setToolTip(source_path)

        def _sync_header_context(self) -> None:
            overview = vm.overview or {}
            stage_code = str(self.calibration_stage_combo.currentData() or self.calibration_stage_combo.currentText()).strip()
            self.header_run_label.setText(
                f"项目: {self.project_code_input.text().strip() or 'DEFAULT_PROJECT'} / "
                f"{_stage_display(stage_code) or stage_code or '-'} / "
                f"{self.run_label_input.text().strip() or 'R01'}"
            )
            connected_count = sum(
                bool(overview.get(key))
                for key in (
                    "vna_connected",
                    "signal_generator_connected",
                    "link_box_connected",
                    "spectrum_analyzer_connected",
                )
            )
            self.header_connection_label.setText(f"设备: {connected_count}/4 已连接")
            self.header_status_label.setText(f"状态: {overview.get('status', 'Ready')}")

        def _sync_command_presets(self) -> None:
            command_presets = vm.device_command_presets()
            for panel in self.command_panels:
                panel.set_presets(command_presets[panel.device_key])

        def _import_link_config(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "导入链路配置",
                "",
                "Link Config JSON (*.json);;All Files (*)",
            )
            if not path:
                return
            try:
                vm.load_catalog(path)
            except Exception as exc:
                self._show_modal_dialog(
                    title="导入链路配置失败",
                    message=f"无法导入所选 JSON。\n\n文件：{path}\n错误：{exc}",
                    buttons=(("确认", "ok", "center"),),
                    default_action="ok",
                    width=620,
                    height=260,
                )
                return
            self._show_modal_dialog(
                title="导入链路配置完成",
                message=f"已加载链路配置。\n\n文件：{path}",
                buttons=(("确认", "ok", "center"),),
                default_action="ok",
                width=560,
                height=220,
            )

        def _import_default_link_config(self) -> None:
            try:
                vm.load_default_catalog()
            except Exception as exc:
                self._show_modal_dialog(
                    title="导入默认配置失败",
                    message=f"无法导入默认链路配置。\n\n错误：{exc}",
                    buttons=(("确认", "ok", "center"),),
                    default_action="ok",
                    width=560,
                    height=240,
                )
                return
            self._show_modal_dialog(
                title="导入默认配置完成",
                message="已加载默认链路配置。",
                buttons=(("确认", "ok", "center"),),
                default_action="ok",
                width=520,
                height=200,
            )

        @staticmethod
        def _list_status_text(status: str) -> str:
            return {
                "pending": "未开始",
                "running": "进行中",
                "done": "已完成",
                "history": "已有历史",
                "broken": "历史异常",
            }.get(status, "未开始")

        @staticmethod
        def _list_status_palette(status: str) -> tuple[str, str, bool]:
            return {
                "pending": ("#6d7b86", "#f5f7f8", False),
                "running": ("#9a6b17", "#fff4df", True),
                "done": ("#356a45", "#edf6ef", True),
                "history": ("#245f8d", "#eaf4fb", True),
                "broken": ("#a33a3a", "#fff0f0", True),
            }.get(status, ("#6d7b86", "#f5f7f8", False))

        def _apply_status_style(self, item: QListWidgetItem, status: str) -> None:
            foreground, background, bold = self._list_status_palette(status)
            item.setForeground(QBrush(QColor(foreground)))
            item.setBackground(QBrush(QColor(background)))
            font = item.font()
            font.setBold(bold)
            item.setFont(font)
            item.setToolTip(self._list_status_text(status))

        @staticmethod
        def _set_current_row_visible(list_widget: QListWidget, row: int) -> None:
            if row < 0 or row >= list_widget.count():
                return
            list_widget.setCurrentRow(row)
            item = list_widget.item(row)
            if item is not None:
                list_widget.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

        def _sync_item_list(self) -> None:
            current_item_id = vm.selected_item.id if vm.catalog.items else ""
            self.item_list.blockSignals(True)
            self.item_list.clear()
            current_row = 0
            for index, item in enumerate(vm.catalog.items):
                status = vm.item_progress_state(item.id)
                status = self._combined_item_status(item, status)
                list_item = QListWidgetItem(
                    f"{self._list_status_text(status)}\n{item.id}\n{_friendly_text(item.name)}"
                )
                self._apply_status_style(list_item, status)
                self.item_list.addItem(list_item)
                if item.id == current_item_id:
                    current_row = index
            if vm.catalog.items:
                self._set_current_row_visible(self.item_list, current_row)
            self.item_list.blockSignals(False)

        def _sync_item_detail(self) -> None:
            item = vm.selected_item
            if item is None:
                self.item_summary.setText("未加载链路配置。\n请先导入链路配置或导入默认配置。")
                self._active_prompt_view = None
                self.step_list.clear()
                self.substep_list.clear()
                self.step_title.setText("未加载链路配置")
                self.step_status.setText("状态：IDLE")
                self.step_progress.setValue(0)
                self.path_view.clear()
                self.command_view.setPlainText("未加载链路配置")
                self.detail_view.setPlainText("请先导入链路配置或导入默认配置。")
                self._sync_overview()
                return
            self.item_summary.setText(
                f"ID: {item.id}\n"
                f"名称: {_friendly_text(item.name)}\n"
                f"步骤数: {len(item.steps)}\n"
                f"用途: {_friendly_text(item.purpose)}"
            )
            self._sync_step_list_colored()
            self._sync_overview()

        def _combined_item_status(self, item: Any, fallback: str) -> str:
            if fallback in {"done", "running"}:
                return fallback
            if not self._history_data_summary or str(self._history_data_summary.get("item_id") or "") != item.id:
                return fallback
            step_statuses = [self._combined_step_status(item.id, step, "pending") for step in item.steps]
            if step_statuses and all(status == "done" for status in step_statuses):
                return "done"
            if any(status == "broken" for status in step_statuses):
                return "broken"
            if any(status == "history" for status in step_statuses):
                return "history"
            return fallback

        def _combined_step_status(self, item_id: str, step: Any, fallback: str) -> str:
            if fallback in {"done", "running"}:
                return fallback
            substep_statuses = [
                self._history_display_status_for_ids(item_id, step.id, substep.id)
                for substep in vm.substep_view_data(step)
            ]
            substep_statuses = [status for status in substep_statuses if status]
            if not substep_statuses:
                return fallback
            if all(status == "done" for status in substep_statuses):
                return "done"
            if any(status == "broken" for status in substep_statuses):
                return "broken"
            if any(status in {"history", "done"} for status in substep_statuses):
                return "history"
            return fallback

        def _history_display_status_for_ids(self, item_id: str, step_id: str, substep_id: str) -> str:
            judgment = self._manual_curve_judgment_for_ids(item_id, step_id, substep_id)
            if judgment == "accept":
                return "done"
            if judgment == "retest":
                return "broken"
            quality = self._history_curve_quality_for_ids(item_id, step_id, substep_id)
            if quality is None:
                return ""
            return "history" if quality.state in {"OK", "SUSPECT"} else "broken"

        def _sync_step_list_colored(self) -> None:
            item = vm.selected_item
            if item is None:
                self.step_list.clear()
                self.substep_list.clear()
                self.step_hint.setText("请先导入链路配置或导入默认配置。")
                return
            self.step_list.blockSignals(True)
            self.step_list.clear()
            for index, step in enumerate(item.steps, start=1):
                status = vm.step_progress_state(item.id, step.id)
                status = self._combined_step_status(item.id, step, status)
                list_item = QListWidgetItem(
                    f"{self._list_status_text(status)}\n{index}. {step.id}\n{_friendly_text(step.name)}"
                )
                self._apply_status_style(list_item, status)
                self.step_list.addItem(list_item)
            if item.steps:
                self._set_current_row_visible(self.step_list, vm.selected_step_index)
            self.step_list.blockSignals(False)
            current_step = vm.selected_step
            if current_step:
                active_step = self._active_prompt_view
                view_step = (
                    active_step
                    if active_step
                    and active_step.item_id == item.id
                    and active_step.step_id == current_step.id
                    and active_step.confirm_phase in {"start", "saved"}
                    else vm._step_view_data(current_step, vm.selected_step_index + 1, len(item.steps))
                )
                self._sync_step_view(view_step)
                self.step_hint.setText(f"当前步骤：{current_step.id} · {_friendly_text(current_step.name)}")
            else:
                self.substep_list.clear()
                self.step_hint.setText("当前校准项暂无步骤。")

        def _sync_step_view(self, step: StepViewData) -> None:
            self._current_step_view = step
            if step.confirm_phase in {"start", "saved"}:
                self._active_prompt_view = step
            substep_text = ""
            if step.substep_id:
                substep_text = f" | 小步骤 {step.substep_index}/{step.substep_total}: {_friendly_text(step.substep_name)}"
            self.step_title.setText(f"[{step.step_index}/{step.step_total}] {step.step_id} - {_friendly_text(step.step_name)}{substep_text}")
            self.step_status.setText(f"状态：{step.status}")
            total_substeps = max(step.item_total_substeps, 1)
            progress = int(step.item_completed_substeps / total_substeps * 100)
            self.step_progress.setValue(progress)
            self._sync_substep_list(step)
            detail_step = step
            if not step.substep_id:
                detail_step = self._step_view_for_substep_row(self.substep_list.currentRow(), step) or step
            self._sync_step_detail_views(detail_step)
            if step.confirm_phase == "saved":
                self._sync_saved_step_curve(step)
            elif step.confirm_phase == "start":
                self._sync_saved_step_curve(detail_step, activate=False)
                self._show_step_instruction_detail()
            else:
                self._sync_saved_step_curve(detail_step, activate=False)
                if self.step_detail_stack.currentIndex() != 1:
                    self._show_step_instruction_detail()
            inline_step = (
                step
                if step.confirm_phase in {"start", "saved"}
                else self._active_prompt_view
                if self._active_prompt_view
                and self._active_prompt_view.item_id == step.item_id
                and self._active_prompt_view.step_id == step.step_id
                else step
            )
            self._sync_inline_confirmation(inline_step)

        def _sync_step_detail_views(self, step: StepViewData) -> None:
            self.path_view.setHtml(_format_path_html(step))
            command_lines = list(step.link_commands)
            command_text = "\n".join(f"{index}. {command}" for index, command in enumerate(command_lines, start=1))
            measurement_text = f"测量 S 参数: {step.measurement_parameter or 'S21'}"
            if step.manual_instruction:
                step_label = f"STEP{step.substep_index}" if step.substep_index else "当前步骤"
                command_text = (command_text + "\n\n" if command_text else "") + f"{step_label} 操作说明:\n{step.manual_instruction}"
            self.command_view.setPlainText(f"{measurement_text}\n{command_text}" if command_text else f"{measurement_text}\n无链路命令")
            phase_text = ""
            if step.confirm_phase == "start":
                phase_text = "确认阶段: 开始前确认\n"
            elif step.confirm_phase == "saved":
                phase_text = "确认阶段: 数据保存完成确认\n"
            self.detail_view.setPlainText(
                phase_text
                + f"测量 S 参数: {step.measurement_parameter or 'S21'}\n"
                + f"输入端口: {_friendly_node_text(step.input_port)}\n"
                f"输出端口: {_friendly_node_text(step.output_port)}\n"
                f"原始输出: {_plain_join(step.raw_outputs)}\n"
                f"最终输出: {_plain_join(step.final_outputs)}\n"
                f"所需输入: {_plain_join(step.required_inputs)}\n"
                f"备注: {step.notes or '无'}"
            )

        def _step_view_for_substep_row(self, row: int, base_step: StepViewData | None = None) -> StepViewData | None:
            source_step = vm.selected_step
            if source_step is None:
                return None
            substeps = vm.substep_view_data(source_step)
            if not substeps:
                return None
            row = max(0, min(row, len(substeps) - 1))
            substep = substeps[row]
            base = base_step or self._current_step_view or vm._step_view_data(
                source_step,
                vm.selected_step_index + 1,
                len(vm.selected_item.steps) if vm.selected_item is not None else 0,
            )
            return StepViewData(
                item_id=base.item_id,
                item_name=base.item_name,
                step_id=base.step_id,
                step_name=base.step_name,
                step_index=base.step_index,
                step_total=base.step_total,
                status=base.status,
                manual_instruction=substep.manual_instruction or base.manual_instruction,
                route_ids=substep.route_ids or base.route_ids,
                link_commands=substep.link_commands or base.link_commands,
                input_port=substep.input_port or base.input_port,
                output_port=substep.output_port or base.output_port,
                raw_outputs=((substep.raw_output,) if substep.raw_output else base.raw_outputs),
                final_outputs=((substep.final_output,) if substep.final_output else base.final_outputs),
                required_inputs=substep.required_inputs or base.required_inputs,
                notes=substep.notes or base.notes,
                measurement_parameter=substep.measurement_parameter or base.measurement_parameter,
                substep_id=substep.id,
                substep_name=substep.name,
                substep_index=row + 1,
                substep_total=len(substeps),
                confirm_phase=base.confirm_phase if base.substep_id == substep.id else "",
                item_total_substeps=base.item_total_substeps,
                item_completed_substeps=base.item_completed_substeps,
                path_template=substep.path_template or base.path_template,
                path=substep.path or base.path,
                saved_files=base.saved_files if base.substep_id == substep.id else (),
            )

        def _on_substep_selected(self, row: int) -> None:
            detail_step = self._step_view_for_substep_row(row)
            if detail_step is None:
                return
            substep_text = (
                f" | 小步骤 {detail_step.substep_index}/{detail_step.substep_total}: "
                f"{_friendly_text(detail_step.substep_name)}"
            )
            self.step_title.setText(
                f"[{detail_step.step_index}/{detail_step.step_total}] "
                f"{detail_step.step_id} - {_friendly_text(detail_step.step_name)}{substep_text}"
            )
            self._sync_step_detail_views(detail_step)
            if detail_step.confirm_phase == "saved":
                self._sync_saved_step_curve(detail_step)
            elif detail_step.confirm_phase == "start":
                self._sync_saved_step_curve(detail_step, activate=False)
                self._show_step_instruction_detail()
            else:
                self._sync_saved_step_curve(detail_step, activate=False)
                if self.step_detail_stack.currentIndex() != 1:
                    self._show_step_instruction_detail()

        def _sync_substep_list(self, active_step: StepViewData | None = None) -> None:
            step = vm.selected_step
            self.substep_list.blockSignals(True)
            self.substep_list.clear()
            if step is None:
                self.substep_list.blockSignals(False)
                return
            item = vm.selected_item
            if item is None:
                self.substep_list.blockSignals(False)
                return
            item_id = item.id
            active_id = active_step.substep_id if active_step and active_step.step_id == step.id else ""
            phase = active_step.confirm_phase if active_step and active_id else ""
            current_row = -1
            for index, substep in enumerate(vm.substep_view_data(step), start=1):
                status = vm.substep_progress_state(item_id, step.id, substep.id)
                display_status = status
                if substep.id == active_id:
                    phase_text = "开始确认" if phase == "start" else "保存确认"
                    prefix = f"当前 {phase_text}"
                    current_row = index - 1
                elif status == "done":
                    prefix = "已完成"
                elif status == "running":
                    prefix = "进行中"
                else:
                    history_status = self._history_display_status_for_ids(item_id, step.id, substep.id)
                    judgment = self._manual_curve_judgment_for_ids(item_id, step.id, substep.id)
                    quality = self._history_curve_quality_for_ids(item_id, step.id, substep.id)
                    if judgment:
                        prefix = self._manual_curve_judgment_prefix(judgment)
                        display_status = history_status or ("history" if judgment == "accept" else "broken")
                    elif quality is not None:
                        prefix = self._history_quality_prefix(quality)
                        display_status = history_status or ("history" if quality.state in {"OK", "SUSPECT"} else "broken")
                    else:
                        prefix = "未开始"
                detail = substep.raw_output or substep.final_output
                detail_text = detail if detail else _friendly_text(substep.name)
                quality_text = self._history_quality_detail_text(item_id, step.id, substep.id)
                if quality_text:
                    detail_text = f"{detail_text}\n{quality_text}"
                list_item = QListWidgetItem(
                    f"{prefix}\nSTEP{index}. {substep.id}\n{_friendly_text(substep.name)}\n{detail_text}"
                )
                self._apply_status_style(list_item, display_status)
                self.substep_list.addItem(list_item)
                if substep.id == active_id:
                    current_row = index - 1
            if current_row < 0 and self.substep_list.count() > 0:
                current_row = 0
            if current_row >= 0:
                self._set_current_row_visible(self.substep_list, current_row)
            self.substep_list.blockSignals(False)

        def _sync_logs(self, *_args: Any) -> None:
            for panel in self.log_panels:
                records = vm.filtered_logs(level=panel.current_level())
                panel.set_records(records, self._format_log_entry)

        def _clear_logs(self, *_args: Any) -> None:
            vm.clear_logs()

        def _sync_overview(self, *_args: Any) -> None:
            overview = vm.overview
            if not overview:
                return
            self._sync_result_history_options()
            result_overview = self._result_overview_for_view(overview)
            self.result_summary.setPlainText(self._format_overview_summary(result_overview))
            self._sync_result_files(result_overview)
            self.result_session.setPlainText(self._format_session_detail(result_overview))
            self._sync_result_recompute_button(result_overview)
            link_box = "connected" if overview.get("link_box_connected") else "disconnected"
            vna = "connected" if overview.get("vna_connected") else "disconnected"
            sg = "connected" if overview.get("signal_generator_connected") else "disconnected"
            sa = "connected" if overview.get("spectrum_analyzer_connected") else "disconnected"
            self.connection_label.setText(f"网分: {vna} | 信号源: {sg} | 链路箱: {link_box} | 频谱仪: {sa}")
            self.status_label.setText(str(overview.get("status", "Ready")))
            self._sync_header_context()
            self._sync_start_button_state(str(overview.get("status", "Ready")))

        def _result_overview_for_view(self, overview: dict[str, Any]) -> dict[str, Any]:
            mode = str(self.result_view_combo.currentData() or "current")
            if mode == "current":
                result = dict(overview)
                result["result_view_label"] = "当前Session"
                return result
            if mode == "latest":
                result = dict(overview)
                latest_summary = self._latest_summary_for_selected_item()
                result["run_summary"] = latest_summary
                result["status"] = "Latest success" if latest_summary else "No latest success"
                result["result_view_label"] = "最新成功"
                return result
            if mode == "history":
                result = dict(overview)
                history_summary = self._selected_history_summary()
                result["run_summary"] = history_summary
                self._apply_summary_identity(result, history_summary)
                result["status"] = "History session" if history_summary else "No history session"
                result["result_view_label"] = "历史Session"
                return result
            if mode == "legacy":
                result = dict(overview)
                legacy_summary = self._legacy_summary_for_selected_item()
                result["run_summary"] = legacy_summary
                self._apply_summary_identity(result, legacy_summary)
                result["status"] = "Legacy readonly" if legacy_summary else "No legacy output"
                result["result_view_label"] = "旧版目录"
                return result
            result = dict(overview)
            result["result_view_label"] = "当前Session"
            return result

        @staticmethod
        def _apply_summary_identity(result: dict[str, Any], summary: dict[str, object]) -> None:
            if not summary:
                return
            item_id = str(summary.get("item_id") or "")
            if item_id:
                result["item_id"] = item_id
                result["item_name"] = str(summary.get("item_name") or item_id)

        def _sync_result_history_options(self) -> None:
            mode = str(self.result_view_combo.currentData() or "current")
            current_manifest = str(self.result_history_combo.currentData() or "")
            summaries = self._history_summaries_for_selected_item()
            self._history_session_summaries = summaries
            self.result_history_combo.blockSignals(True)
            self.result_history_combo.clear()
            selected_index = -1
            for index, summary in enumerate(summaries):
                manifest_file = str(summary.get("manifest_file", ""))
                label = self._history_session_label(summary)
                self.result_history_combo.addItem(label, manifest_file)
                if manifest_file and manifest_file == current_manifest:
                    selected_index = index
            if summaries and selected_index >= 0:
                self.result_history_combo.setCurrentIndex(selected_index)
            elif summaries:
                self.result_history_combo.setCurrentIndex(0)
            else:
                self.result_history_combo.addItem("无历史Session", "")
            self.result_history_combo.setEnabled(mode == "history" and bool(summaries))
            self.result_history_combo.blockSignals(False)

        def _selected_history_summary(self) -> dict[str, object]:
            manifest_file = str(self.result_history_combo.currentData() or "")
            if manifest_file:
                for summary in self._history_session_summaries:
                    if str(summary.get("manifest_file", "")) == manifest_file:
                        return summary
            return self._history_session_summaries[0] if self._history_session_summaries else {}

        def _history_summaries_for_selected_item(self) -> tuple[dict[str, object], ...]:
            item = vm.selected_item
            imported_workspace_root = self._result_workspace_root_from_input()
            if imported_workspace_root is not None:
                manifest_path = imported_workspace_root / "session_manifest.json"
                if manifest_path.exists():
                    try:
                        summary = load_session_summary_from_manifest(manifest_path)
                    except Exception:
                        summary = {}
                    if summary and (item is None or str(summary.get("item_id", "")) == item.id):
                        return (summary,)
                return list_session_summaries_from_workspace_root(
                    workspace_root=imported_workspace_root,
                    item_id=item.id if item is not None and vm.catalog.source_path != str(workspace_config_snapshot_path(imported_workspace_root)) else None,
                )
            if item is None:
                return ()
            current_summary = vm.run_summary_for_item(item.id)
            workspace_root = str(current_summary.get("workspace_root", "")).strip()
            project_code = str(current_summary.get("project_code", "")).strip()
            if workspace_root and project_code:
                return list_session_summaries_from_project_root(
                    project_root=Path(workspace_root) / "projects" / project_code,
                    item_id=item.id,
                )
            workspace = workspace_for_catalog(vm.catalog)
            return list_session_summaries(
                workspace=workspace,
                run=self._result_run_context(),
                item_id=item.id,
            )

        def _result_workspace_root_from_input(self) -> Path | None:
            text = self.result_workspace_input.text().strip()
            return Path(text) if text else None

        def _default_result_workspace_root(self) -> Path:
            item = vm.selected_item
            if item is not None:
                current_summary = vm.run_summary_for_item(item.id)
                workspace_root = str(current_summary.get("workspace_root", "")).strip()
                if workspace_root:
                    return Path(workspace_root)
            return workspace_for_catalog(vm.catalog).workspace_root

        def _browse_result_workspace(self) -> None:
            start_path = str(self._result_workspace_root_from_input() or self._default_result_workspace_root())
            selected = QFileDialog.getExistingDirectory(self, "选择校准工作空间目录", start_path)
            if not selected:
                return
            self.result_workspace_input.setText(selected)
            self._load_result_workspace()

        def _load_result_workspace(self) -> None:
            root = self._result_workspace_root_from_input()
            if root is None:
                self.result_curve_status.setText("未填写校准工作空间路径，使用当前配置默认 workspace。")
                self._sync_overview()
                return
            if not root.exists():
                self.result_curve_status.setText(f"校准工作空间不存在: {root}")
                self._sync_overview()
                return
            self.result_curve_status.setText(f"已加载校准工作空间: {root}")
            if self._looks_like_legacy_output_root(root):
                self.result_view_combo.setCurrentIndex(3)
                return
            if (root / "session_manifest.json").exists():
                summary = load_session_summary_from_manifest(root / "session_manifest.json")
                workspace_root = Path(str(summary.get("workspace_root") or ""))
                if workspace_root.exists():
                    self._load_catalog_snapshot_from_workspace(workspace_root)
            else:
                self._load_catalog_snapshot_from_workspace(root)
            if str(self.result_view_combo.currentData() or "") != "history":
                self.result_view_combo.setCurrentIndex(2)
            else:
                self._sync_overview()

        def _import_history_data(self) -> None:
            start_path = str(self._result_workspace_root_from_input() or self._default_result_workspace_root())
            selected = QFileDialog.getExistingDirectory(self, "选择历史校准 workspace 或 session 目录", start_path)
            if not selected:
                return
            root = Path(selected)
            try:
                summary = self._history_summary_from_path(root)
            except Exception as exc:
                self._history_data_summary = {}
                self._curve_quality_cache.clear()
                self._manual_curve_judgments.clear()
                self.btn_generate_resume_results.setEnabled(False)
                self.btn_result_generate_resume_results.setEnabled(False)
                self.history_data_status.setText("历史导入失败")
                self._show_modal_dialog(
                    title="导入历史数据失败",
                    message=str(exc),
                    buttons=(("确定", "ok", "center"),),
                    default_action="ok",
                    width=560,
                    height=220,
                )
                self._sync_substep_list(self._current_step_view)
                return
            if not summary:
                self._history_data_summary = {}
                self._curve_quality_cache.clear()
                self._manual_curve_judgments.clear()
                self.btn_generate_resume_results.setEnabled(False)
                self.btn_result_generate_resume_results.setEnabled(False)
                self.history_data_status.setText("未找到历史数据")
                self._show_modal_dialog(
                    title="未找到历史数据",
                    message="所选目录中没有找到当前校准项可用的历史 session 或旧版输出文件。",
                    buttons=(("确定", "ok", "center"),),
                    default_action="ok",
                    width=560,
                    height=220,
                )
                self._sync_substep_list(self._current_step_view)
                return
            self._history_data_summary = summary
            self._curve_quality_cache.clear()
            self._load_manual_curve_judgments(summary)
            self.btn_generate_resume_results.setEnabled(True)
            self.btn_result_generate_resume_results.setEnabled(True)
            self.result_workspace_input.setText(str(root))
            status = self._format_history_import_status(summary)
            self.history_data_status.setText(status)
            self.history_data_status.setToolTip(self._format_history_import_tooltip(summary))
            self._sync_item_list()
            self._sync_step_list_colored()
            self._sync_substep_list(self._current_step_view)
            detail_step = self._step_view_for_substep_row(self.substep_list.currentRow())
            if detail_step is not None:
                self._sync_saved_step_curve(detail_step, activate=False)
            self._show_modal_dialog(
                title="导入历史数据完成",
                message=f"{status}\n完整信息可在状态文本悬停查看。",
                buttons=(("确定", "ok", "center"),),
                default_action="ok",
                width=560,
                height=220,
            )

        def _history_summary_from_path(self, root: Path) -> dict[str, object]:
            item = vm.selected_item
            item_id = item.id if item is not None else None
            if (root / "session_manifest.json").exists():
                return load_session_summary_from_manifest(root / "session_manifest.json")
            if root.name.lower() == "latest" and item_id:
                return load_latest_summary_from_index(root / f"{item_id}.json")
            if (root / "workspace.json").exists() or (root / "projects").exists():
                self._load_catalog_snapshot_from_workspace(root)
                summaries = list_session_summaries_from_workspace_root(workspace_root=root, item_id=item_id)
                return summaries[0] if summaries else {}
            if self._looks_like_legacy_output_root(root):
                return load_legacy_output_summary(root, item_id=item_id)
            summaries = list_session_summaries_from_workspace_root(workspace_root=root, item_id=item_id)
            if summaries:
                return summaries[0]
            return {}

        @staticmethod
        def _format_history_import_status(summary: dict[str, object]) -> str:
            session_id = str(summary.get("session_id") or "历史数据")
            state = str(summary.get("state") or "-")
            raw_count = len(summary.get("raw_files", ()) or ())
            finished = str(summary.get("finished_at") or summary.get("started_at") or "").replace("T", " ")
            if "+" in finished:
                finished = finished.split("+", 1)[0]
            time_text = finished.split(" ")[-1] if " " in finished else finished
            compact_id = session_id[:8] if len(session_id) > 8 else session_id
            return f"历史: {compact_id} | {state} | raw {raw_count} | {time_text}".strip()

        @staticmethod
        def _format_history_import_tooltip(summary: dict[str, object]) -> str:
            session_id = str(summary.get("session_id") or "")
            state = str(summary.get("state") or "-")
            raw_count = len(summary.get("raw_files", ()) or ())
            loss_count = len(summary.get("loss_files", ()) or ())
            finished = str(summary.get("finished_at") or summary.get("started_at") or "")
            manifest = str(summary.get("manifest_file") or "")
            return (
                f"session: {session_id}\n"
                f"state: {state}\n"
                f"raw: {raw_count}, loss/final: {loss_count}\n"
                f"time: {finished}\n"
                f"manifest: {manifest}"
            )

        def _load_catalog_snapshot_from_workspace(self, root: Path) -> None:
            snapshot_path = workspace_config_snapshot_path(root)
            if not snapshot_path.exists():
                return
            current_path = str(Path(vm.catalog.source_path)) if vm.catalog.source_path else ""
            if current_path == str(snapshot_path):
                return
            try:
                vm.load_catalog(snapshot_path)
            except Exception as exc:
                self.result_curve_status.setText(f"已加载 workspace，但自动导入配置快照失败: {exc}")
                return
            self.result_curve_status.setText(f"已加载 workspace，并自动导入配置快照: {snapshot_path}")

        def _legacy_summary_for_selected_item(self) -> dict[str, object]:
            item = vm.selected_item
            root = self._result_workspace_root_from_input()
            if root is None:
                return {}
            return load_legacy_output_summary(root, item_id=item.id if item is not None else None)

        @staticmethod
        def _looks_like_legacy_output_root(root: Path) -> bool:
            candidate = root.parent if root.name.lower() in {"metadata", "raw", "loss"} else root
            return (
                (candidate / "metadata").exists()
                and not (candidate / "projects").exists()
                and not (candidate / "session_manifest.json").exists()
            )

        def _open_history_sessions_dir(self) -> None:
            root = self._result_workspace_root_from_input() or self._default_result_workspace_root()
            if str(self.result_view_combo.currentData() or "") == "legacy":
                path = root.parent if root.name.lower() in {"metadata", "raw", "loss"} else root
                if not path.exists():
                    self.result_curve_status.setText(f"旧版目录不存在: {path}")
                    return
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                self.result_curve_status.setText(f"已打开旧版目录: {path}")
                return
            project_code = self._result_run_context().normalized().project_code
            path = root / "projects" / project_code / "sessions"
            if not path.exists():
                self.result_curve_status.setText(f"历史目录不存在: {path}")
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            self.result_curve_status.setText(f"已打开历史目录: {path}")

        def _history_session_label(self, summary: dict[str, object]) -> str:
            finished = str(summary.get("finished_at") or summary.get("started_at") or "").replace("T", " ")
            if "+" in finished:
                finished = finished.split("+", 1)[0]
            state = str(summary.get("state") or "-")
            stage = _stage_display(str(summary.get("calibration_stage") or ""))
            run_label = str(summary.get("run_label") or "")
            session_id = str(summary.get("session_id") or "")
            tail = f"{stage}/{run_label}" if stage or run_label else session_id
            return f"{finished} | {state} | {tail}"

        def _latest_summary_for_selected_item(self) -> dict[str, object]:
            item = vm.selected_item
            if item is None:
                return {}
            imported_workspace_root = self._result_workspace_root_from_input()
            if imported_workspace_root is not None:
                project_code = self._result_run_context().normalized().project_code
                latest_path = imported_workspace_root / "projects" / project_code / "latest" / f"{item.id}.json"
                return load_latest_summary_from_index(latest_path)
            current_summary = vm.run_summary_for_item(item.id)
            workspace_root = str(current_summary.get("workspace_root", "")).strip()
            project_code = str(current_summary.get("project_code", "")).strip()
            if workspace_root and project_code:
                latest_path = Path(workspace_root) / "projects" / project_code / "latest" / f"{item.id}.json"
                latest = load_latest_summary_from_index(latest_path)
                if latest:
                    return latest
            workspace = workspace_for_catalog(vm.catalog)
            return load_latest_summary(workspace=workspace, run=self._result_run_context(), item_id=item.id)

        def _result_run_context(self) -> CalibrationRunContext:
            stage_code = self.calibration_stage_combo.currentData()
            return CalibrationRunContext(
                project_code=self.project_code_input.text().strip() or "DEFAULT_PROJECT",
                calibration_stage=str(stage_code or self.calibration_stage_combo.currentText()).strip() or "initial",
                run_label=self.run_label_input.text().strip() or "R01",
            )

        def _sync_result_files(self, overview: dict[str, Any]) -> None:
            selected_path = self._selected_result_path()
            rows = self._result_rows_from_overview(overview)
            self._result_rows = rows
            self.result_file_table.blockSignals(True)
            self.result_file_table.setRowCount(len(rows))
            selected_row = -1
            for row_index, row in enumerate(rows):
                values = [row["kind"], row["name"], row["size"], row["modified"], row["path"]]
                for column_index, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, row["path"])
                    if row["kind"] == "FINAL":
                        item.setForeground(QBrush(QColor("#256d45")))
                    elif row["kind"] == "RAW":
                        item.setForeground(QBrush(QColor("#234f84")))
                    elif row["kind"] == "METADATA":
                        item.setForeground(QBrush(QColor("#695a2d")))
                    self.result_file_table.setItem(row_index, column_index, item)
                if row["path"] == selected_path:
                    selected_row = row_index
            self.result_file_table.blockSignals(False)
            if rows:
                self.result_file_table.selectRow(selected_row if selected_row >= 0 else 0)
            else:
                self.result_file_table.clearSelection()
                self._clear_result_curve("当前校准项还没有生成文件。")

        def _result_rows_from_overview(self, overview: dict[str, Any]) -> list[dict[str, str]]:
            run_summary = overview.get("run_summary") or {}
            if not isinstance(run_summary, dict):
                return []
            file_groups = (
                ("FINAL", "loss_files"),
                ("RAW", "raw_files"),
                ("METADATA", "metadata_files"),
            )
            rows: list[dict[str, str]] = []
            for kind, key in file_groups:
                for raw_path in run_summary.get(key, ()) or ():
                    path = Path(str(raw_path))
                    exists = path.exists()
                    stat = path.stat() if exists else None
                    rows.append(
                        {
                            "kind": kind,
                            "name": path.name,
                            "size": self._format_file_size(stat.st_size) if stat else "缺失",
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S") if stat else "",
                            "path": str(path),
                        }
                    )
            manifest_file = str(run_summary.get("manifest_file") or "").strip()
            if manifest_file:
                path = Path(manifest_file)
                exists = path.exists()
                stat = path.stat() if exists else None
                rows.append(
                    {
                        "kind": "MANIFEST",
                        "name": path.name,
                        "size": self._format_file_size(stat.st_size) if stat else "缺失",
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S") if stat else "",
                        "path": str(path),
                    }
                )
            return rows

        @staticmethod
        def _format_file_size(size: int) -> str:
            if size < 1024:
                return f"{size} B"
            if size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            return f"{size / (1024 * 1024):.1f} MB"

        def _selected_result_path(self) -> str:
            selected_rows = self.result_file_table.selectionModel().selectedRows()
            if not selected_rows:
                return ""
            item = self.result_file_table.item(selected_rows[0].row(), 4)
            return str(item.data(Qt.ItemDataRole.UserRole) or item.text()) if item is not None else ""

        def _copy_selected_result_path(self, *_args: Any) -> None:
            path = self._selected_result_path()
            if not path:
                self.result_curve_status.setText("请先选择一个结果文件。")
                return
            QApplication.clipboard().setText(path)
            self.result_curve_status.setText(f"已复制路径: {path}")

        def _open_selected_result_dir(self, *_args: Any) -> None:
            path = self._selected_result_path()
            if not path:
                self.result_curve_status.setText("请先选择一个结果文件。")
                return
            directory = Path(path).parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

        def _open_result_context_dir(self, key: str, *_args: Any) -> None:
            overview = self._result_overview_for_view(vm.overview)
            run_summary = overview.get("run_summary") or {}
            if not isinstance(run_summary, dict) or not run_summary:
                self.result_curve_status.setText("当前没有可打开的校准文件空间。")
                return
            if key == "project_root":
                session_root = str(run_summary.get("session_root") or "").strip()
                path = Path(session_root).parents[1] if session_root and len(Path(session_root).parents) >= 2 else None
            else:
                raw_path = str(run_summary.get(key) or "").strip()
                path = Path(raw_path) if raw_path else None
            if path is None or not path.exists():
                self.result_curve_status.setText(f"目录不存在: {path}")
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            self.result_curve_status.setText(f"已打开目录: {path}")

        def _export_result_summary(self, *_args: Any) -> None:
            overview = self._result_overview_for_view(vm.overview)
            default_name = f"{overview.get('item_id', 'calibration')}_result_summary.txt" if overview else "calibration_result_summary.txt"
            path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "导出当前 session 输出摘要",
                default_name,
                "Text Files (*.txt);;All Files (*)",
            )
            if not path:
                return
            lines = [
                self._format_overview_summary(overview),
                "",
                self._format_session_detail(overview),
                "",
                "generated_files:",
            ]
            for row in self._result_rows:
                lines.append(f"{row['kind']}\t{row['name']}\t{row['size']}\t{row['modified']}\t{row['path']}")
            try:
                Path(path).write_text("\n".join(lines), encoding="utf-8")
            except Exception as exc:
                self.result_curve_status.setText(f"导出摘要失败: {exc}")
                return
            self.result_curve_status.setText(f"已导出摘要: {path}")

        def _show_step_instruction_detail(self) -> None:
            self.step_detail_stack.setCurrentIndex(0)

        def _sync_saved_step_curve(self, step: StepViewData, *, activate: bool = True) -> None:
            if activate:
                self.step_detail_stack.setCurrentIndex(1)
            self._current_curve_step_key = self._step_key(step)
            self._saved_curve_measurement_parameter = step.measurement_parameter or "S21"
            path = self._curve_path_for_step(step)
            self._saved_curve_path = path
            if path is None:
                self._clear_saved_step_curve(f"STEP{step.substep_index}. {_friendly_text(step.substep_name)} 暂无可预览曲线。")
                return
            try:
                curve_data = self._load_csv_curve_data(path)
            except Exception as exc:
                self._clear_saved_step_curve(f"读取步骤曲线失败: {exc}")
                return
            self._saved_curve_data = curve_data
            self.saved_curve_column.blockSignals(True)
            self.saved_curve_column.clear()
            self.saved_curve_column.addItems(tuple(curve_data.keys()))
            self.saved_curve_column.setEnabled(bool(curve_data))
            self.btn_saved_curve_autorange.setEnabled(bool(curve_data) and pg is not None)
            self.saved_curve_column.blockSignals(False)
            self._sync_manual_curve_judgment_combo(step, enabled=bool(curve_data))
            self.btn_use_history_curve.setEnabled(bool(curve_data) and self._history_curve_path_for_step(step) is not None)
            self.btn_retest_substep.setEnabled(bool(step.substep_id))
            if curve_data:
                self._plot_saved_step_curve()
            else:
                self._clear_saved_step_curve(f"{path.name} 没有可绘制的 dB 数据列。")

        def _sync_manual_curve_judgment_combo(self, step: StepViewData, *, enabled: bool) -> None:
            judgment = self._manual_curve_judgments.get(self._step_key(step), "")
            self.manual_curve_judgment_combo.blockSignals(True)
            self.manual_curve_judgment_combo.setEnabled(enabled)
            target_index = max(0, self.manual_curve_judgment_combo.findData(judgment))
            self.manual_curve_judgment_combo.setCurrentIndex(target_index)
            self.manual_curve_judgment_combo.blockSignals(False)

        @staticmethod
        def _saved_curve_path_for_step(step: StepViewData) -> Path | None:
            for raw_path in step.saved_files:
                path = Path(raw_path)
                if path.suffix.lower() == ".csv" and path.exists():
                    return path
            return None

        def _curve_path_for_step(self, step: StepViewData) -> Path | None:
            return self._saved_curve_path_for_step(step) or self._history_curve_path_for_step(step)

        def _history_curve_path_for_step(self, step: StepViewData) -> Path | None:
            return self._history_curve_path_for_ids(step.item_id, step.step_id, step.substep_id)

        def _history_curve_path_for_ids(self, item_id: str, step_id: str, substep_id: str) -> Path | None:
            if not self._history_data_summary:
                return None
            expected_name = f"{item_id}_{step_id}_{self._safe_measurement_token(substep_id)}.csv"
            for raw_path in self._history_file_candidates("raw_files"):
                if raw_path.name == expected_name:
                    return raw_path
            return None

        def _history_curve_quality_for_ids(self, item_id: str, step_id: str, substep_id: str) -> CurveQuality | None:
            path = self._history_curve_path_for_ids(item_id, step_id, substep_id)
            if path is None:
                return None
            return self._curve_quality(path)

        def _curve_quality(self, path: Path) -> CurveQuality:
            key = str(path)
            quality = self._curve_quality_cache.get(key)
            if quality is None:
                quality = analyze_curve_csv(path)
                self._curve_quality_cache[key] = quality
            return quality

        @staticmethod
        def _history_quality_prefix(quality: CurveQuality) -> str:
            if quality.state == "OK":
                return "已有历史"
            if quality.state == "SUSPECT":
                return "历史可疑"
            if quality.state == "NO_CURVE":
                return "无曲线"
            return "曲线异常"

        def _history_quality_detail_text(self, item_id: str, step_id: str, substep_id: str) -> str:
            quality = self._history_curve_quality_for_ids(item_id, step_id, substep_id)
            if quality is None:
                return ""
            judgment = self._manual_curve_judgment_for_ids(item_id, step_id, substep_id)
            if judgment:
                return f"{quality.label} · {self._manual_curve_judgment_text(judgment)} · {quality.point_count}点"
            action = "待读取后人工判断" if quality.is_usable else "需重测或重新导入"
            return f"{quality.label} · {action} · {quality.point_count}点"

        def _step_key_for_ids(self, item_id: str, step_id: str, substep_id: str) -> str:
            return f"{item_id}:{step_id}:{substep_id}"

        def _step_key(self, step: StepViewData) -> str:
            return self._step_key_for_ids(step.item_id, step.step_id, step.substep_id)

        def _manual_curve_judgment_for_ids(self, item_id: str, step_id: str, substep_id: str) -> str:
            return self._manual_curve_judgments.get(self._step_key_for_ids(item_id, step_id, substep_id), "")

        @staticmethod
        def _manual_curve_judgment_text(judgment: str) -> str:
            return {
                "accept": "人工判定正常，可沿用",
                "retest": "人工判定异常，需重测",
            }.get(judgment, "未判定")

        @staticmethod
        def _manual_curve_judgment_prefix(judgment: str) -> str:
            return {
                "accept": "人工正常",
                "retest": "需重测",
            }.get(judgment, "未判定")

        def _on_manual_curve_judgment_changed(self) -> None:
            if not self._current_curve_step_key:
                return
            judgment = str(self.manual_curve_judgment_combo.currentData() or "")
            if judgment:
                self._manual_curve_judgments[self._current_curve_step_key] = judgment
            else:
                self._manual_curve_judgments.pop(self._current_curve_step_key, None)
            self._save_manual_curve_judgments()
            self._sync_item_list()
            self._sync_step_list_colored()
            self._sync_substep_list(self._current_step_view)

        def _resume_decision_path(self, summary: dict[str, object] | None = None) -> Path | None:
            source = summary or self._history_data_summary
            if not source:
                return None
            item_id = str(source.get("item_id") or (vm.selected_item.id if vm.selected_item is not None else "")).strip()
            source_id = str(source.get("session_id") or source.get("latest_session_id") or "history").strip()
            if not item_id:
                return None
            workspace = workspace_for_catalog(vm.catalog)
            project_code = self._result_run_context().normalized().project_code
            name = f"{self._safe_measurement_token(item_id)}_{self._safe_measurement_token(source_id)}.json"
            return workspace.workspace_root / "projects" / project_code / "resume_decisions" / name

        def _load_manual_curve_judgments(self, summary: dict[str, object]) -> None:
            self._manual_curve_judgments.clear()
            path = self._resume_decision_path(summary)
            if path is None or not path.exists():
                return
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return
            judgments = payload.get("judgments", {}) if isinstance(payload, dict) else {}
            if isinstance(judgments, dict):
                self._manual_curve_judgments.update(
                    {
                        str(key): str(value)
                        for key, value in judgments.items()
                        if str(value) in {"accept", "retest"}
                    }
                )

        def _save_manual_curve_judgments(self) -> None:
            path = self._resume_decision_path()
            if path is None:
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": "catr-resume-decisions.v1",
                "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "source": {
                    "workspace_root": str(self._history_data_summary.get("workspace_root") or ""),
                    "session_id": str(self._history_data_summary.get("session_id") or ""),
                    "manifest_file": str(self._history_data_summary.get("manifest_file") or ""),
                    "item_id": str(self._history_data_summary.get("item_id") or ""),
                },
                "judgments": dict(sorted(self._manual_curve_judgments.items())),
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        def _history_file_candidates(self, key: str) -> tuple[Path, ...]:
            paths: list[Path] = []
            session_root = Path(str(self._history_data_summary.get("session_root") or ""))
            workspace_root = Path(str(self._history_data_summary.get("workspace_root") or ""))
            for raw_path in self._history_data_summary.get(key, ()) or ():
                path = Path(str(raw_path))
                if not path.is_absolute():
                    candidates = [path]
                    if session_root:
                        candidates.append(session_root / path)
                    if workspace_root:
                        candidates.append(workspace_root / path)
                    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
                if path.suffix.lower() == ".csv" and path.exists():
                    paths.append(path)
            return tuple(paths)

        @staticmethod
        def _safe_measurement_token(value: str) -> str:
            return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip()) or "MEAS"

        def _plot_saved_step_curve(self, *_args: Any) -> None:
            column = self.saved_curve_column.currentText()
            if not column or column not in self._saved_curve_data:
                return
            x_values, y_values = self._saved_curve_data[column]
            path = self._saved_curve_path or Path("saved_curve.csv")
            quality = self._curve_quality(path) if path.exists() else None
            quality_text = f"读取状态: {quality.label}; {quality.reason}" if quality is not None else "读取状态: 未知"
            judgment_text = self._manual_curve_judgment_text(self._manual_curve_judgments.get(self._current_curve_step_key, ""))
            measurement_parameter = getattr(self, "_saved_curve_measurement_parameter", "S21")
            self.saved_curve_status.setText(
                f"{path.name} | {column} | {len(x_values)} 点 | 测量 {measurement_parameter}\n"
                f"{quality_text}\n人工判断: {judgment_text}"
            )
            if pg is None:
                self.saved_curve_plot.setPlainText(
                    f"{path.name}\n{column}\n测量: {measurement_parameter}\n点数: {len(x_values)}\n"
                    f"X(GHz): {x_values[0]:.6g} ... {x_values[-1]:.6g}\n"
                    f"Y(dB): {np.nanmin(y_values):.3f} ... {np.nanmax(y_values):.3f}"
                )
                return
            self.saved_curve_plot.clear()
            self.saved_curve_plot.plot(x_values, y_values, pen=pg.mkPen("#2f6f9f", width=2), name=column)
            self.saved_curve_plot.setTitle(f"{path.name} - {column} - 测量 {measurement_parameter}")
            self.saved_curve_plot.enableAutoRange(axis="xy", enable=True)

        def _autorange_saved_step_curve(self, *_args: Any) -> None:
            if not self._saved_curve_data:
                self.saved_curve_status.setText("当前没有可自适应的保存曲线。")
                return
            if pg is None:
                self.saved_curve_status.setText("未安装 pyqtgraph，无法执行曲线自适应。")
                return
            self.saved_curve_plot.enableAutoRange(axis="xy", enable=True)
            self.saved_curve_plot.autoRange(padding=0.08)

        def _clear_saved_step_curve(self, message: str) -> None:
            self._saved_curve_data = {}
            self._saved_curve_path = None
            self._saved_curve_measurement_parameter = "S21"
            self.saved_curve_column.blockSignals(True)
            self.saved_curve_column.clear()
            self.saved_curve_column.setEnabled(False)
            self.saved_curve_column.blockSignals(False)
            self.manual_curve_judgment_combo.blockSignals(True)
            self.manual_curve_judgment_combo.setCurrentIndex(0)
            self.manual_curve_judgment_combo.setEnabled(False)
            self.manual_curve_judgment_combo.blockSignals(False)
            self.btn_use_history_curve.setEnabled(False)
            self.btn_retest_substep.setEnabled(bool(self._current_curve_step_key))
            self.btn_saved_curve_autorange.setEnabled(False)
            self.saved_curve_status.setText(message)
            if pg is None:
                self.saved_curve_plot.setPlainText(message)
            else:
                self.saved_curve_plot.clear()

        def _use_selected_history_curve(self) -> None:
            detail_step = self._step_view_for_substep_row(self.substep_list.currentRow())
            if detail_step is None:
                self.saved_curve_status.setText("请先选择一个细分步骤。")
                return
            if self._history_curve_path_for_step(detail_step) is None:
                self.saved_curve_status.setText("当前细分步骤没有可沿用的历史曲线。")
                return
            index = self.manual_curve_judgment_combo.findData("accept")
            if index >= 0:
                self.manual_curve_judgment_combo.setCurrentIndex(index)
            self.saved_curve_status.setText(
                f"已标记沿用历史数据: STEP{detail_step.substep_index}. {_friendly_text(detail_step.substep_name)}"
            )
            self._sync_substep_list(self._current_step_view)

        def _retest_selected_substep(self) -> None:
            detail_step = self._step_view_for_substep_row(self.substep_list.currentRow())
            if detail_step is None:
                self.saved_curve_status.setText("请先选择一个细分步骤。")
                return
            try:
                summary = vm.run_single_substep(
                    detail_step.step_id,
                    detail_step.substep_id,
                    self._history_conditioned_vna_run_settings(),
                    history_summary=self._history_data_summary or None,
                )
            except Exception as exc:
                self._show_modal_dialog(
                    title="重测当前细分步骤失败",
                    message=str(exc),
                    buttons=(("确定", "ok", "center"),),
                    default_action="ok",
                    width=560,
                    height=220,
                )
                return
            self._history_data_summary = self._merged_history_summary_with_current(summary)
            self._curve_quality_cache.clear()
            self._manual_curve_judgments.pop(self._step_key(detail_step), None)
            self._save_manual_curve_judgments()
            self._sync_substep_list(self._current_step_view)
            self._sync_item_list()
            self._sync_step_list_colored()
            refreshed_step = self._step_view_for_substep_row(self.substep_list.currentRow()) or detail_step
            self._sync_saved_step_curve(refreshed_step)
            self._sync_overview()

        def _history_conditioned_vna_run_settings(self) -> dict[str, Any]:
            settings = self._vna_run_settings()
            history_settings = self._history_data_summary.get("measurement_settings") if self._history_data_summary else None
            if not isinstance(history_settings, dict):
                return settings
            for key in ("start_hz", "stop_hz", "points", "if_bandwidth_hz", "parameter", "feed", "horn"):
                if key in history_settings and str(history_settings[key]).strip():
                    settings[key] = history_settings[key]
            return settings

        def _generate_resume_results(self) -> None:
            source_summary = self._history_data_summary or self._selected_result_recompute_summary()
            if not source_summary:
                self.saved_curve_status.setText("请先导入历史数据。")
                self.result_curve_status.setText("请先导入历史数据。")
                return
            try:
                summary = vm.generate_resume_results(
                    source_summary,
                    self._manual_curve_judgments,
                    self._vna_run_settings(),
                )
            except Exception as exc:
                self._show_modal_dialog(
                    title="生成/更新结果失败",
                    message=str(exc),
                    buttons=(("确定", "ok", "center"),),
                    default_action="ok",
                    width=560,
                    height=220,
                )
                return
            self._history_data_summary = self._merged_history_summary_with_current(summary)
            self._curve_quality_cache.clear()
            state = str(summary.get("state") or "")
            warnings = tuple(str(value) for value in summary.get("resume_compatibility_warnings", ()) or ())
            warning_text = f"\n异常提醒: {len(warnings)} 项; " + "; ".join(warnings[:3]) if warnings else ""
            self.history_data_status.setText(f"续测结果: {state}")
            self.saved_curve_status.setText(
                f"续测结果已生成: {state}\n"
                f"raw: {len(summary.get('raw_files', ()) or ())}; "
                f"final/loss: {len(summary.get('loss_files', ()) or ())}"
                f"{warning_text}"
            )
            self.result_curve_status.setText(
                f"续测结果已重新计算: {state}; "
                f"raw {len(summary.get('raw_files', ()) or ())}; "
                f"final/loss {len(summary.get('loss_files', ()) or ())}"
            )
            self._sync_substep_list(self._current_step_view)
            self._sync_item_list()
            self._sync_step_list_colored()
            self._sync_overview()
            self.tabs.setCurrentWidget(self.result_page)

        def _selected_result_recompute_summary(self) -> dict[str, object]:
            mode = str(self.result_view_combo.currentData() or "current")
            if mode == "history":
                return self._selected_history_summary()
            if mode == "latest":
                return self._latest_summary_for_selected_item()
            root = self._result_workspace_root_from_input()
            if root is not None and (root / "session_manifest.json").exists():
                try:
                    return load_session_summary_from_manifest(root / "session_manifest.json")
                except Exception:
                    return {}
            return {}

        def _sync_result_recompute_button(self, overview: dict[str, Any] | None = None) -> None:
            summary = self._history_data_summary or self._selected_result_recompute_summary()
            enabled = bool(
                summary
                and str(summary.get("state") or "").strip().upper() != "LEGACY_READONLY"
                and str(summary.get("session_root") or "").strip()
                and str(summary.get("manifest_file") or "").strip()
            )
            self.btn_result_generate_resume_results.setEnabled(enabled)
            self.btn_generate_resume_results.setEnabled(bool(self._history_data_summary))
            if overview is not None and not enabled and str(self.result_view_combo.currentData() or "") == "legacy":
                self.result_curve_status.setText("旧版目录为只读结果，不能重新计算。请加载 workspace/session 历史数据。")

        def _merged_history_summary_with_current(self, current_summary: dict[str, object]) -> dict[str, object]:
            if not self._history_data_summary:
                return current_summary
            if str(current_summary.get("session_id") or "") == str(self._history_data_summary.get("session_id") or ""):
                return current_summary
            merged = dict(self._history_data_summary)
            for key in ("raw_files", "loss_files", "metadata_files"):
                current_paths = tuple(str(path) for path in current_summary.get(key, ()) or ())
                old_paths = tuple(str(path) for path in self._history_data_summary.get(key, ()) or ())
                current_names = {Path(path).name for path in current_paths}
                merged[key] = (*current_paths, *(path for path in old_paths if Path(path).name not in current_names))
            merged["state"] = "RESUME_MIXED"
            merged["last_event"] = str(current_summary.get("last_event") or "single_substep_retest")
            merged["latest_retest_session_id"] = str(current_summary.get("session_id") or "")
            old_retested = {str(key) for key in self._history_data_summary.get("current_retested_substep_ids", ()) or ()}
            new_retested = {str(key) for key in current_summary.get("completed_substep_ids", ()) or ()}
            merged["current_retested_substep_ids"] = tuple(sorted(old_retested | new_retested))
            return merged

        def _sync_result_curve(self, *_args: Any) -> None:
            path_text = self._selected_result_path()
            if not path_text:
                self._clear_result_curve("请选择一个结果文件。")
                return
            path = Path(path_text)
            if path.suffix.lower() != ".csv":
                self._clear_result_curve(f"{path.name} 不是 CSV 文件，仅显示文件信息。")
                return
            try:
                curve_data = self._load_csv_curve_data(path)
            except Exception as exc:
                self._clear_result_curve(f"读取曲线失败: {exc}")
                return
            self._current_curve_data = curve_data
            self.result_curve_column.blockSignals(True)
            self.result_curve_column.clear()
            self.result_curve_column.addItems(tuple(curve_data.keys()))
            self.result_curve_column.setEnabled(bool(curve_data))
            self.btn_result_curve_autorange.setEnabled(bool(curve_data) and pg is not None)
            self.result_curve_column.blockSignals(False)
            if curve_data:
                self._plot_selected_result_curve()
            else:
                self._clear_result_curve(f"{path.name} 没有可绘制的 dB 数据列。")

        def _load_csv_curve_data(self, path: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                fieldnames = tuple(reader.fieldnames or ())
            if not fieldnames:
                raise ValueError("CSV 没有表头。")
            freq_column = self._detect_frequency_column(fieldnames)
            if not freq_column:
                raise ValueError("未找到频率列。")
            x_raw = np.asarray([self._to_float(row.get(freq_column)) for row in rows], dtype=float)
            valid_x = np.isfinite(x_raw)
            if not np.any(valid_x):
                raise ValueError("频率列没有有效数字。")
            x_ghz = self._frequency_to_ghz(freq_column, x_raw)
            y_columns = self._detect_curve_columns(fieldnames, freq_column)
            curves: dict[str, tuple[np.ndarray, np.ndarray]] = {}
            for column in y_columns:
                y = np.asarray([self._to_float(row.get(column)) for row in rows], dtype=float)
                valid = np.isfinite(x_ghz) & np.isfinite(y)
                if np.any(valid):
                    curves[column] = (x_ghz[valid], y[valid])
            return curves

        @staticmethod
        def _detect_frequency_column(fieldnames: tuple[str, ...]) -> str:
            normalized = {name.strip().lower(): name for name in fieldnames}
            for candidate in ("freq_hz", "frequency_hz", "freq", "frequency", "freq_ghz", "frequency_ghz"):
                if candidate in normalized:
                    return normalized[candidate]
            for name in fieldnames:
                if "freq" in name.strip().lower():
                    return name
            return ""

        @staticmethod
        def _detect_curve_columns(fieldnames: tuple[str, ...], freq_column: str) -> list[str]:
            priority = ("value_db", "raw_s21_db", "raw_s12_db", "gain_db", "loss_db", "s21_db", "s12_db", "s11_db", "s22_db")
            lower_to_name = {name.strip().lower(): name for name in fieldnames}
            columns = [lower_to_name[name] for name in priority if name in lower_to_name and lower_to_name[name] != freq_column]
            for name in fieldnames:
                lower = name.strip().lower()
                if name == freq_column or name in columns:
                    continue
                if lower.endswith("_db") or lower.endswith("_dbi") or any(parameter in lower for parameter in ("s11", "s12", "s21", "s22")):
                    columns.append(name)
            return columns

        @staticmethod
        def _measurement_parameter_from_csv(path: Path) -> str:
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    row = next(reader, None)
            except Exception:
                return ""
            if not row:
                return ""
            for key in ("param", "parameter", "s_parameter", "measurement_parameter"):
                value = str(row.get(key) or "").strip().upper()
                if value:
                    return value
            return ""

        @staticmethod
        def _frequency_to_ghz(column: str, values: np.ndarray) -> np.ndarray:
            lower = column.strip().lower()
            if "ghz" in lower:
                return values
            if "mhz" in lower:
                return values / 1000.0
            return values / 1e9 if np.nanmax(values) > 1e6 else values

        @staticmethod
        def _to_float(value: Any) -> float:
            try:
                return float(str(value).strip())
            except Exception:
                return float("nan")

        def _plot_selected_result_curve(self, *_args: Any) -> None:
            column = self.result_curve_column.currentText()
            if not column or column not in self._current_curve_data:
                return
            x_values, y_values = self._current_curve_data[column]
            path = Path(self._selected_result_path())
            measurement_parameter = self._measurement_parameter_from_csv(path)
            measurement_text = f" | 测量 {measurement_parameter}" if measurement_parameter else ""
            self.result_curve_status.setText(f"{path.name} | {column} | {len(x_values)} 点{measurement_text}")
            if pg is None:
                self.result_curve_plot.setPlainText(
                    f"{path.name}\n{column}\n"
                    f"{'测量: ' + measurement_parameter + chr(10) if measurement_parameter else ''}"
                    f"点数: {len(x_values)}\n"
                    f"X(GHz): {x_values[0]:.6g} ... {x_values[-1]:.6g}\n"
                    f"Y(dB): {np.nanmin(y_values):.3f} ... {np.nanmax(y_values):.3f}"
                )
                return
            self.result_curve_plot.clear()
            self.result_curve_plot.plot(x_values, y_values, pen=pg.mkPen("#2f6f9f", width=2), name=column)
            title_suffix = f" - 测量 {measurement_parameter}" if measurement_parameter else ""
            self.result_curve_plot.setTitle(f"{path.name} - {column}{title_suffix}")
            self._autorange_result_curve()

        def _autorange_result_curve(self, *_args: Any) -> None:
            if not self._current_curve_data:
                self.result_curve_status.setText("当前没有可自适应的曲线。")
                return
            if pg is None:
                self.result_curve_status.setText("未安装 pyqtgraph，无法执行曲线自适应。")
                return
            self.result_curve_plot.enableAutoRange(axis="xy", enable=True)
            self.result_curve_plot.autoRange(padding=0.08)

        def _clear_result_curve(self, message: str) -> None:
            self._current_curve_data = {}
            self.result_curve_column.blockSignals(True)
            self.result_curve_column.clear()
            self.result_curve_column.setEnabled(False)
            self.result_curve_column.blockSignals(False)
            self.btn_result_curve_autorange.setEnabled(False)
            self.result_curve_status.setText(message)
            if pg is None:
                self.result_curve_plot.setPlainText(message)
            else:
                self.result_curve_plot.clear()

        def _on_state_changed(self, state: str) -> None:
            self.step_status.setText(f"状态：{state}")
            self._sync_start_button_state(state)
            if str(state).strip().upper() in {"DONE", "CANCELLED", "FAILED"} or str(state).upper().startswith("ERROR"):
                self._active_prompt_view = None
                self._hide_inline_confirmation()

        def _sync_command_response(self, response: str) -> None:
            self.status_label.setText(f"命令响应: {response}")

        def _sync_band_options(self, preferred_feed: str | None = None, preferred_horn: str | None = None) -> None:
            entries = band_entries_from_config(vm.catalog.band_config)
            default_feed, default_horn = default_feed_horn_from_config(vm.catalog.band_config)
            current_feed = (preferred_feed or self.feed_combo.currentText() or default_feed).strip().upper()
            feeds = sorted({str(entry["feed"]) for entry in entries})
            self.feed_combo.blockSignals(True)
            self.feed_combo.clear()
            self.feed_combo.addItems(feeds)
            if current_feed in feeds:
                self.feed_combo.setCurrentText(current_feed)
            elif default_feed in feeds:
                self.feed_combo.setCurrentText(default_feed)
            elif feeds:
                self.feed_combo.setCurrentIndex(0)
            self.feed_combo.blockSignals(False)
            self._sync_horn_options(self.feed_combo.currentText(), preferred_horn or default_horn)

        def _sync_horn_options(self, feed: str, preferred_horn: str | None = None) -> None:
            current = (preferred_horn or self.horn_combo.currentText()).strip().upper()
            selected_feed = feed.strip().upper()
            entries = band_entries_from_config(vm.catalog.band_config)
            horns = sorted(
                {
                    str(entry["horn"])
                    for entry in entries
                    if str(entry["feed"]).strip().upper() == selected_feed
                }
            )
            if not horns:
                horns = sorted({str(entry["horn"]) for entry in entries})
            self.horn_combo.blockSignals(True)
            self.horn_combo.clear()
            self.horn_combo.addItems(horns)
            if current in horns:
                self.horn_combo.setCurrentText(current)
            elif horns:
                self.horn_combo.setCurrentIndex(0)
            self.horn_combo.blockSignals(False)
            self._apply_band_sweep_range()

        def _apply_band_sweep_range(self) -> None:
            entry = self._selected_band_entry()
            if not entry:
                return
            self._apply_band_horn_gain_file(entry)
            if "start_ghz" not in entry or "stop_ghz" not in entry:
                return
            for panel in self.command_panels:
                if panel.device_key != "vna":
                    continue
                panel.vna_start_ghz.blockSignals(True)
                panel.vna_stop_ghz.blockSignals(True)
                panel.vna_start_ghz.setValue(float(entry["start_ghz"]))
                panel.vna_stop_ghz.setValue(float(entry["stop_ghz"]))
                panel.vna_start_ghz.blockSignals(False)
                panel.vna_stop_ghz.blockSignals(False)
                panel._refresh_vna_points_label()
                return

        def _apply_band_horn_gain_file(self, entry: dict[str, Any]) -> None:
            horn_gain_file = str(entry.get("horn_gain_file", "")).strip()
            if not horn_gain_file:
                return
            path = resolve_data_file(horn_gain_file, source_path=vm.catalog.source_path)
            self.horn_gain_file_input.setText(str(path.resolve()))

        def _selected_band_entry(self) -> dict[str, Any]:
            feed = self.feed_combo.currentText().strip().upper()
            horn = self.horn_combo.currentText().strip().upper()
            for entry in band_entries_from_config(vm.catalog.band_config):
                if str(entry["feed"]).strip().upper() == feed and str(entry["horn"]).strip().upper() == horn:
                    return entry
            return {}

        def _browse_horn_gain_file(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "选择喇叭增益文件",
                "",
                "Gain Files (*.csv *.txt *.s2p *.dat);;All Files (*)",
            )
            if path:
                self.horn_gain_file_input.setText(path)

        def _sync_inline_confirmation(self, step: StepViewData) -> None:
            if not step.substep_id or step.confirm_phase not in {"start", "saved"}:
                self._hide_inline_confirmation()
                return

            step_label = f"STEP{step.substep_index}" if step.substep_index else "当前小步骤"
            if step.confirm_phase == "start":
                self._set_inline_confirmation(
                    message=(
                        f"{step_label} 接线确认：{_friendly_text(step.substep_name)}。"
                        "请按上方步骤执行区的接线路径和命令说明确认。"
                    ),
                    continue_label="确认接线完成",
                    allow_retry=False,
                )
                return

            self._set_inline_confirmation(
                message=(
                    f"{step_label} 保存确认：原始输出 {_plain_join(step.raw_outputs)}，"
                    f"最终输出 {_plain_join(step.final_outputs)}。请确认数据已保存。"
                ),
                continue_label="完成并继续",
                allow_retry=True,
            )

        def _set_inline_confirmation(self, *, message: str, continue_label: str, allow_retry: bool) -> None:
            assert self.inline_confirm_panel is not None
            assert self.inline_confirm_label is not None
            assert self.btn_inline_retry is not None
            assert self.btn_inline_continue is not None
            assert self.btn_inline_skip is not None
            assert self.btn_inline_cancel is not None
            self.inline_confirm_label.setText(message)
            self.btn_inline_continue.setText(continue_label)
            self.btn_inline_retry.setVisible(allow_retry)
            self.btn_inline_continue.setVisible(True)
            self.btn_inline_skip.setVisible(True)
            self.btn_inline_cancel.setVisible(True)
            self.inline_confirm_panel.setProperty("confirmState", "active")
            self.inline_confirm_panel.style().unpolish(self.inline_confirm_panel)
            self.inline_confirm_panel.style().polish(self.inline_confirm_panel)
            self._set_confirmation_blocked(True)
            self.inline_confirm_panel.setVisible(True)

        def _hide_inline_confirmation(self) -> None:
            if self.inline_confirm_panel is not None:
                self._set_inline_confirmation_idle(self.inline_confirm_panel)

        def _set_inline_confirmation_idle(self, panel: QFrame) -> None:
            if self.inline_confirm_label is not None:
                self.inline_confirm_label.setText("等待当前 STEP 确认")
            for button in (
                self.btn_inline_retry,
                self.btn_inline_continue,
                self.btn_inline_skip,
                self.btn_inline_cancel,
            ):
                if button is not None:
                    button.setVisible(False)
            panel.setProperty("confirmState", "idle")
            panel.style().unpolish(panel)
            panel.style().polish(panel)
            self._set_confirmation_blocked(False)
            panel.setVisible(True)

        def _set_confirmation_blocked(self, blocked: bool) -> None:
            for widget in (
                self.item_list,
                self.step_list,
                self.substep_list,
                self.btn_import_config,
                self.btn_import_default_config,
            ):
                widget.setEnabled(not blocked)

        def _submit_inline_prompt_action(self, action: str) -> None:
            self._active_prompt_view = None
            self._hide_inline_confirmation()
            vm.submit_action(action)

        def _show_modal_dialog(
            self,
            *,
            title: str,
            message: str,
            buttons: tuple[tuple[str, str, str], ...],
            default_action: str = "",
            width: int = 600,
            height: int = 300,
        ) -> str:
            dialog = QDialog(self)
            dialog.setWindowTitle(title)
            dialog.setFixedSize(width, height)
            selected_action = {"value": ""}

            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(16, 16, 16, 14)
            layout.setSpacing(10)

            message_label = QLabel(message)
            message_label.setWordWrap(True)
            message_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            message_label.setObjectName("dialogMessage")

            message_area = QScrollArea()
            message_area.setWidgetResizable(True)
            message_area.setFrameShape(QFrame.Shape.NoFrame)
            message_area.setWidget(message_label)
            layout.addWidget(message_area, 1)

            button_row = QHBoxLayout()
            button_row.setSpacing(10)
            groups = {"left": [], "center": [], "right": []}

            def add_action_button(label: str, action: str) -> QPushButton:
                button = QPushButton(label)
                role = {
                    "continue": "success",
                    "ok": "primary",
                    "yes": "success",
                    "no": "danger",
                    "retry": "warning",
                    "skip": "primary",
                    "cancel": "danger",
                }.get(action, "secondary")
                _style_button(button, role=role)
                button.clicked.connect(
                    lambda _checked=False, selected=action: self._finish_modal_dialog(
                        dialog,
                        selected_action,
                        selected,
                    )
                )
                if action == default_action:
                    button.setDefault(True)
                    button.setAutoDefault(True)
                return button

            for label, action, position in buttons:
                groups[position].append(add_action_button(label, action))
            for button in groups["left"]:
                button_row.addWidget(button)
            button_row.addStretch(1)
            for button in groups["center"]:
                button_row.addWidget(button)
            button_row.addStretch(1)
            for button in groups["right"]:
                button_row.addWidget(button)
            layout.addLayout(button_row)
            dialog.exec()
            return selected_action["value"]

        def _finish_modal_dialog(self, dialog: QDialog, selected_action: dict[str, str], action: str) -> None:
            selected_action["value"] = action
            dialog.accept()

        def _confirm_start_button(self) -> None:
            self._confirm_start_calibration(recalibrate=bool(self.btn_start.property("recalibrateAction")))

        def _confirm_start_calibration(self, recalibrate: bool = False) -> None:
            item = vm.selected_item
            if item is None:
                self._show_modal_dialog(
                    title="无法开始校准",
                    message="当前未加载链路配置。\n\n请先导入链路配置或导入默认配置。",
                    buttons=(("确认", "ok", "center"),),
                    default_action="ok",
                    width=460,
                    height=200,
                )
                return
            if recalibrate and vm.item_progress_state(item.id) not in {"done", "running"}:
                recalibrate = False
            try:
                vna_settings = self._vna_run_settings()
            except Exception as exc:
                self._show_modal_dialog(
                    title="喇叭增益文件错误",
                    message=str(exc),
                    buttons=(("确认", "ok", "center"),),
                    default_action="ok",
                    width=560,
                    height=230,
                )
                return
            horn_gain_message = (
                f"\n喇叭增益: {Path(vna_settings['horn_gain_file']).name}"
                if vna_settings.get("horn_gain_file")
                else "\n喇叭增益: 未导入，Mock 计算使用 0 dB 默认值。"
            )
            action = self._show_modal_dialog(
                title="重新校准确认" if recalibrate else "开始校准确认",
                message=(
                    f"确认{'重新' if recalibrate else '开始'}执行 {item.id} - {_friendly_text(item.name)}？\n\n"
                    f"网分扫频: {vna_settings['start_ghz']:.3f} GHz 到 {vna_settings['stop_ghz']:.3f} GHz，"
                    f"{vna_settings['points']} 点，步进 {vna_settings['frequency_step_mhz']:.3f} MHz。\n"
                    f"馈源/喇叭: {vna_settings['feed']} / {vna_settings['horn']}。"
                    f"{horn_gain_message}\n"
                    f"{'将覆盖当前校准项的运行状态，并按现有输出规则写入新文件。' if recalibrate else '步骤列表显示校准项，步骤执行区会逐个小步骤等待确认。'}"
                ),
                buttons=(("重新校准" if recalibrate else "开始校准", "yes", "center"), ("取消", "cancel", "center")),
                default_action="yes",
                width=520,
                height=240,
            )
            if action == "yes":
                vm.start_selected(vna_settings)

        def _vna_run_settings(self) -> dict[str, Any]:
            for panel in self.command_panels:
                if panel.device_key == "vna":
                    settings = panel.vna_settings()
                    break
            else:
                settings = {}
            settings["feed"] = self.feed_combo.currentText().strip()
            settings["horn"] = self.horn_combo.currentText().strip()
            settings["project_code"] = self.project_code_input.text().strip() or "DEFAULT_PROJECT"
            stage_code = self.calibration_stage_combo.currentData()
            settings["calibration_stage"] = str(stage_code or self.calibration_stage_combo.currentText()).strip() or "initial"
            settings["run_label"] = self.run_label_input.text().strip() or "R01"
            settings["operator"] = ""
            settings["operator_note"] = ""
            horn_gain_file = self.horn_gain_file_input.text().strip()
            if horn_gain_file:
                settings["horn_gain_file"] = horn_gain_file
                settings["external_inputs"] = self._load_horn_gain_inputs(horn_gain_file, settings)
                settings["horn_gain_sha256"] = hashlib.sha256(Path(horn_gain_file).read_bytes()).hexdigest()
            return settings

        def _load_horn_gain_inputs(self, path_text: str, settings: dict[str, Any]) -> dict[str, Any]:
            path = Path(path_text)
            if not path.exists():
                raise RuntimeError(f"喇叭增益文件不存在：{path}")
            rows = self._read_numeric_gain_rows(path)
            if not rows:
                raise RuntimeError(f"喇叭增益文件没有可读取的数值行：{path}")

            frequencies = np.asarray([row["freq_hz"] for row in rows], dtype=float)
            if np.any(np.diff(frequencies) < 0):
                order = np.argsort(frequencies)
                frequencies = frequencies[order]
                rows = [rows[int(index)] for index in order]
            target = np.linspace(float(settings["start_ghz"]) * 1e9, float(settings["stop_ghz"]) * 1e9, int(settings["points"]))
            horn_gain_warnings = list(settings.get("horn_gain_warnings", ()) or ())
            if len(frequencies) < 2:
                horn_gain_warnings.append("喇叭增益文件少于 2 个频率点。")
            if np.any(np.diff(frequencies) <= 0):
                horn_gain_warnings.append("喇叭增益文件频率列不是严格递增或存在重复频点。")
            if float(target[0]) < float(frequencies[0]) or float(target[-1]) > float(frequencies[-1]):
                horn_gain_warnings.append("喇叭增益文件频率范围未覆盖当前扫频范围，已按端点外推提醒处理。")
            if horn_gain_warnings:
                settings["horn_gain_warnings"] = tuple(horn_gain_warnings)

            def column_values(name: str, fallback: str = "gain_db") -> np.ndarray:
                values = [row.get(name, row.get(fallback)) for row in rows]
                if any(value is None for value in values):
                    raise RuntimeError(f"喇叭增益文件缺少列：{name}")
                return np.asarray(values, dtype=float)

            gain_h = column_values("gain_h_db") if any("gain_h_db" in row for row in rows) else column_values("gain_db")
            gain_v = column_values("gain_v_db") if any("gain_v_db" in row for row in rows) else gain_h
            return {
                "G_STD_HORN_H": np.interp(target, frequencies, gain_h),
                "G_STD_HORN_V": np.interp(target, frequencies, gain_v),
            }

        def _read_numeric_gain_rows(self, path: Path) -> list[dict[str, float]]:
            with path.open("r", encoding="utf-8-sig", newline="") as file:
                sample = file.read(2048)
                file.seek(0)
                delimiter = "\t" if "\t" in sample and "," not in sample else ","
                reader = csv.reader(file, delimiter=delimiter)
                raw_rows = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]
            if not raw_rows:
                return []

            header = [cell.strip().lower() for cell in raw_rows[0]]
            has_header = any(not self._is_float(cell) for cell in header)
            data_rows = raw_rows[1:] if has_header else raw_rows
            indexes = self._gain_column_indexes(header) if has_header else {"freq_hz": 0, "gain_db": 1}
            rows: list[dict[str, float]] = []
            for row in data_rows:
                try:
                    freq = float(row[indexes["freq_hz"]])
                    if freq < 1e6:
                        freq *= 1e9
                    record = {"freq_hz": freq}
                    for key in ("gain_db", "gain_h_db", "gain_v_db"):
                        if key in indexes and indexes[key] < len(row):
                            record[key] = float(row[indexes[key]])
                    if "gain_db" not in record and "gain_h_db" in record:
                        record["gain_db"] = record["gain_h_db"]
                    rows.append(record)
                except (ValueError, IndexError, KeyError):
                    continue
            return rows

        @staticmethod
        def _gain_column_indexes(header: list[str]) -> dict[str, int]:
            aliases = {
                "freq_hz": {"freq_hz", "frequency_hz", "freq", "frequency", "hz", "freq_ghz", "ghz"},
                "gain_db": {"gain_db", "gain_dbi", "db", "dbi", "gain"},
                "gain_h_db": {"gain_h_db", "gain_h_dbi", "h_gain_db", "h_gain_dbi", "g_std_horn_h"},
                "gain_v_db": {"gain_v_db", "gain_v_dbi", "v_gain_db", "v_gain_dbi", "g_std_horn_v"},
            }
            result: dict[str, int] = {}
            for index, column in enumerate(header):
                normalized = column.strip().lower()
                for key, names in aliases.items():
                    if normalized in names:
                        result[key] = index
            if "freq_hz" not in result:
                raise RuntimeError("喇叭增益文件缺少频率列。")
            if not {"gain_db", "gain_h_db", "gain_v_db"} & set(result):
                raise RuntimeError("喇叭增益文件缺少增益列。")
            return result

        @staticmethod
        def _is_float(value: str) -> bool:
            try:
                float(value)
                return True
            except ValueError:
                return False

        def _confirm_run_finished(self, summary: object) -> None:
            data = dict(summary) if isinstance(summary, dict) else {}
            self._sync_start_button_state("DONE")
            self._active_prompt_view = None
            self._hide_inline_confirmation()
            self._show_modal_dialog(
                title="校准完成确认",
                message=(
                    "校准执行已完成。\n\n"
                    f"校准项: {_friendly_text(data.get('item_id', ''))}\n"
                    f"状态: {_friendly_text(data.get('state', ''))}\n"
                    f"完成小步骤: {data.get('completed_steps', '')}/{data.get('total_substeps', data.get('total_steps', ''))}\n"
                    f"最后事件: {_friendly_text(data.get('last_event', ''))}"
                ),
                buttons=(("确定", "ok", "center"),),
                default_action="ok",
                width=540,
                height=250,
            )

        def _sync_start_button_state(self, state: str) -> None:
            normalized = str(state).upper()
            selected_item = vm.selected_item
            item_state = vm.item_progress_state(selected_item.id) if selected_item is not None else "pending"
            if normalized in {"DONE", "CALIBRATION COMPLETED"} or item_state == "done":
                button_state = "done"
            elif normalized in {"FAILED", "CANCELLED", "ERROR"} or normalized.startswith("ERROR"):
                button_state = "error"
            elif normalized in {"IDLE", "READY"}:
                button_state = "idle"
            else:
                button_state = "running"
            is_recalibrate = button_state in {"done", "error"} and selected_item is not None
            if button_state == "running":
                text = "校准中"
            elif is_recalibrate:
                text = "重新校准"
            else:
                text = "开始校准"
            self.btn_start.setText(text)
            self.btn_start.setProperty("recalibrateAction", is_recalibrate)
            _style_button(self.btn_start, role="warning" if is_recalibrate else "primary", state=button_state)
            can_click = selected_item is not None and (button_state == "idle" or is_recalibrate)
            self.btn_start.setEnabled(can_click)

        def _fill_preset(self, panel: DeviceCommandPanel) -> None:
            panel.command_input.setText(panel.selected_command())

        def _send_command(self, panel: DeviceCommandPanel) -> None:
            try:
                response = vm.send_device_command(panel.device_key, panel.command_text())
            except Exception as exc:
                self._show_modal_dialog(title="命令发送失败", message=str(exc), buttons=(("确定", "ok", "center"),), default_action="ok", width=500, height=220)
                return
            panel.set_response(response)

        def _configure_vna(self, panel: DeviceCommandPanel) -> None:
            try:
                response = vm.configure_vna(panel.vna_settings())
            except Exception as exc:
                self._show_modal_dialog(title="网分配置失败", message=str(exc), buttons=(("确定", "ok", "center"),), default_action="ok", width=500, height=220)
                return
            panel.set_response(response)

        def _trigger_vna(self, panel: DeviceCommandPanel) -> None:
            try:
                response = vm.trigger_vna(panel.vna_settings())
            except Exception as exc:
                self._show_modal_dialog(title="网分触发失败", message=str(exc), buttons=(("确定", "ok", "center"),), default_action="ok", width=500, height=220)
                return
            panel.set_response(response)

        def _sample_vna(self, panel: DeviceCommandPanel) -> None:
            try:
                response = vm.sample_vna(panel.vna_settings())
            except Exception as exc:
                self._show_modal_dialog(title="网分采样失败", message=str(exc), buttons=(("确定", "ok", "center"),), default_action="ok", width=500, height=220)
                return
            panel.set_response(response)

        def _configure_signal_generator(self, panel: DeviceCommandPanel) -> None:
            try:
                response = vm.configure_signal_generator(panel.signal_generator_settings())
            except Exception as exc:
                self._show_modal_dialog(title="信号源配置失败", message=str(exc), buttons=(("确定", "ok", "center"),), default_action="ok", width=500, height=220)
                return
            panel.set_response(response)

        def _configure_spectrum_analyzer(self, panel: DeviceCommandPanel) -> None:
            try:
                response = vm.configure_spectrum_analyzer(panel.spectrum_analyzer_settings())
            except Exception as exc:
                self._show_modal_dialog(title="频谱仪配置失败", message=str(exc), buttons=(("确定", "ok", "center"),), default_action="ok", width=500, height=220)
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
                self._show_modal_dialog(title="设备连接失败", message=str(exc), buttons=(("确定", "ok", "center"),), default_action="ok", width=500, height=220)
                return
            panel.set_connection_state(state)
            self._sync_overview()

        def _disconnect_command_device(self, panel: DeviceCommandPanel) -> None:
            try:
                state = vm.disconnect_device(panel.device_key)
            except Exception as exc:
                self._show_modal_dialog(title="设备断开失败", message=str(exc), buttons=(("确定", "ok", "center"),), default_action="ok", width=500, height=220)
                return
            panel.set_connection_state(state)
            self._sync_overview()

        def _search_visa_resources(self, panel: DeviceCommandPanel) -> None:
            if panel.device_key == "link_box":
                return
            if panel.mock_check.isChecked():
                panel.set_resource_options(vm.device_mock_resource_options(panel.device_key))
                return
            try:
                resources = vm.list_visa_resources()
            except Exception as exc:
                self._show_modal_dialog(title="VISA 资源搜索失败", message=str(exc), buttons=(("确定", "ok", "center"),), default_action="ok", width=500, height=220)
                return
            if not resources:
                self._show_modal_dialog(title="VISA 资源搜索", message="未发现 VISA 资源。", buttons=(("确定", "ok", "center"),), default_action="ok", width=480, height=210)
                return
            panel.set_resource_options(resources, resources[0])
            panel.select_matching_resource_for_model()

        def _on_mock_mode_changed(self, panel: DeviceCommandPanel) -> None:
            if panel.mock_check.isChecked():
                resources = vm.device_mock_resource_options(panel.device_key)
                panel.set_resource_options(resources, resources[0] if resources else "")
            elif panel.device_key == "link_box":
                panel.btn_search_visa.setEnabled(False)
            else:
                panel.btn_search_visa.setEnabled(True)
                try:
                    resources = vm.list_visa_resources()
                except Exception:
                    return
                if resources:
                    panel.set_resource_options(resources, resources[0])
                    panel.select_matching_resource_for_model()

        def _sync_device_connection_panels(self) -> None:
            for panel in self.command_panels:
                state = vm.device_connection_state(panel.device_key)
                panel.set_connection_state(state)
                panel.set_model_options(vm.device_model_options(panel.device_key), state.model)
                resources = vm.device_mock_resource_options(panel.device_key) if state.use_mock else (state.resource,)
                panel.set_resource_options(resources, state.resource)

        def _format_log_entry(self, record: LogEntry, show_timestamp: bool = True) -> str:
            palette = {
                "INFO": ("#2563eb", "#1f2937"),
                "WARNING": ("#b45309", "#78350f"),
                "WARN": ("#b45309", "#78350f"),
                "ERROR": ("#dc2626", "#7f1d1d"),
            }
            level_color, text_color = palette.get(record.level.upper(), ("#475569", "#1f2937"))
            prefix = f"{html.escape(record.timestamp)} " if show_timestamp else ""
            level = html.escape(record.level)
            source = html.escape(record.source)
            name = html.escape(record.name)
            message = html.escape(record.message)
            return (
                f"<span style='color:#64748b;'>{prefix}</span>"
                f"<span style='color:{level_color};font-weight:700;'>[{level}]</span> "
                f"<span style='color:#475569;'>{source}/{name}</span>"
                f"<span style='color:#94a3b8;'> - </span>"
                f"<span style='color:{text_color};'>{message}</span>"
            )

        def _format_overview_summary(self, overview: dict[str, Any]) -> str:
            run_summary = overview.get("run_summary") or {}
            raw_count = len(run_summary.get("raw_files", ())) if isinstance(run_summary, dict) else 0
            loss_count = len(run_summary.get("loss_files", ())) if isinstance(run_summary, dict) else 0
            metadata_count = len(run_summary.get("metadata_files", ())) if isinstance(run_summary, dict) else 0
            manifest_count = 1 if isinstance(run_summary, dict) and run_summary.get("manifest_file") else 0
            project_code = run_summary.get("project_code", "") if isinstance(run_summary, dict) else ""
            calibration_stage = run_summary.get("calibration_stage", "") if isinstance(run_summary, dict) else ""
            run_label = run_summary.get("run_label", "") if isinstance(run_summary, dict) else ""
            session_id = run_summary.get("session_id", "") if isinstance(run_summary, dict) else ""
            lines = [
                f"视图: {overview.get('result_view_label', '当前Session')}",
                f"项目: {_friendly_text(overview.get('item_name', ''))}",
                f"文件空间: {project_code or '-'} / {_stage_display(calibration_stage) or '-'} / {run_label or '-'}",
                f"session: {session_id or '-'}",
                f"当前步骤: {overview.get('selected_step_id', '')}",
                f"状态: {overview.get('status', '')}",
                f"校准步数: {overview.get('steps', '')}",
                f"连接: {'OK' if self._all_command_devices_connected(overview) else '待连接'}",
                f"已完成子步骤: {run_summary.get('completed_steps', 0) if isinstance(run_summary, dict) else 0}",
                f"文件: final {loss_count} / raw {raw_count} / metadata {metadata_count} / manifest {manifest_count}",
                f"最后事件: {_friendly_text(run_summary.get('last_event', '') if isinstance(run_summary, dict) else '')}",
            ]
            return "\n".join(lines)

        def _format_overview_detail(self, overview: dict[str, Any]) -> str:
            run_summary = overview.get("run_summary") or {}
            lines = [
                f"item_id: {overview.get('item_id', '')}",
                f"purpose: {_friendly_text(overview.get('purpose', ''))}",
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
                lines.append(f"workspace_id: {run_summary.get('workspace_id', '')}")
                lines.append(f"workspace_root: {run_summary.get('workspace_root', '')}")
                lines.append(f"config_hash: {run_summary.get('config_hash', '')}")
                lines.append(f"config_source_path: {run_summary.get('config_source_path', '')}")
                lines.append(f"project_code: {run_summary.get('project_code', '')}")
                stage = str(run_summary.get("calibration_stage", ""))
                lines.append(f"calibration_stage: {_stage_display(stage)} ({stage})" if stage else "calibration_stage: ")
                lines.append(f"run_label: {run_summary.get('run_label', '')}")
                lines.append(f"operator: {run_summary.get('operator', '')}")
                lines.append(f"operator_note: {run_summary.get('operator_note', '')}")
                lines.append(f"session_id: {run_summary.get('session_id', '')}")
                lines.append(f"session_root: {run_summary.get('session_root', '')}")
                lines.append(f"completed_steps: {run_summary.get('completed_steps', '')}")
                lines.append(f"completed_big_steps: {run_summary.get('completed_big_steps', '')}")
                if "publishable" in run_summary:
                    lines.append(f"publishable: {run_summary.get('publishable', '')}")
                if run_summary.get("publish_blockers"):
                    lines.append(f"publish_blockers: {', '.join(str(value) for value in run_summary.get('publish_blockers', ()) or ())}")
                if run_summary.get("measurement_warnings"):
                    lines.append(f"measurement_warnings: {', '.join(str(value) for value in run_summary.get('measurement_warnings', ()) or ())}")
                if run_summary.get("resume_compatibility_warnings"):
                    lines.append(
                        "resume_compatibility_warnings: "
                        + ", ".join(str(value) for value in run_summary.get("resume_compatibility_warnings", ()) or ())
                    )
                lines.append(f"last_event: {_friendly_text(run_summary.get('last_event', ''))}")
                lines.append(f"link_box_connected: {run_summary.get('link_box_connected', '')}")
                lines.append(f"vna_connected: {run_summary.get('vna_connected', '')}")
                lines.append(f"output_root: {run_summary.get('output_root', '')}")
                lines.append(f"final_files: {len(run_summary.get('loss_files', ()) or ())}")
                lines.append(f"raw_files: {len(run_summary.get('raw_files', ()) or ())}")
                lines.append(f"metadata_files: {len(run_summary.get('metadata_files', ()) or ())}")
                lines.append(f"manifest_file: {run_summary.get('manifest_file', '')}")
                if run_summary.get("latest_index_file"):
                    lines.append(f"latest_index_file: {run_summary.get('latest_index_file', '')}")
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
    style_text = _load_text(style_dir / "style_bule.qss")
    app.setStyleSheet(style_text)

    window = MainWindow()
    if "--gui-smoke" in set(sys.argv[1:]):
        vm.load_default_catalog()
        vm.connect_mock_devices()
        window._sync_after_catalog_changed()
        window._sync_device_connection_panels()
        window._sync_logs()
        window._sync_start_button_state("READY")
        initial_button_ok = window.btn_start.isEnabled() and window.btn_start.text() == "开始校准" and not bool(window.btn_start.property("recalibrateAction"))
        window._sync_start_button_state("WAIT_MANUAL_CONFIRM")
        running_button_ok = not window.btn_start.isEnabled() and window.btn_start.text() == "校准中"
        run_summary: dict[str, object] = {}
        latest_result_rows_ok = False
        latest_result_detail_ok = False
        history_result_rows_ok = False
        history_result_detail_ok = False
        legacy_result_rows_ok = False
        legacy_result_detail_ok = False
        history_import_button_ok = False
        step_detail_tabs_ok = False
        history_curve_preview_ok = False
        history_item_step_color_ok = False
        if vm.selected_item is not None:
            with TemporaryDirectory() as tmpdir:
                window.project_code_input.setText("SMOKE_PROJECT")
                workspace = workspace_for_catalog(vm.catalog, Path(tmpdir))
                write_workspace_manifest(workspace, vm.catalog)
                session = create_session_context(
                    workspace=workspace,
                    run=CalibrationRunContext(
                        project_code="SMOKE_PROJECT",
                        calibration_stage="initial",
                        run_label="R01",
                    ),
                    item_id=vm.selected_item.id,
                )
                runner = CalibrationRunner(
                    vm.selected_item,
                    vm._mock_vna,
                    vm._mock_link_box,
                    session.session_root,
                    vna_settings={"points": 3},
                    session_context=session,
                )
                runner.run()
                run_summary = runner.overview()
                item_id = str(run_summary.get("item_id", ""))
                if item_id:
                    vm._run_summaries_by_item[item_id] = run_summary
                    vm._run_status_by_item[item_id] = "Calibration completed"
                    vm.status_text_update("Calibration completed")
                    vm.refresh_overview()
                window._sync_overview()
                window.result_view_combo.setCurrentIndex(1)
                window._sync_overview()
                latest_result_rows_ok = window.result_file_table.rowCount() >= 4
                latest_result_detail_ok = "latest_index_file:" in window.result_session.toPlainText()
                window.result_workspace_input.setText(str(workspace.workspace_root))
                window.result_view_combo.setCurrentIndex(2)
                window._sync_overview()
                history_result_rows_ok = window.result_file_table.rowCount() >= 4
                history_result_detail_ok = "session_id:" in window.result_session.toPlainText()
                history_import_button_ok = window.btn_import_history_data.text() == "导入历史数据"
                step_detail_tabs_ok = (
                    window.step_detail_stack.count() == 2
                    and window.step_detail_stack.tabText(0) == "链路说明"
                    and window.step_detail_stack.tabText(1) == "数据展示"
                )
                window._history_data_summary = load_session_summary_from_manifest(session.session_root / "session_manifest.json")
                window.step_list.setCurrentRow(0)
                window._sync_item_list()
                window._sync_step_list_colored()
                window._sync_substep_list()
                item_tooltip = window.item_list.item(window.item_list.currentRow()).toolTip()
                step_tooltip = window.step_list.item(0).toolTip()
                history_item_step_color_ok = item_tooltip in {"已有历史", "已完成"} and step_tooltip in {"已有历史", "已完成"}
                history_detail_step = window._step_view_for_substep_row(0)
                history_curve_path = window._history_curve_path_for_step(history_detail_step) if history_detail_step else None
                if history_detail_step is not None and history_curve_path is not None:
                    window._sync_saved_step_curve(history_detail_step, activate=False)
                    history_curve_preview_ok = bool(window._saved_curve_data)
                legacy_root = Path(tmpdir) / "legacy_output"
                legacy_raw = legacy_root / "raw" / "LINK-CAL-001_LEGACY_RAW.csv"
                legacy_loss = legacy_root / "loss" / "L_LEGACY_10_15G_F10_17G_H10_15G.csv"
                legacy_metadata = legacy_root / "metadata" / "LINK-CAL-001_LEGACY.json"
                legacy_raw.parent.mkdir(parents=True, exist_ok=True)
                legacy_loss.parent.mkdir(parents=True, exist_ok=True)
                legacy_metadata.parent.mkdir(parents=True, exist_ok=True)
                legacy_raw.write_text("freq_hz,raw_s21_db\n10000000000,-1\n", encoding="utf-8")
                legacy_loss.write_text("freq_hz,value_db\n10000000000,-2\n", encoding="utf-8")
                legacy_metadata.write_text(
                    json.dumps(
                        {
                            "calibration_item": vm.selected_item.id,
                            "input_files": [str(legacy_raw)],
                            "output_files": [str(legacy_loss)],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                window.result_workspace_input.setText(str(legacy_root))
                window.result_view_combo.setCurrentIndex(3)
                window._sync_overview()
                legacy_result_rows_ok = window.result_file_table.rowCount() >= 3
                legacy_result_detail_ok = "UNBOUND_LEGACY" in window.result_session.toPlainText()
                window.result_view_combo.setCurrentIndex(0)
                window._sync_overview()
        app.processEvents()
        sg_panel = next(panel for panel in window.command_panels if panel.device_key == "signal_generator")
        sa_panel = next(panel for panel in window.command_panels if panel.device_key == "spectrum_analyzer")
        vna_panel = next(panel for panel in window.command_panels if panel.device_key == "vna")
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        grouped_panel_titles_ok = all(
            {"资源连接", "仪表配置", "指令控制"}.issubset(
                {group.title() for group in panel.findChildren(QGroupBox)}
            )
            for panel in (vna_panel, sg_panel, sa_panel)
        )
        checks = {
            "tabs": window.tabs.count() >= 3,
            "items": window.item_list.count() == len(vm.catalog.items),
            "steps": window.step_list.count() == len(vm.selected_item.steps) if vm.selected_item is not None else False,
            "logs": window.global_log_panel.copy_all_text() != "",
            "connection_label": window.connection_label.text() != "",
            "raw_files": bool(run_summary.get("raw_files")),
            "loss_files": bool(run_summary.get("loss_files")),
            "metadata_files": bool(run_summary.get("metadata_files")),
            "manifest_file": bool(run_summary.get("manifest_file")),
            "default_horn_gain_file": bool(window.horn_gain_file_input.text()) and Path(window.horn_gain_file_input.text()).exists(),
            "result_rows": window.result_file_table.rowCount() >= 4,
            "latest_result_rows": latest_result_rows_ok,
            "latest_result_detail": latest_result_detail_ok,
            "history_result_rows": history_result_rows_ok,
            "history_result_detail": history_result_detail_ok,
            "legacy_result_rows": legacy_result_rows_ok,
            "legacy_result_detail": legacy_result_detail_ok,
            "history_import_button": history_import_button_ok,
            "step_detail_tabs": step_detail_tabs_ok,
            "history_curve_preview": history_curve_preview_ok,
            "history_item_step_color": history_item_step_color_ok,
            "session_detail": "workspace_id:" in window.result_session.toPlainText(),
            "completed_status": vm.overview.get("status") == "Calibration completed",
            "initial_buttons": initial_button_ok,
            "running_buttons": running_button_ok,
            "done_recalibrate_button": window.btn_start.isEnabled() and window.btn_start.text() == "重新校准" and bool(window.btn_start.property("recalibrateAction")),
            "signal_generator_settings": sg_panel.signal_generator_settings_group is not None and sg_panel.signal_generator_settings_group.isEnabled(),
            "spectrum_analyzer_settings": sa_panel.spectrum_analyzer_settings_group is not None and sa_panel.spectrum_analyzer_settings_group.isEnabled(),
            "device_panel_group_titles": grouped_panel_titles_ok,
            "command_page_scroll": bool(window.command_page.findChildren(QScrollArea)),
            "initial_size_in_screen": (
                available is None
                or (window.width() <= available.width() and window.height() <= available.height())
            ),
        }
        window.close()
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            print("GUI smoke failed checks: " + ", ".join(failed))
            return 1
        return 0
    window._center_on_screen()
    window.show()
    return app.exec()
