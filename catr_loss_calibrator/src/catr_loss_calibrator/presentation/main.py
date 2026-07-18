from __future__ import annotations

import html
import re
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
    print("通用路损校准控制台")
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
    from PySide6.QtGui import QAction, QBrush, QColor, QCursor, QFont, QPainter, QPixmap, QTextCursor
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
        QPushButton,
        QProgressBar,
        QScrollArea,
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

    def _friendly_node_text(value: str) -> str:
        text = value.strip()
        exact = _NODE_LABELS.get(text.upper())
        if exact:
            return exact
        if "/" in text:
            return "/".join(_friendly_node_text(part) for part in text.split("/"))
        return _friendly_text(text)

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

    def _aux_route(aux_name: str) -> list[str]:
        return ["网分 PORT1", aux_name, "网分 PORT2"]

    def _dut_vna2_return_route(aux_name: str, *, amp1: bool = False) -> list[str]:
        route = ["网分 PORT1", aux_name, "转台 DUT 接口", "暗室接口板 DUT"]
        if amp1:
            route.append("AMP1")
        route.extend(["链路箱 VNA2", "网分 PORT2"])
        return route

    def _space_nodes(polarization: str, *, reverse: bool = False) -> list[str]:
        nodes = [
            f"链路箱 {polarization}",
            f"暗室接口板 {polarization}",
            f"馈源 {polarization}",
            "反射面",
            "标准增益喇叭",
            "暗室接口板 DUT",
        ]
        return list(reversed(nodes)) if reverse else nodes

    def _vna_main_route(polarization: str, *, amp1: bool = False, amp2: bool = False) -> list[str]:
        if amp2:
            return [
                "网分 PORT1",
                "链路箱 VNA2",
                "暗室接口板 DUT",
                "标准增益喇叭",
                "反射面",
                f"馈源 {polarization}",
                f"暗室接口板 {polarization}",
                f"链路箱 {polarization}",
                "AMP2",
                "链路箱 VNA1",
                "网分 PORT2",
            ]
        route = ["网分 PORT1", "链路箱 VNA1", *_space_nodes(polarization)]
        if amp1:
            route.append("AMP1")
        route.extend(["链路箱 VNA2", "网分 PORT2"])
        return route

    def _sa_hv_route(polarization: str, *, amp1: bool = False, amp2: bool = False) -> list[str]:
        if amp2:
            return [
                "网分 PORT1",
                "链路箱 VNA2",
                "暗室接口板 DUT",
                "标准增益喇叭",
                "反射面",
                f"馈源 {polarization}",
                f"暗室接口板 {polarization}",
                f"链路箱 {polarization}",
                "AMP2",
                "链路箱 SA",
                "网分 PORT2",
            ]
        route = ["网分 PORT1", "链路箱 SA", *_space_nodes(polarization)]
        if amp1:
            route.append("AMP1")
        route.extend(["链路箱 VNA2", "网分 PORT2"])
        return route

    def _sg_route(polarization: str, *, amp1: bool = False, amp2: bool = False) -> list[str]:
        if amp2:
            return [
                "网分 PORT1",
                "链路箱 VNA2",
                "暗室接口板 DUT",
                "标准增益喇叭",
                "反射面",
                f"馈源 {polarization}",
                f"暗室接口板 {polarization}",
                f"链路箱 {polarization}",
                "AMP2",
                "链路箱 SG",
                "网分 PORT2",
            ]
        route = ["网分 PORT1", "链路箱 SG", *_space_nodes(polarization)]
        if amp1:
            route.append("AMP1")
        route.extend(["链路箱 VNA2", "网分 PORT2"])
        return route

    def _path_routes_from_template(step: StepViewData) -> list[list[str]]:
        key = f"{step.step_id}:{step.substep_id}" if step.substep_id else step.step_id
        templates: dict[str, list[list[str]]] = {
            "CAL001-AUX:AUX-A": [_aux_route("AUX-A")],
            "CAL001-AUX:AUX-B": [_aux_route("AUX-B")],
            "CAL001-AUX:AUX-C": [_aux_route("AUX-C")],
            "CAL001-AUX": [["网分 PORT1", "3M 辅助线 A/B/C", "网分 PORT2"]],
            "CAL001-H": [["网分 PORT1", "AUX-A", "暗室接口板 H", "馈源 H", "反射面", "标准增益喇叭", "暗室接口板 DUT", "AUX-C", "网分 PORT2"]],
            "CAL001-V": [["网分 PORT1", "AUX-B", "暗室接口板 V", "馈源 V", "反射面", "标准增益喇叭", "暗室接口板 DUT", "AUX-C", "网分 PORT2"]],
            "CAL001-DUT": [["网分 PORT1", "AUX-A", "转台 DUT 接口", "DUT 内部段", "暗室接口板 DUT", "AUX-C", "网分 PORT2"]],
            "CAL002-AUX-D": [_aux_route("AUX-D")],
            "CAL002-DUT-VNA2": [_dut_vna2_return_route("AUX-D")],
            "CAL002-DUT-AMP1-VNA2": [_dut_vna2_return_route("AUX-D", amp1=True)],
            "CAL002-MAIN:H-THRU": [_vna_main_route("H")],
            "CAL002-MAIN:V-THRU": [_vna_main_route("V")],
            "CAL002-MAIN:H-DUTAMP1": [_vna_main_route("H", amp1=True)],
            "CAL002-MAIN:V-DUTAMP1": [_vna_main_route("V", amp1=True)],
            "CAL002-MAIN:H-AMP2": [_vna_main_route("H", amp2=True)],
            "CAL002-MAIN:V-AMP2": [_vna_main_route("V", amp2=True)],
            "CAL003-AUX-E": [_aux_route("AUX-E")],
            "CAL003-DUT-SA": [
                ["网分 PORT1", "AUX-E", "转台 DUT 接口", "暗室接口板 DUT", "链路箱 SA", "网分 PORT2"],
                ["网分 PORT1", "AUX-E", "转台 DUT 接口", "暗室接口板 DUT", "AMP1", "链路箱 SA", "网分 PORT2"],
            ],
            "CAL004-AUX-F": [_aux_route("AUX-F")],
            "CAL004-DUT-VNA2": [
                _dut_vna2_return_route("AUX-F"),
                _dut_vna2_return_route("AUX-F", amp1=True),
            ],
            "CAL004-SA-HV-THRU:H-SA": [_sa_hv_route("H")],
            "CAL004-SA-HV-THRU:V-SA": [_sa_hv_route("V")],
            "CAL004-SA-HV-AMP2:H-AMP2-SA": [_sa_hv_route("H", amp2=True)],
            "CAL004-SA-HV-AMP2:V-AMP2-SA": [_sa_hv_route("V", amp2=True)],
            "CAL004-SA-HV-DUTAMP1-CHECK:H-SA-DUTAMP1-CHECK": [_sa_hv_route("H", amp1=True)],
            "CAL004-SA-HV-DUTAMP1-CHECK:V-SA-DUTAMP1-CHECK": [_sa_hv_route("V", amp1=True)],
            "CAL005-AUX-G": [_aux_route("AUX-G")],
            "CAL005-DUT-VNA2": [
                _dut_vna2_return_route("AUX-G"),
                _dut_vna2_return_route("AUX-G", amp1=True),
            ],
            "CAL005-SG:H-SG": [_sg_route("H")],
            "CAL005-SG:V-SG": [_sg_route("V")],
            "CAL005-SG:H-SG-DUTAMP1": [_sg_route("H", amp1=True)],
            "CAL005-SG:V-SG-DUTAMP1": [_sg_route("V", amp1=True)],
            "CAL005-SG:H-AMP2-SG": [_sg_route("H", amp2=True)],
            "CAL005-SG:V-AMP2-SG": [_sg_route("V", amp2=True)],
        }
        if key in templates:
            return templates[key]
        if step.step_id in templates:
            return templates[step.step_id]
        return []

    def _node_style(node: str) -> str:
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

        routes = _path_routes_from_template(step) or _route_nodes_from_instruction(step.manual_instruction)
        route_html: list[str] = []
        for nodes in routes:
            parts: list[str] = []
            for index, node in enumerate(nodes):
                label = html.escape(_friendly_node_text(node))
                style = _node_style(node)
                parts.append(
                    "<span style='display:inline-block;border:1px solid "
                    "#9eb2ca;border-radius:5px;padding:5px 11px;margin:3px 4px 3px 0;"
                    f"{style}'>{label}</span>"
                )
                if index < len(nodes) - 1:
                    parts.append("<span style='color:#64748b;margin:0 6px;'>→</span>")
            route_html.append("<div style='margin-top:5px;'>" + "".join(parts) + "</div>")

        instruction = html.escape(step.manual_instruction or "无接线说明")
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
            tokens = [label for pattern, label in self._COMMAND_TOKEN_LABELS if pattern.search(selected)]
            tokens = list(dict.fromkeys(tokens))
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

    DeviceCommandPanel._COMMAND_TOKEN_LABELS = _COMMAND_TOKEN_LABELS

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("通用路损校准控制台")
            self.resize(1180, 780)
            self._last_confirmation_prompt_key = ""

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
            self.substep_list.setMinimumWidth(220)
            self.substep_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            self.path_view = QTextEdit()
            self.path_view.setReadOnly(True)
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
            self.connection_label = QLabel("网分: disconnected | 信号源: disconnected | 链路箱: disconnected | 频谱仪: disconnected")

            self.btn_connect = QPushButton("连接全部设备")
            self.btn_disconnect = QPushButton("断开全部设备")
            self.btn_start = QPushButton("开始校准")

            self.btn_refresh = QPushButton("刷新结果")
            _style_button(self.btn_connect, role="success")
            _style_button(self.btn_disconnect, role="danger")
            _style_button(self.btn_start, role="primary", state="idle")
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
            top_left = frame_geometry.topLeft()
            offset_x = 200
            offset_y = 48
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
            left = QVBoxLayout()
            title_row = QHBoxLayout()
            title_row.addWidget(self.logo_badge)
            title_row.addWidget(self.logo_title)
            title_row.addStretch(1)
            left.addLayout(title_row)
            layout.addLayout(left, 1)
            meta = QVBoxLayout()
            config_name = vm.catalog.display_name or vm.catalog.name or "未命名链路配置"
            self.project_label = QLabel(f"当前配置：{config_name}")
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
            self.step_hint = QLabel("选择左侧步骤后，在细分步骤框中查看 STEP1、STEP2、STEP3。")
            self.step_hint.setStyleSheet("color: #64748B;")
            center_layout.addWidget(self.step_hint)

            execution_body = QSplitter(Qt.Horizontal)

            substep_box = QGroupBox("细分步骤")
            substep_box.setMinimumWidth(220)
            substep_layout = QVBoxLayout(substep_box)
            substep_layout.addWidget(self.substep_list)

            detail_box = QWidget()
            detail_layout = QVBoxLayout(detail_box)
            detail_layout.setContentsMargins(0, 0, 0, 0)
            detail_layout.addWidget(QLabel("接线路径"))
            detail_layout.addWidget(self.path_view)
            detail_layout.addWidget(QLabel("命令 / 说明"))
            detail_layout.addWidget(self.command_view)
            detail_layout.addWidget(QLabel("步骤详情"))
            detail_layout.addWidget(self.detail_view)

            execution_body.addWidget(substep_box)
            execution_body.addWidget(detail_box)
            execution_body.setStretchFactor(0, 1)
            execution_body.setStretchFactor(1, 3)
            center_layout.addWidget(execution_body, 1)

            button_row = QHBoxLayout()
            button_row.addWidget(self.btn_start)
            button_row.addStretch(1)
            center_layout.addLayout(button_row)
            center_stack_layout.addWidget(center, 1)

            page_splitter = QSplitter(Qt.Horizontal)
            page_splitter.addWidget(left)
            page_splitter.addWidget(center_stack)
            page_splitter.setStretchFactor(0, 1)
            page_splitter.setStretchFactor(1, 3)
            layout.addWidget(page_splitter)
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
            vm.selected_step_changed.connect(self._sync_step_list_colored)
            vm.step_view_changed.connect(self._sync_step_view)
            vm.step_view_changed.connect(self._sync_step_list_colored)
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

        @staticmethod
        def _list_status_text(status: str) -> str:
            return {
                "pending": "未开始",
                "running": "进行中",
                "done": "已完成",
            }.get(status, "未开始")

        @staticmethod
        def _list_status_palette(status: str) -> tuple[str, str, bool]:
            return {
                "pending": ("#6d7b86", "#f5f7f8", False),
                "running": ("#9a6b17", "#fff4df", True),
                "done": ("#356a45", "#edf6ef", True),
            }.get(status, ("#6d7b86", "#f5f7f8", False))

        def _apply_status_style(self, item: QListWidgetItem, status: str) -> None:
            foreground, background, bold = self._list_status_palette(status)
            item.setForeground(QBrush(QColor(foreground)))
            item.setBackground(QBrush(QColor(background)))
            font = item.font()
            font.setBold(bold)
            item.setFont(font)
            item.setToolTip(self._list_status_text(status))

        def _sync_item_list(self) -> None:
            current_item_id = vm.selected_item.id if vm.catalog.items else ""
            self.item_list.blockSignals(True)
            self.item_list.clear()
            current_row = 0
            for index, item in enumerate(vm.catalog.items):
                status = vm.item_progress_state(item.id)
                list_item = QListWidgetItem(
                    f"{self._list_status_text(status)}\n{item.id}\n{_friendly_text(item.name)}"
                )
                self._apply_status_style(list_item, status)
                self.item_list.addItem(list_item)
                if item.id == current_item_id:
                    current_row = index
            if vm.catalog.items:
                self.item_list.setCurrentRow(current_row)
            self.item_list.blockSignals(False)

        def _sync_item_detail(self) -> None:
            item = vm.selected_item
            self.item_summary.setText(
                f"ID: {item.id}\n"
                f"名称: {_friendly_text(item.name)}\n"
                f"步骤数: {len(item.steps)}\n"
                f"用途: {_friendly_text(item.purpose)}"
            )
            self._sync_step_list_colored()
            self._sync_overview()

        def _sync_step_list_colored(self) -> None:
            item = vm.selected_item
            self.step_list.blockSignals(True)
            self.step_list.clear()
            for index, step in enumerate(item.steps, start=1):
                status = vm.step_progress_state(item.id, step.id)
                list_item = QListWidgetItem(
                    f"{self._list_status_text(status)}\n{index}. {step.id}\n{_friendly_text(step.name)}"
                )
                self._apply_status_style(list_item, status)
                self.step_list.addItem(list_item)
            if item.steps:
                self.step_list.setCurrentRow(vm.selected_step_index)
            self.step_list.blockSignals(False)
            current_step = vm.selected_step
            if current_step:
                self._sync_step_view(
                    vm._step_view_data(current_step, vm.selected_step_index + 1, len(item.steps))
                )
                self._sync_substep_list()
                self.step_hint.setText(f"当前步骤：{current_step.id} · {_friendly_text(current_step.name)}")
            else:
                self.substep_list.clear()
                self.step_hint.setText("当前校准项暂无步骤。")

        def _sync_step_view(self, step: StepViewData) -> None:
            substep_text = ""
            if step.substep_id:
                substep_text = f" | 小步骤 {step.substep_index}/{step.substep_total}: {_friendly_text(step.substep_name)}"
            self.step_title.setText(f"[{step.step_index}/{step.step_total}] {step.step_id} - {_friendly_text(step.step_name)}{substep_text}")
            self.step_status.setText(f"状态：{step.status}")
            total_substeps = max(step.item_total_substeps, 1)
            progress = int(step.item_completed_substeps / total_substeps * 100)
            self.step_progress.setValue(progress)
            self._sync_substep_list(step)
            self.path_view.setHtml(_format_path_html(step))
            self.command_view.setPlainText("\n".join(step.link_commands) if step.link_commands else "无链路命令")
            phase_text = ""
            if step.confirm_phase == "start":
                phase_text = "确认阶段: 开始前确认\n"
            elif step.confirm_phase == "saved":
                phase_text = "确认阶段: 数据保存完成确认\n"
            self.detail_view.setPlainText(
                phase_text
                + (f"小步骤: {step.substep_id} {_friendly_text(step.substep_name)}\n" if step.substep_id else "")
                + f"输入端口: {_friendly_node_text(step.input_port)}\n"
                f"输出端口: {_friendly_node_text(step.output_port)}\n"
                f"原始输出: {_plain_join(step.raw_outputs)}\n"
                f"最终输出: {_plain_join(step.final_outputs)}\n"
                f"所需输入: {_plain_join(step.required_inputs)}\n"
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
            item_id = vm.selected_item.id
            active_id = active_step.substep_id if active_step and active_step.step_id == step.id else ""
            phase = active_step.confirm_phase if active_step and active_id else ""
            current_row = -1
            for index, substep in enumerate(vm.substep_view_data(step), start=1):
                status = vm.substep_progress_state(item_id, step.id, substep.id)
                if substep.id == active_id:
                    phase_text = "开始确认" if phase == "start" else "保存确认"
                    prefix = f"当前 {phase_text}"
                    current_row = index - 1
                elif status == "done":
                    prefix = "已完成"
                elif status == "running":
                    prefix = "进行中"
                else:
                    prefix = "未开始"
                detail = substep.raw_output or substep.final_output
                detail_text = detail if detail else _friendly_text(substep.name)
                list_item = QListWidgetItem(
                    f"{prefix}\nSTEP{index}. {substep.id}\n{_friendly_text(substep.name)}\n{detail_text}"
                )
                self._apply_status_style(list_item, status)
                self.substep_list.addItem(list_item)
                if substep.id == active_id:
                    current_row = index - 1
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
            self.connection_label.setText(f"网分: {vna} | 信号源: {sg} | 链路箱: {link_box} | 频谱仪: {sa}")
            self.status_label.setText(str(overview.get("status", "Ready")))
            self._sync_start_button_state(str(overview.get("status", "Ready")))

        def _on_state_changed(self, state: str) -> None:
            self.step_status.setText(f"状态：{state}")
            self._sync_start_button_state(state)

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
                    f"大步骤: {step.step_id} - {_friendly_text(step.step_name)}\n"
                    f"小步骤: {step.substep_index}/{step.substep_total} {step.substep_id} - {_friendly_text(step.substep_name)}\n"
                    f"输入端口: {_friendly_node_text(step.input_port or '无')}\n"
                    f"输出端口: {_friendly_node_text(step.output_port or '无')}\n\n"
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
                f"大步骤: {step.step_id} - {_friendly_text(step.step_name)}\n"
                f"小步骤: {step.substep_index}/{step.substep_total} {step.substep_id} - {_friendly_text(step.substep_name)}\n"
                f"原始输出: {_plain_join(step.raw_outputs)}\n"
                f"最终输出: {_plain_join(step.final_outputs)}"
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
            action = self._show_modal_dialog(
                title=title,
                message=message,
                buttons=(
                    *tuple(("上一步", action, "left") for label, action in actions if action == "retry"),
                    *tuple((label, action, "center") for label, action in actions if action not in {"retry", "skip"}),
                    *tuple(("下一步", action, "right") for label, action in actions if action == "skip"),
                ),
                default_action=default_action,
                width=620,
                height=320,
            )
            vm.submit_action(action or "cancel")

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

        def _confirm_start_calibration(self) -> None:
            item = vm.selected_item
            action = self._show_modal_dialog(
                title="开始校准确认",
                message=(
                    f"确认开始执行 {item.id} - {_friendly_text(item.name)}？\n\n"
                    "步骤列表显示校准项，步骤执行区会逐个小步骤等待确认。"
                ),
                buttons=(("开始校准", "yes", "center"), ("取消", "cancel", "center")),
                default_action="yes",
                width=520,
                height=240,
            )
            if action == "yes":
                vm.start_selected()

        def _confirm_run_finished(self, summary: object) -> None:
            data = dict(summary) if isinstance(summary, dict) else {}
            self._sync_start_button_state("DONE")
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
            if normalized in {"DONE"}:
                button_state = "done"
            elif normalized in {"FAILED", "CANCELLED", "ERROR"} or normalized.startswith("ERROR"):
                button_state = "error"
            elif normalized in {"IDLE", "READY"}:
                button_state = "idle"
            else:
                button_state = "running"
            _style_button(self.btn_start, role="primary", state=button_state)

        def _clear_log_filters(self, panel: LogPanel) -> None:
            panel.clear_filters()
            self._sync_logs()

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
                f"项目: {_friendly_text(overview.get('item_name', ''))}",
                f"当前步骤: {overview.get('selected_step_id', '')}",
                f"状态: {overview.get('status', '')}",
                f"校准步数: {overview.get('steps', '')}",
                f"连接: {'OK' if self._all_command_devices_connected(overview) else '待连接'}",
                f"已完成步骤: {run_summary.get('completed_steps', 0) if isinstance(run_summary, dict) else 0}",
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
                lines.append(f"completed_steps: {run_summary.get('completed_steps', '')}")
                lines.append(f"last_event: {_friendly_text(run_summary.get('last_event', ''))}")
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
    style_text = _load_text(style_dir / "style_bule.qss")
    app.setStyleSheet(style_text)

    window = MainWindow()
    window._center_on_screen()
    window.show()
    return app.exec()
