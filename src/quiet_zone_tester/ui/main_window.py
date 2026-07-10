from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from quiet_zone_tester.hardware import InstrumentInfo, Position
from quiet_zone_tester.models import SParameterTrace, ScanVolume
from quiet_zone_tester.application import ScanWorkflowState
from quiet_zone_tester.presentation.modules.motion_control import PositionTracker
from quiet_zone_tester.resources import resource_path
from quiet_zone_tester.services import InstrumentService
from quiet_zone_tester.application.task_runner import TaskRunner
from quiet_zone_tester.ui.widgets.connection_panel import ConnectionPanel
from quiet_zone_tester.ui.widgets.live_plot_panel import LivePlotPanel
from quiet_zone_tester.ui.widgets.positioner_control_panel import PositionerControlPanel
from quiet_zone_tester.ui.widgets.scan_animation_panel import ScanAnimationPanel
from quiet_zone_tester.ui.widgets.status_log_panel import StatusLogPanel
from quiet_zone_tester.ui.widgets.switch_box_control_panel import SwitchBoxControlPanel
from quiet_zone_tester.ui.widgets.test_setup_panel import TestSetupPanel
from quiet_zone_tester.ui.widgets.vna_control_panel import VnaControlPanel


APP_TITLE = "微波暗室静区测试系统"
APP_ICON_NAME = "gtslogo_icon.png"


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: InstrumentService | None = None,
        task_runner_factory: Callable[[QObject | None], TaskRunner] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon(str(resource_path(APP_ICON_NAME))))

        self._service = service or InstrumentService()
        self._tasks = (task_runner_factory or TaskRunner)(self)
        self._scan_workflow = ScanWorkflowState()
        self._latest_trace: SParameterTrace | None = None
        self._position_tracker = PositionTracker(
            task_runner=self._tasks,
            is_connected=lambda: self._service.is_positioner_connected,
            query_position=self._service.query_positioner_position,
            parent=self,
        )
        self._position_tracker.position_ready.connect(self._on_positioner_motion_poll_ready)
        self._position_tracker.position_failed.connect(self._on_positioner_motion_poll_failed)

        self._connection_panel = ConnectionPanel()
        self._positioner_control_panel = PositionerControlPanel()
        self._positioner_control_dialog: QDialog | None = None
        self._vna_control_panel = VnaControlPanel()
        self._vna_control_dialog: QDialog | None = None
        self._switch_box_control_panel = SwitchBoxControlPanel()
        self._switch_box_control_dialog: QDialog | None = None
        self._test_setup_panel = TestSetupPanel()
        self._scan_animation_panel = ScanAnimationPanel()
        self._plot_panel = LivePlotPanel()
        self._log_panel = StatusLogPanel()

        self._build_menu_bar()
        self._build_layout()
        self._connect_signals()
        self._preview_scan_volume(self._test_setup_panel.current_settings())
        self.statusBar().showMessage("就绪")
        self._log_panel.append_info("应用已启动。真实测试模式下，网分仪、扫描架和开关箱全部连接后才能开始测试。")

    def _build_menu_bar(self) -> None:
        vna_menu = self.menuBar().addMenu("网分仪")
        open_vna_control_action = QAction("网分配置与采样", self)
        open_vna_control_action.triggered.connect(self._show_vna_control)
        vna_menu.addAction(open_vna_control_action)

        positioner_menu = self.menuBar().addMenu("扫描架")
        open_control_action = QAction("扫描架控制", self)
        open_control_action.triggered.connect(self._show_positioner_control)
        positioner_menu.addAction(open_control_action)

        switch_box_menu = self.menuBar().addMenu("开关箱")
        open_switch_box_action = QAction("开关箱控制", self)
        open_switch_box_action.triggered.connect(self._show_switch_box_control)
        switch_box_menu.addAction(open_switch_box_action)

    def _build_layout(self) -> None:
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._connection_panel, 1)
        left_layout.addWidget(self._test_setup_panel, 0)
        left_column.setMinimumWidth(620)
        left_column.setMaximumWidth(860)
        self._connection_panel.setMinimumHeight(460)
        self._connection_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._test_setup_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        top_right_splitter = QSplitter(Qt.Horizontal)
        top_right_splitter.addWidget(self._scan_animation_panel)
        top_right_splitter.addWidget(self._log_panel)
        top_right_splitter.setSizes([680, 300])
        top_right_splitter.setChildrenCollapsible(False)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(top_right_splitter)
        right_splitter.addWidget(self._plot_panel)
        right_splitter.setSizes([380, 360])
        right_splitter.setChildrenCollapsible(False)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(left_column)
        body_layout.addWidget(right_splitter)
        body_layout.setStretch(0, 0)
        body_layout.setStretch(1, 1)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(10, 8, 10, 8)
        central_layout.setSpacing(8)
        central_layout.addWidget(self._build_header())
        central_layout.addWidget(body, 1)

        self._plot_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._log_panel.setMinimumWidth(260)
        self._log_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setCentralWidget(central)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("appHeader")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setFixedSize(54, 54)
        icon_label.setAlignment(Qt.AlignCenter)
        icon = QPixmap(str(resource_path(APP_ICON_NAME)))
        if not icon.isNull():
            icon_label.setPixmap(icon.scaled(46, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        title_label = QLabel(APP_TITLE)
        title_font = QFont("Microsoft YaHei UI", 24, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #000000; font-weight: 800;")

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addStretch(1)
        return header

    def _connect_signals(self) -> None:
        self._connection_panel.connect_all_requested.connect(self._connect_all)
        self._connection_panel.connect_vna_requested.connect(self._connect_vna)
        self._connection_panel.connect_positioner_requested.connect(self._connect_positioner)
        self._connection_panel.connect_switch_box_requested.connect(self._connect_switch_box)
        self._connection_panel.positioner_axis_move_requested.connect(self._move_positioner_axis)
        self._connection_panel.positioner_axis_stop_requested.connect(self._stop_positioner_axis)
        self._connection_panel.positioner_default_speed_changed.connect(
            self._test_setup_panel.set_positioner_default_speed
        )
        self._connection_panel.disconnect_all_requested.connect(self._disconnect_all)
        self._connection_panel.disconnect_vna_requested.connect(self._disconnect_vna)
        self._connection_panel.disconnect_positioner_requested.connect(self._disconnect_positioner)
        self._connection_panel.disconnect_switch_box_requested.connect(self._disconnect_switch_box)

        self._positioner_control_panel.query_position_requested.connect(self._query_positioner_position)
        self._positioner_control_panel.absolute_move_requested.connect(self._move_positioner_absolute)
        self._positioner_control_panel.relative_move_requested.connect(self._move_positioner_relative)
        self._positioner_control_panel.stop_requested.connect(self._stop_positioner_from_control)

        self._vna_control_panel.configure_requested.connect(self._configure_vna_from_control)
        self._vna_control_panel.sample_requested.connect(self._start_vna_control_sample)

        self._switch_box_control_panel.command_requested.connect(self._send_switch_box_command)
        self._plot_panel.polarization_changed.connect(self._route_switch_box_polarization)
        self._plot_panel.dut_path_requested.connect(self._route_switch_box_dut_path)

        self._test_setup_panel.config_changed.connect(self._preview_scan_volume)
        self._test_setup_panel.vna_sample_requested.connect(self._start_vna_sample)
        self._test_setup_panel.scan_requested.connect(self._start_scan_flow)
        self._test_setup_panel.pause_requested.connect(self._pause_sampling)
        self._test_setup_panel.resume_requested.connect(self._resume_sampling)
        self._test_setup_panel.stop_requested.connect(self._stop_sampling)

        self._scan_animation_panel.progress_changed.connect(self._on_scan_progress_changed)
        self._scan_animation_panel.probe_position_refresh_requested.connect(
            self._refresh_scan_animation_probe_position
        )

    def _show_positioner_control(self) -> None:
        if self._positioner_control_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("扫描架控制")
            dialog.setWindowModality(Qt.NonModal)
            dialog.setAttribute(Qt.WA_DeleteOnClose, False)
            layout = QVBoxLayout(dialog)
            layout.addWidget(self._positioner_control_panel)
            dialog.resize(420, 520)
            self._positioner_control_dialog = dialog

        self._positioner_control_dialog.show()
        self._positioner_control_dialog.raise_()
        self._positioner_control_dialog.activateWindow()

    def _show_vna_control(self) -> None:
        if self._vna_control_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("网分仪配置与采样")
            dialog.setWindowModality(Qt.NonModal)
            dialog.setAttribute(Qt.WA_DeleteOnClose, False)
            layout = QVBoxLayout(dialog)
            layout.addWidget(self._vna_control_panel)
            dialog.resize(420, 360)
            self._vna_control_dialog = dialog

        self._vna_control_dialog.show()
        self._vna_control_dialog.raise_()
        self._vna_control_dialog.activateWindow()

    def _show_switch_box_control(self) -> None:
        if self._switch_box_control_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("开关箱控制")
            dialog.setWindowModality(Qt.NonModal)
            dialog.setAttribute(Qt.WA_DeleteOnClose, False)
            layout = QVBoxLayout(dialog)
            layout.addWidget(self._switch_box_control_panel)
            dialog.resize(860, 780)
            self._switch_box_control_dialog = dialog

        self._switch_box_control_dialog.show()
        self._switch_box_control_dialog.raise_()
        self._switch_box_control_dialog.activateWindow()

    def _connect_all(self, config: dict) -> None:
        self._set_busy(True)
        self.statusBar().showMessage("正在连接全部仪器...")
        self._log_panel.append_info("开始连接网分仪、扫描架和开关箱。")
        self._tasks.run(
            lambda: self._service.connect_all(config),
            on_success=self._on_all_connected,
            on_error=partial(self._on_connection_failed, "全部连接失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _connect_vna(self, config: dict) -> None:
        self._set_busy(True)
        self.statusBar().showMessage("正在连接网分仪...")
        self._log_panel.append_info("开始连接网分仪。")
        self._tasks.run(
            lambda: self._service.connect_vna(config),
            on_success=self._on_vna_connected,
            on_error=partial(self._on_connection_failed, "网分仪连接失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _connect_positioner(self, config: dict) -> None:
        self._set_busy(True)
        self.statusBar().showMessage("正在连接扫描架...")
        self._log_panel.append_info("开始连接扫描架。")
        self._tasks.run(
            lambda: self._service.connect_positioner(config),
            on_success=self._on_positioner_connected,
            on_error=partial(self._on_connection_failed, "扫描架连接失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _connect_switch_box(self, config: dict) -> None:
        self._set_busy(True)
        self.statusBar().showMessage("正在连接开关箱...")
        self._log_panel.append_info("开始连接开关箱。")
        self._tasks.run(
            lambda: self._service.connect_switch_box(config),
            on_success=self._on_switch_box_connected,
            on_error=partial(self._on_connection_failed, "开关箱连接失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _move_positioner_axis(self, config: dict, axis_name: str) -> None:
        axis = self._axis_id_from_config(config, axis_name)
        speed = float(config.get("positioner", {}).get("default_speed", 20.0))
        self._set_busy(True)
        self.statusBar().showMessage(f"正在运动{axis_name}轴...")
        self._log_panel.append_info(f"扫描架手动运动：{axis_name} 轴，速度 {speed:.3f} mm/s。")
        self._tasks.run(
            lambda: self._service.jog_positioner_axis(axis, speed, config),
            on_error=partial(self._on_operation_failed, "扫描架运动失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _stop_positioner_axis(self, config: dict, axis_name: str) -> None:
        axis = self._axis_id_from_config(config, axis_name)
        self.statusBar().showMessage(f"正在停止{axis_name}轴...")
        self._log_panel.append_info(f"扫描架手动停止：{axis_name} 轴。")
        self._tasks.run(
            lambda: self._service.stop_positioner_axis(axis),
            on_error=partial(self._on_operation_failed, "扫描架停止失败"),
        )

    def _query_positioner_position(self) -> None:
        self._set_busy(True)
        self.statusBar().showMessage("正在查询扫描架当前位置...")
        self._log_panel.append_info("查询扫描架当前位置。")
        self._tasks.run(
            lambda: self._service.query_positioner_position(self._connection_panel.current_config()),
            on_success=self._on_positioner_position_ready,
            on_error=partial(self._on_operation_failed, "扫描架位置查询失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _move_positioner_absolute(self, command: dict) -> None:
        x_mm = float(command["x_mm"])
        y_mm = float(command["y_mm"])
        speed_mm_s = float(command["speed_mm_s"])
        self._set_busy(True)
        self._start_positioner_motion_polling()
        self.statusBar().showMessage("正在执行扫描架绝对定位...")
        self._log_panel.append_info(f"扫描架绝对定位：X={x_mm:.3f} mm，Y={y_mm:.3f} mm，速度 {speed_mm_s:.3f} mm/s。")
        self._tasks.run(
            lambda: self._service.move_positioner_absolute(
                x_mm,
                y_mm,
                speed_mm_s,
                self._connection_panel.current_config(),
            ),
            on_success=self._on_positioner_position_ready,
            on_error=partial(self._on_operation_failed, "扫描架绝对定位失败"),
            on_finished=self._finish_positioner_move,
        )

    def _move_positioner_relative(self, command: dict) -> None:
        delta_x_mm = float(command["delta_x_mm"])
        delta_y_mm = float(command["delta_y_mm"])
        speed_mm_s = float(command["speed_mm_s"])
        self._set_busy(True)
        self._start_positioner_motion_polling()
        self.statusBar().showMessage("正在执行扫描架相对定位...")
        self._log_panel.append_info(
            f"扫描架相对定位：ΔX={delta_x_mm:.3f} mm，ΔY={delta_y_mm:.3f} mm，速度 {speed_mm_s:.3f} mm/s。"
        )
        self._tasks.run(
            lambda: self._service.move_positioner_relative(
                delta_x_mm,
                delta_y_mm,
                speed_mm_s,
                self._connection_panel.current_config(),
            ),
            on_success=self._on_positioner_position_ready,
            on_error=partial(self._on_operation_failed, "扫描架相对定位失败"),
            on_finished=self._finish_positioner_move,
        )

    def _stop_positioner_from_control(self) -> None:
        self.statusBar().showMessage("正在停止扫描架...")
        self._log_panel.append_info("扫描架控制页面请求停止。")
        self._tasks.run(
            self._service.stop_positioner,
            on_error=partial(self._on_operation_failed, "扫描架停止失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _refresh_scan_animation_probe_position(self) -> None:
        self._set_busy(True)
        self.statusBar().showMessage("正在刷新探头当前位置...")
        self._log_panel.append_info("刷新扫描动画探头当前位置。")
        self._tasks.run(
            lambda: self._service.query_positioner_position(self._connection_panel.current_config()),
            on_success=self._on_scan_animation_probe_position_ready,
            on_error=partial(self._on_operation_failed, "探头位置刷新失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _on_scan_animation_probe_position_ready(self, position: object) -> None:
        if not isinstance(position, Position):
            self._on_operation_failed("探头位置刷新失败", "业务层返回了未知位置数据。")
            return

        self._scan_animation_panel.set_probe_center_position(position.x_mm, position.y_mm)
        self.statusBar().showMessage("探头位置已刷新")
        self._log_panel.append_info(f"探头当前位置：X={position.x_mm:.3f} mm，Y={position.y_mm:.3f} mm。")

    def _start_positioner_motion_polling(self) -> None:
        self._position_tracker.start()

    def _finish_positioner_move(self) -> None:
        self._position_tracker.stop()
        self._set_busy(False)

    def _on_positioner_motion_poll_ready(self, position: object) -> None:
        if isinstance(position, Position):
            self._positioner_control_panel.set_current_position(position)

    def _on_positioner_motion_poll_failed(self, message: str) -> None:
        self._log_panel.append_error(f"扫描架当前位置刷新失败: {self._format_error_message(message)}")

    def _configure_vna_from_control(self, settings: dict) -> None:
        self._set_busy(True)
        self.statusBar().showMessage("正在配置网分仪...")
        self._log_panel.append_info(
            "网分仪独立配置："
            f"{settings['parameter']}，"
            f"{settings['start_ghz']:.3f}-{settings['stop_ghz']:.3f} GHz，"
            f"{settings['points']} 点，"
            f"功率 {settings['vna_power_dbm']:.1f} dBm，"
            f"中频带宽 {settings['if_bandwidth_hz']:.0f} Hz。"
        )
        self._tasks.run(
            self._service.configure_vna_trace,
            on_success=lambda _: self._on_vna_control_configured(settings),
            on_error=partial(self._on_operation_failed, "网分仪配置失败"),
            on_finished=partial(self._set_busy, False),
            start_ghz=settings["start_ghz"],
            stop_ghz=settings["stop_ghz"],
            points=settings["points"],
            parameter=settings["parameter"],
            vna_power_dbm=settings["vna_power_dbm"],
            if_bandwidth_hz=settings["if_bandwidth_hz"],
        )

    def _start_vna_control_sample(self, settings: dict) -> None:
        self._latest_trace = None
        self._plot_panel.clear()
        self._set_busy(True)
        self.statusBar().showMessage("正在执行网分仪独立采样...")
        self._log_panel.append_info(f"网分仪独立采样：{settings['parameter']}。")
        self._tasks.run(
            lambda: self._service.sample_vna_trace(settings["parameter"], file_flag=self._plot_panel.file_flag()),
            on_success=self._on_single_trace_ready,
            on_error=partial(self._on_operation_failed, "网分仪采样失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _route_switch_box_polarization(self, polarization: str) -> None:
        polarization = str(polarization).strip().upper()
        if polarization not in {"H", "V"}:
            return

        self._set_busy(True)
        self.statusBar().showMessage("正在切换开关箱极化链路...")
        self._log_panel.append_info(f"开关箱按极化切换：{polarization}。")
        self._tasks.run(
            lambda: self._service.select_switch_box_polarization(polarization),
            on_success=partial(self._on_switch_box_command_done, polarization),
            on_error=partial(self._on_operation_failed, "开关箱切换失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _route_switch_box_dut_path(self, target: str) -> None:
        target = str(target).strip().upper()
        labels = {"VNA2": "网分", "SA": "信号源+频谱"}
        if target not in labels:
            return

        command = f"CONFigure:LINK DUT, AMP1, {target}"
        self._set_busy(True)
        self.statusBar().showMessage("正在切换 DUT 到仪表链路...")
        self._log_panel.append_info(f"DUT 到仪表链路切换：{labels[target]}。")
        self._tasks.run(
            lambda: self._service.send_switch_box_command(command),
            on_success=partial(self._on_switch_box_command_done, labels[target]),
            on_error=partial(self._on_operation_failed, "DUT 链路切换失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _send_switch_box_command(self, command: str) -> None:
        command = str(command).strip()
        self._set_busy(True)
        self.statusBar().showMessage("正在发送开关箱命令...")
        self._log_panel.append_info(f"发送开关箱命令：{command}。")
        self._tasks.run(
            lambda: self._service.send_switch_box_command(command),
            on_success=partial(self._on_switch_box_command_done, command),
            on_error=partial(self._on_operation_failed, "开关箱命令失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _disconnect_all(self) -> None:
        self._run_disconnect("全部断开", self._service.disconnect_all, self._on_all_disconnected)

    def _disconnect_vna(self) -> None:
        self._run_disconnect("网分仪断开", self._service.disconnect_vna, self._on_vna_disconnected)

    def _disconnect_positioner(self) -> None:
        self._run_disconnect("扫描架断开", self._service.disconnect_positioner, self._on_positioner_disconnected)

    def _disconnect_switch_box(self) -> None:
        self._run_disconnect("开关箱断开", self._service.disconnect_switch_box, self._on_switch_box_disconnected)

    def _run_disconnect(self, label: str, operation, on_success) -> None:
        self._set_busy(True)
        self.statusBar().showMessage(f"正在{label}...")
        self._log_panel.append_info(f"开始执行{label}。")
        self._tasks.run(
            operation,
            on_success=lambda _: on_success(),
            on_error=partial(self._on_operation_failed, f"{label}失败"),
            on_finished=partial(self._set_busy, False),
        )

    def _preview_scan_volume(self, settings: dict) -> None:
        if self._scan_workflow.sampling_active:
            return

        self._plot_panel.set_main_line_from_scan_settings(settings)
        try:
            volume = self._build_scan_volume(settings)
        except ValueError:
            return
        self._scan_animation_panel.set_probe_position_from_settings(settings)
        self._scan_animation_panel.preview_volume(volume)

    def _start_vna_sample(self, settings: dict) -> None:
        if not self._ensure_ready_for_test("无法采样"):
            return

        self._latest_trace = None
        self._scan_workflow.begin_preview_sample()
        self._plot_panel.clear()
        self._set_busy(True)
        self.statusBar().showMessage("正在采集网分曲线...")
        self._log_panel.append_info(
            "曲线采样："
            f"{settings['parameter']}，"
            f"{settings['start_ghz']:.3f}-{settings['stop_ghz']:.3f} GHz，"
            f"功率 {settings['vna_power_dbm']:.1f} dBm，"
            f"中频带宽 {settings['if_bandwidth_hz']:.0f} Hz。"
        )
        self._tasks.run(
            self._service.acquire_preview_trace,
            on_success=self._on_single_trace_ready,
            on_error=partial(self._on_operation_failed, "网分采样失败"),
            on_finished=partial(self._set_busy, False),
            start_ghz=settings["start_ghz"],
            stop_ghz=settings["stop_ghz"],
            points=settings["points"],
            parameter=settings["parameter"],
            polarization=self._plot_panel.polarization(),
            vna_power_dbm=settings["vna_power_dbm"],
            if_bandwidth_hz=settings["if_bandwidth_hz"],
            file_flag=self._plot_panel.file_flag(),
        )

    def _start_scan_flow(self, settings: dict) -> None:
        if self._scan_workflow.task_running or self._scan_workflow.stop_positioner_task_running:
            message = "上一轮扫描正在停止，请等待扫描架停稳后再开始。"
            self.statusBar().showMessage(message)
            self._log_panel.append_info(message)
            return

        if not self._ensure_ready_for_test("无法启动扫描流程"):
            return
        if not self._start_scan_animation(settings):
            return

        settings = dict(settings)
        self._plot_panel.set_main_line_from_scan_settings(settings)
        settings["polarization"] = self._plot_panel.polarization()
        settings["connection_config"] = self._connection_panel.current_config()
        settings["file_flag"] = self._plot_panel.file_flag()
        self._scan_workflow.mark_scan_task_running(True)
        self._set_busy(True)
        self._tasks.run(
            self._service.run_scan,
            on_success=self._on_scan_task_finished,
            on_error=self._on_scan_task_failed,
            on_finished=self._on_scan_task_finished_cleanup,
            on_progress=self._on_scan_task_progress,
            settings=settings,
        )

    def _start_scan_animation(self, settings: dict) -> bool:
        try:
            volume = self._build_scan_volume(settings)
        except ValueError as exc:
            self._on_operation_failed("参数错误", str(exc))
            return False

        self._latest_trace = None
        self._scan_workflow.begin_scan(volume.point_count)
        self._plot_panel.clear()
        self._test_setup_panel.set_sampling_active(True)
        self._test_setup_panel.set_sampling_paused(False)
        self._scan_animation_panel.set_probe_position_from_settings(settings)
        self._scan_animation_panel.start_scan(volume)
        self._set_busy(True)

        message = "扫描测试已启动。"
        self.statusBar().showMessage(message)
        self._log_scan_start(settings, volume, message)
        return True

    def _pause_sampling(self) -> None:
        if not self._scan_workflow.sampling_active or self._scan_workflow.paused:
            return

        self._scan_workflow.pause()
        self._service.request_pause()
        self._test_setup_panel.set_sampling_paused(True)
        self.statusBar().showMessage("正在暂停扫描测试...")
        self._log_panel.append_info("用户请求暂停扫描测试；当前动作完成后将停在安全点。")

    def _resume_sampling(self) -> None:
        if not self._scan_workflow.sampling_active or not self._scan_workflow.paused:
            return

        self._scan_workflow.resume()
        self._service.resume_scan()
        self._test_setup_panel.set_sampling_paused(False)
        self.statusBar().showMessage("扫描测试继续")
        self._log_panel.append_info("扫描测试继续。")

    def _stop_sampling(self) -> None:
        if not self._scan_workflow.sampling_active:
            return

        self._scan_workflow.request_stop()
        self._service.request_stop()
        self._test_setup_panel.set_sampling_active(False)
        self._test_setup_panel.set_sampling_paused(False)
        self._scan_animation_panel.stop_scan()
        self._set_busy(False)
        self.statusBar().showMessage("正在停止流程...")
        self._log_panel.append_info("用户停止当前流程。")
        self._scan_workflow.set_stop_positioner_task_running(True)
        self._set_busy(False)
        self._tasks.run(
            self._service.stop_positioner,
            on_error=partial(self._on_stop_positioner_failed, "扫描架停止失败"),
            on_finished=self._on_stop_positioner_finished,
        )

    def _on_stop_positioner_failed(self, title: str, message: str) -> None:
        message = self._format_error_message(message)
        self.statusBar().showMessage(title)
        self._log_panel.append_error(f"{title}: {message}")

    def _on_stop_positioner_finished(self) -> None:
        self._scan_workflow.set_stop_positioner_task_running(False)
        self._set_busy(False)

    def _on_all_connected(self, instruments: object) -> None:
        if isinstance(instruments, list):
            self._connection_panel.set_all_connected(instruments)
            self._vna_control_panel.set_vna_connected(len(instruments) > 0)
            self._positioner_control_panel.set_positioner_connected(len(instruments) > 1)
            self._switch_box_control_panel.set_switch_box_connected(len(instruments) > 2)
        self.statusBar().showMessage("全部仪器已连接")
        self._log_panel.append_info("网分仪、扫描架和开关箱连接完成。")

    def _on_vna_connected(self, info: object) -> None:
        if isinstance(info, InstrumentInfo):
            self._connection_panel.set_vna_connected(info)
            self._vna_control_panel.set_vna_connected(True)
        self.statusBar().showMessage("网分仪已连接")
        self._log_panel.append_info("网分仪连接完成。")

    def _on_positioner_connected(self, info: object) -> None:
        if isinstance(info, InstrumentInfo):
            self._connection_panel.set_positioner_connected(info)
            self._positioner_control_panel.set_positioner_connected(True)
        self.statusBar().showMessage("扫描架已连接")
        self._log_panel.append_info("扫描架连接完成。")

    def _on_switch_box_connected(self, info: object) -> None:
        if isinstance(info, InstrumentInfo):
            self._connection_panel.set_switch_box_connected(info)
            self._switch_box_control_panel.set_switch_box_connected(True)
        self.statusBar().showMessage("开关箱已连接")
        self._log_panel.append_info("开关箱连接完成。")

    def _on_connection_failed(self, title: str, message: str) -> None:
        self._on_operation_failed(title, self._format_error_message(message))

    def _on_all_disconnected(self) -> None:
        self._connection_panel.set_all_disconnected()
        self._vna_control_panel.set_vna_connected(False)
        self._positioner_control_panel.set_positioner_connected(False)
        self._switch_box_control_panel.set_switch_box_connected(False)
        self._clear_runtime_state()
        self.statusBar().showMessage("全部仪器已断开")
        self._log_panel.append_info("全部仪器已断开。")

    def _on_vna_disconnected(self) -> None:
        self._connection_panel.set_vna_disconnected()
        self._vna_control_panel.set_vna_connected(False)
        self._latest_trace = None
        self._plot_panel.clear()
        self.statusBar().showMessage("网分仪已断开")
        self._log_panel.append_info("网分仪已断开。")

    def _on_positioner_disconnected(self) -> None:
        self._position_tracker.stop()
        self._connection_panel.set_positioner_disconnected()
        self._positioner_control_panel.set_positioner_connected(False)
        self.statusBar().showMessage("扫描架已断开")
        self._log_panel.append_info("扫描架已断开。")

    def _on_switch_box_disconnected(self) -> None:
        self._connection_panel.set_switch_box_disconnected()
        self._switch_box_control_panel.set_switch_box_connected(False)
        self.statusBar().showMessage("开关箱已断开")
        self._log_panel.append_info("开关箱已断开。")

    def _on_single_trace_ready(self, trace: object) -> None:
        if not isinstance(trace, SParameterTrace):
            self._on_operation_failed("网分采样失败", "业务层返回了未知数据类型。")
            return

        self._latest_trace = trace
        self._plot_panel.set_trace(trace)
        self.statusBar().showMessage("网分曲线已更新")
        self._log_panel.append_info(f"网分曲线就绪：{trace.parameter}，{trace.frequency_hz.size} 点。")

    def _on_vna_control_configured(self, settings: dict) -> None:
        self.statusBar().showMessage("网分仪配置完成")
        self._log_panel.append_info(f"网分仪配置完成：{settings['parameter']}，后续可直接采样。")

    def _on_positioner_position_ready(self, position: object) -> None:
        if not isinstance(position, Position):
            self._on_operation_failed("扫描架位置更新失败", "业务层返回了未知位置数据。")
            return

        self._positioner_control_panel.set_position(position)
        self.statusBar().showMessage("扫描架位置已更新")
        self._log_panel.append_info(f"扫描架当前位置：X={position.x_mm:.3f} mm，Y={position.y_mm:.3f} mm。")

    def _on_switch_box_command_done(self, label: str, response: object) -> None:
        response_text = str(response or "").strip()
        message = f"{label} -> {response_text or '完成'}"
        self._switch_box_control_panel.set_result(message)
        self.statusBar().showMessage("开关箱命令已完成")
        self._log_panel.append_info(f"开关箱命令完成：{message}。")

    def _on_scan_task_progress(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 3:
            return

        completed_points, total_points, trace = payload
        self._scan_workflow.set_progress(int(completed_points), int(total_points))
        self._scan_animation_panel.set_progress(
            self._scan_workflow.completed_points,
            self._scan_workflow.total_points,
        )
        if isinstance(trace, SParameterTrace):
            self._latest_trace = trace
            self._plot_panel.set_trace(trace)
        if self._scan_workflow.paused:
            self.statusBar().showMessage(
                f"扫描测试暂停中：{self._scan_workflow.completed_points}/{self._scan_workflow.total_points}"
            )
            return
        self.statusBar().showMessage(
            f"扫描测试中：{self._scan_workflow.completed_points}/{self._scan_workflow.total_points}"
        )

    def _on_scan_task_finished(self, result: object) -> None:
        if isinstance(result, list) and result:
            trace = result[-1]
            if isinstance(trace, SParameterTrace):
                self._latest_trace = trace
                self._plot_panel.set_trace(trace)

    def _on_scan_task_failed(self, message: str) -> None:
        if self._scan_workflow.stop_requested or "已停止" in str(message):
            self._scan_workflow.mark_stopped()
            self._test_setup_panel.set_sampling_active(False)
            self._test_setup_panel.set_sampling_paused(False)
            self._scan_animation_panel.stop_scan()
            self.statusBar().showMessage("流程已停止")
            self._log_panel.append_info("扫描测试已停止。")
            return

        self._scan_workflow.mark_failed()
        self._test_setup_panel.set_sampling_active(False)
        self._test_setup_panel.set_sampling_paused(False)
        self._scan_animation_panel.stop_scan()
        self._on_operation_failed("扫描测试失败", message)

    def _on_scan_task_finished_cleanup(self) -> None:
        stop_requested, failed = self._scan_workflow.begin_finished_cleanup()

        if not self._scan_workflow.sampling_active:
            self._set_busy(False)
            self._test_setup_panel.set_sampling_paused(False)
            if stop_requested:
                self.statusBar().showMessage("流程已停止")
            self._scan_workflow.finish_inactive_cleanup()
            return

        self._scan_workflow.finish_success_cleanup()
        self._test_setup_panel.set_sampling_active(False)
        self._test_setup_panel.set_sampling_paused(False)
        self._set_busy(False)
        if not stop_requested and not failed:
            self.statusBar().showMessage("扫描测试完成")
            self._log_panel.append_info("扫描测试完成。")
            scan_output_dir = self._service.last_scan_output_dir
            if scan_output_dir is not None:
                self._log_panel.append_info(f"扫描数据目录：{scan_output_dir}")

    def _on_scan_progress_changed(self, completed_points: int, total_points: int) -> None:
        self._scan_workflow.set_progress(completed_points, total_points)

    def _clear_runtime_state(self) -> None:
        self._latest_trace = None
        self._scan_workflow.reset()
        self._position_tracker.reset()
        self._test_setup_panel.set_sampling_active(False)
        self._test_setup_panel.set_sampling_paused(False)
        self._positioner_control_panel.set_busy(False)
        self._vna_control_panel.set_busy(False)
        self._switch_box_control_panel.set_busy(False)
        self._scan_animation_panel.stop_scan()
        self._plot_panel.clear()

    def _log_scan_start(self, settings: dict, volume: ScanVolume, message: str) -> None:
        mode_text = "步进测试" if settings.get("scan_mode") == "step" else "匀速测试"
        self._log_panel.append_info(
            f"{message} "
            f"{mode_text}，"
            f"{settings['parameter']}，"
            f"极化 {settings.get('polarization', '-')}，"
            f"{settings['start_ghz']:.3f}-{settings['stop_ghz']:.3f} GHz，"
            f"功率 {settings['vna_power_dbm']:.1f} dBm，"
            f"中频带宽 {settings.get('if_bandwidth_hz', 1000.0):.0f} Hz，"
            f"步进速度 {settings['step_speed_mm_s']:.3f} mm/s，"
            f"匀速速度 {settings.get('continuous_speed_mm_s', settings['step_speed_mm_s']):.3f} mm/s，"
            f"X[{settings['x_start_mm']:.1f}, {settings['x_stop_mm']:.1f}] mm，"
            f"Y[{settings['y_start_mm']:.1f}, {settings['y_stop_mm']:.1f}] mm，"
            f"总扫描点 {volume.point_count}。"
        )

    @staticmethod
    def _axis_id_from_config(config: dict, axis_name: str) -> int:
        positioner_config = config.get("positioner", {})
        key = "y_axis" if axis_name.strip().upper() == "Y" else "x_axis"
        default_axis = 3 if key == "y_axis" else 2
        return int(positioner_config.get(key, default_axis))

    @staticmethod
    def _build_scan_volume(settings: dict) -> ScanVolume:
        return ScanVolume(
            x_start_mm=settings["x_start_mm"],
            x_stop_mm=settings["x_stop_mm"],
            y_start_mm=settings["y_start_mm"],
            y_stop_mm=settings["y_stop_mm"],
            step_x_mm=settings["step_x_mm"],
            step_y_mm=settings["step_y_mm"],
        )

    def _ensure_ready_for_test(self, title: str) -> bool:
        try:
            self._service.verify_ready_for_test()
        except Exception as exc:
            self._on_operation_failed(title, str(exc))
            return False
        return True

    def _on_operation_failed(self, title: str, message: str) -> None:
        message = self._format_error_message(message)
        self.statusBar().showMessage(title)
        self._log_panel.append_error(f"{title}: {message}")
        QMessageBox.critical(self, title, message)

    def _set_busy(self, busy: bool) -> None:
        connection_busy = self._scan_workflow.connection_busy(busy)
        test_busy = self._scan_workflow.test_busy(busy)
        self._connection_panel.set_busy(connection_busy)
        self._test_setup_panel.set_busy(test_busy)
        self._positioner_control_panel.set_busy(connection_busy)
        self._vna_control_panel.set_busy(connection_busy)
        self._switch_box_control_panel.set_busy(connection_busy)

    @staticmethod
    def _format_error_message(message: str) -> str:
        message = str(message or "未知错误").strip()
        if not message:
            return "未知错误"
        return message if len(message) <= 500 else f"{message[:500]}..."
