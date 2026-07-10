# 架构迁移进度记录

Status: Active
Domain: ARCH
Canonical: `docs/ARCH_TASK_PROGRESS.md`
Related: `docs/architecture_migration_plan.md`, `docs/ARCH_MIGRATION_TODO.md`
Last updated: 2026-07-10

本文档记录架构迁移过程中已经发生的重要实施、验证、风险和决策。待办事项仍维护在 `docs/ARCH_MIGRATION_TODO.md`。

### ARCH-TASK-20260709-001 - P0 迁移骨架和扫描基础模型

- 目标：完成入口职责确认、新目录骨架、扫描事实模型、扫描状态机和基础测试闭环。
- 完成：保留旧 `ui/`、`services/`、`drivers/`、`instruments/` 不动，新增 `application/`、`domains/`、`hardware/`、`presentation/`、`shared/` 骨架；新增 `ScanSession`、`TraceRecord`、`ScanEvent`、`ScanStateMachine`。
- 验证：`py_compile` 通过；`python -m unittest discover -s tests` 通过 5 个测试；主窗口 offscreen 初始化输出 `ok`。
- 风险：pytest 暂未安装到当前 Conda 环境，安装请求被审批层拦截；测试暂采用标准库 `unittest`，pytest 后续可直接收集。
- 后续：进入 P1，优先抽出 `FilenamePolicy` 和 `TraceStorage`，继续保持旧扫描流程输出不回归。
- 涉及文件：`src/quiet_zone_tester/domains/scan_management/`、`tests/`、`docs/ARCH_MIGRATION_TODO.md`。

### ARCH-TASK-20260709-002 - P1 文件命名和 TraceStorage 抽取

- 目标：把文件名清洗、探头偏置 tag、trace CSV、metadata、trace index 从 `InstrumentService` 中抽到数据管理域。
- 完成：新增 `FilenamePolicy` 和 `TraceStorage`；`InstrumentService` 保留原私有方法签名并委托到新模块，现有 UI 和扫描流程调用方式不变。
- 验证：`py_compile` 通过；`python -m unittest discover -s tests` 通过 11 个测试；主窗口 offscreen 初始化输出 `ok`。
- 风险：本阶段仍保留 `InstrumentService` 的兼容私有方法，后续拆 facade 时再删除旧壳；pytest 仍未安装，当前使用标准库 `unittest`。
- 后续：进入 P1-03，抽出 `ScanPlanner`，让二维动画和扫描执行逐步共用同一份路径规划。
- 涉及文件：`src/quiet_zone_tester/domains/data_management/`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_filename_policy.py`、`tests/test_trace_storage.py`。

### ARCH-TASK-20260709-003 - P1 ScanPlanner 抽取

- 目标：把 X 线段、Y 线段、二维蛇形路径和反向扫描路径规划从共享模型中抽到扫描管理域。
- 完成：新增 `ScanPlanner`、`ScanPlan`、`PlannedScanPoint`；`ScanVolume.point_count()` 和 `ScanVolume.scan_points()` 保留兼容 API 并委托 planner；`scan_points_from_volume()` 改为使用 planner 输出。现有步进扫描、匀速扫描和动画预览仍通过 `volume.scan_points()` 获取同一规划结果。
- 验证：当前 PATH Python 为 `D:\Microsoft\Miniconda3\python.exe`；设置 `PYTHONPATH=src` 后，`python -m unittest discover -s tests` 通过 16 个测试；相关文件 `py_compile` 通过。
- 风险：文档中 `D:\Microsoft\Miniconda\envs\TEST\python.exe` 在当前机器不存在，当前 PATH Python 未安装 PySide6，主窗口 offscreen 初始化因 `ModuleNotFoundError: No module named 'PySide6'` 未能执行；`conda env list` 被系统拒绝访问。
- 后续：进入 P1-04，抽出 `LinkRouter`，将 S 参数到开关箱命令/profile 的映射从驱动或 service 逻辑中独立出来。
- 涉及文件：`src/quiet_zone_tester/domains/scan_management/scan_planner.py`、`src/quiet_zone_tester/models/scan_config.py`、`src/quiet_zone_tester/domains/scan_management/models.py`、`tests/test_scan_planner.py`、`tests/test_scan_points.py`。

### ARCH-TASK-20260709-004 - P1 LinkRouter 抽取

- 目标：把 `S11/S21/S12/S22` 到开关箱命令的映射抽到链路管理域，并支持 LCD74000F、TC500 和 Mock profile。
- 完成：新增 `SwitchBoxProfile`、`LinkRouter`、`LinkRoute` 和默认 profile；Mock、TC500、LCD74000F 的 `select_s_parameter()` 保持原签名，但内部统一委托 router 解析命令；自定义 `s11_command/s21_command/s12_command/s22_command` 仍通过 profile 覆盖生效。
- 验证：设置 `PYTHONPATH=src` 后，`python -m unittest discover -s tests` 通过 20 个测试；`link_management`、开关箱驱动和 `InstrumentService` 相关文件 `py_compile` 通过。
- 风险：旧硬件 controller 暂时仍暴露 `select_s_parameter()` 兼容接口，后续 P2 硬件层迁移时可进一步收口为 `send_command()` + domain `LinkService`；当前 Python 仍缺少 PySide6，未重复执行主窗口 offscreen 初始化。
- 后续：进入 P1-05，引入连接配置 dataclass，并保留旧 `dict` API 适配。
- 涉及文件：`src/quiet_zone_tester/domains/link_management/`、`src/quiet_zone_tester/drivers/mock_switch_box.py`、`src/quiet_zone_tester/instruments/switch_box_tc500.py`、`src/quiet_zone_tester/instruments/switch_box_lcd74000f.py`、`tests/test_link_router.py`。

### ARCH-TASK-20260709-005 - P1 连接配置 dataclass 引入

- 目标：为 VNA、扫描架和开关箱连接配置建立 typed dataclass，并让旧 `dict` API 可继续工作。
- 完成：新增 `VnaConnectionConfig`、`PositionerConnectionConfig`、`SwitchBoxConnectionConfig`、`InstrumentConnectionConfig`；支持从当前 UI 嵌套 dict 和单设备 dict 构造，并可输出兼容旧 service/controller 的 dict；`InstrumentService.connect_all/connect_vna/connect_positioner/connect_switch_box/update_positioner_runtime_config` 入口开始接受 dataclass 或旧 dict。
- 验证：设置 `PYTHONPATH=src` 后，`python -m unittest discover -s tests` 通过 24 个测试；`instrument_management` 和 `InstrumentService` 相关文件 `py_compile` 通过。
- 风险：当前 PATH Python 缺少 `pyvisa`，`InstrumentService` 实际导入检查停在 `ModuleNotFoundError: No module named 'pyvisa'`；当前 Python 也缺少 PySide6，仍无法执行主窗口 offscreen 初始化。真实运行环境恢复后需要补一次完整导入和 UI 初始化检查。
- 后续：进入 P1-06，引入扫描配置 dataclass，逐步替代扫描设置散乱 dict 字段。
- 涉及文件：`src/quiet_zone_tester/domains/instrument_management/models.py`、`src/quiet_zone_tester/domains/instrument_management/__init__.py`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_connection_config.py`。

### ARCH-TASK-20260709-006 - P1 扫描配置 dataclass 引入

- 目标：为扫描设置建立 typed dataclass，减少 UI、扫描执行和数据保存之间散落的 `dict` 字段。
- 完成：新增 `SweepSettings`、`ProbeOffset`、`ScanSettings`；支持从当前 UI 的扁平 settings dict 构造，并通过 `to_dict()` 输出兼容旧流程的字段形状；`InstrumentService.run_scan` 和 `TraceStorage` 开始接受 `ScanSettings` 或旧 `dict`。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 29 个 `unittest`；相关扫描管理、数据管理和 service 文件 `py_compile` 通过。
- 风险：本阶段仍保留旧 `dict` 作为主要 UI 信号载荷，后续 ViewModel 迁移时再把 Widget 输出切换为 dataclass；`ScanSettings.to_dict()` 会保留未知 extra 字段以降低兼容风险。
- 后续：进入 P1-07，建立结构化 `LogRecordModel`，保留当前日志视图行为。
- 涉及文件：`src/quiet_zone_tester/domains/scan_management/models.py`、`src/quiet_zone_tester/domains/scan_management/__init__.py`、`src/quiet_zone_tester/domains/data_management/trace_storage.py`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_scan_settings.py`。

### ARCH-TASK-20260709-007 - P1 结构化日志模型

- 目标：把运行日志从纯文本追加逐步迁移为结构化 Qt Model，同时保留现有日志面板显示行为。
- 完成：新增 `LogRecord` 和 `LogRecordModel(QAbstractTableModel)`，包含时间、等级、来源、消息四列；`StatusLogPanel` 继续使用 `QPlainTextEdit` 显示旧格式文本，同时每条日志写入结构化 model；修复 `presentation/modules/logs/__init__.py` 为本地可读文件并导出日志模型。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 32 个 `unittest`；日志 model、状态日志面板、扫描配置和 service 相关文件 `py_compile` 通过。
- 风险：当前日志视图仍是文本控件，后续 P2/ViewModel 阶段可再切换到 `QTableView` 或过滤视图；本阶段只建立结构化数据源，不改变用户可见日志格式。
- 后续：P1 任务已完成，进入 P2 时优先选择低风险 ViewModel 迁移项，例如 `ConnectionPanel` 或 `TestSetupPanel`。
- 涉及文件：`src/quiet_zone_tester/presentation/modules/logs/log_record_model.py`、`src/quiet_zone_tester/presentation/modules/logs/__init__.py`、`src/quiet_zone_tester/ui/widgets/status_log_panel.py`、`tests/test_log_record_model.py`。

### ARCH-TASK-20260709-008 - P2 ConnectionPanel ViewModel 迁移

- 目标：把连接面板中的连接配置拼装、串口刷新、开关箱型号默认值逻辑迁入 ViewModel，保留现有 UI 行为和信号载荷。
- 完成：新增 `ConnectionViewModel`、`VnaFormState`、`PositionerFormState`、`SwitchBoxFormState`、`SwitchBoxModelDefaults`；`ConnectionPanel.current_config()` 委托 ViewModel 输出旧 dict 形状；VNA VISA 资源名、串口枚举、开关箱 LCD74000F/TC500 默认连接参数和串口/TCP 显示判断都由 ViewModel 提供。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 36 个 `unittest`；由于 OneDrive/权限导致 `py_compile` 写入 `__pycache__` 失败，改用 `compile(Path(...).read_text(...), file, 'exec')` 对相关文件完成不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：`ConnectionPanel` 仍负责控件创建、显示状态和按钮 enable 逻辑，本阶段只迁出纯配置/默认值/串口枚举逻辑；后续可继续把连接状态派生和命令对象迁入 ViewModel。
- 后续：进入 P2-02，迁移 `TestSetupPanel` 到 ViewModel，优先抽出扫描参数默认值、探头位置和预览配置。
- 涉及文件：`src/quiet_zone_tester/presentation/modules/connection/connection_view_model.py`、`src/quiet_zone_tester/presentation/modules/connection/__init__.py`、`src/quiet_zone_tester/ui/widgets/connection_panel.py`、`tests/test_connection_view_model.py`。

### ARCH-TASK-20260709-009 - P2 TestSetupPanel ViewModel 迁移

- 目标：把测试参数面板中的扫描设置构造、探头位置预设、步进距离和圈数换算迁入 ViewModel，保留现有 UI 信号和 settings dict。
- 完成：新增 `ScanSetupViewModel`、`ScanSetupFormState`、`ProbeOffsetPreset` 和扫描参数默认值；`TestSetupPanel.current_settings()` 委托 ViewModel 输出兼容旧流程的 settings dict；探头预设、连续模式步距计算、步进距离到圈数换算由 ViewModel 提供。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 41 个 `unittest`；对 `ScanSetupViewModel`、`scan_setup/__init__.py`、`TestSetupPanel` 使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：`TestSetupPanel` 仍负责控件创建、布局、可见性和按钮状态，本阶段只迁出纯参数逻辑；后续可继续将模式可见性和按钮状态派生迁入 ViewModel。
- 后续：进入 P2-03，迁移 `PositionerControlPanel` 到运动控制域，优先抽出手动运动命令和位置显示模型。
- 涉及文件：`src/quiet_zone_tester/presentation/modules/scan_setup/scan_setup_view_model.py`、`src/quiet_zone_tester/presentation/modules/scan_setup/__init__.py`、`src/quiet_zone_tester/ui/widgets/test_setup_panel.py`、`tests/test_scan_setup_view_model.py`。

### ARCH-TASK-20260709-010 - P2 PositionerControlPanel ViewModel 迁移

- 目标：把扫描架控制面板中的手动运动命令、当前位置显示和基础按钮状态派生迁入运动控制 ViewModel，保留现有 UI 信号载荷。
- 完成：新增 `MotionControlViewModel`、`AbsoluteMoveCommand`、`RelativeMoveCommand`、`PositionDisplay`、`MotionControlUiState`；`PositionerControlPanel` 的绝对/相对运动命令 dict、位置文本格式和 connected/busy 按钮状态委托 ViewModel；外部 `absolute_move_requested`、`relative_move_requested` 信号仍发旧 dict。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 46 个 `unittest`；对 `MotionControlViewModel`、`motion_control/__init__.py`、`PositionerControlPanel` 使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：MainWindow 中的位置轮询定时器仍未迁出，本阶段先完成 Widget 内纯逻辑迁移；后续拆 `MotionService` 时再把轮询流程和安全停止流程统一收口。
- 后续：进入 P2-04，迁移 `SwitchBoxControlPanel` 到链路管理域，优先抽出链路命令选择和面板状态。
- 涉及文件：`src/quiet_zone_tester/presentation/modules/motion_control/motion_control_view_model.py`、`src/quiet_zone_tester/presentation/modules/motion_control/__init__.py`、`src/quiet_zone_tester/ui/widgets/positioner_control_panel.py`、`tests/test_motion_control_view_model.py`。

### ARCH-TASK-20260709-011 - P2 SwitchBoxControlPanel ViewModel 迁移

- 目标：把开关箱控制面板中的链路命令列表、S 参数规范化、命令文本清洗、结果显示和按钮状态派生迁入链路控制 ViewModel。
- 完成：新增 `LinkControlViewModel` 和 `LinkControlUiState`；默认 LCD74000F 链路命令列表迁入 `presentation/modules/link_control`；`SwitchBoxControlPanel` 的参数切换信号、命令发送信号、当前命令文本、执行结果文本和 connected/busy 状态委托 ViewModel；面板外部 `parameter_requested`、`command_requested` 信号仍保持旧载荷。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 51 个 `unittest`；对 `LinkControlViewModel`、`link_control/__init__.py`、`SwitchBoxControlPanel` 使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：链路图绘制仍留在 Widget；真实开关箱执行仍通过 `InstrumentService.select_switch_box_parameter/send_switch_box_command`，后续 P2-05 拆 facade 时再引入更完整的 `LinkService`。
- 后续：进入 P2-05，将 `InstrumentService` 逐步变成 facade，优先抽取已经有基础模块的数据保存、链路路由和扫描规划委托边界。
- 涉及文件：`src/quiet_zone_tester/presentation/modules/link_control/link_control_view_model.py`、`src/quiet_zone_tester/presentation/modules/link_control/__init__.py`、`src/quiet_zone_tester/ui/widgets/switch_box_control_panel.py`、`tests/test_link_control_view_model.py`。

### ARCH-TASK-20260709-012 - P2 InstrumentService facade 链路控制抽取

- 目标：启动 `InstrumentService` facade 化，先把开关箱链路选择和原始命令发送委托到链路管理域。
- 完成：新增 `LinkService` 和 `LinkServiceError`；`InstrumentService.select_switch_box_parameter()` 与 `send_switch_box_command()` 保留原对外 API，但内部委托 `LinkService`；`LinkService` 只依赖开关箱控制器协议，不依赖 UI 和真实通信实现。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 55 个 `unittest`；对 `LinkService`、`link_management/__init__.py`、`InstrumentService` 使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：P2-05 尚未整体完成；运动、采样、扫描运行和连接创建仍主要留在 `InstrumentService`。本记录只代表链路控制职责已开始委托。
- 后续：继续 P2-05，优先抽出采样配置/采样执行或运动控制委托，逐步缩小 `InstrumentService`。
- 涉及文件：`src/quiet_zone_tester/domains/link_management/link_service.py`、`src/quiet_zone_tester/domains/link_management/__init__.py`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_link_service.py`。

### ARCH-TASK-20260709-013 - P2 InstrumentService facade 采样职责抽取

- 目标：继续 `InstrumentService` facade 化，把 VNA sweep 配置、IF 带宽配置和单次采样执行迁入采样域。
- 完成：新增 `AcquisitionService`、`AcquisitionServiceError` 和 `SweepConfiguration`；`InstrumentService.acquire_preview_trace()`、`configure_vna_trace()`、`sample_vna_trace()`、`_configure_vna_for_scan()` 与 `_measure_scan_trace()` 保留原 API，但 VNA 配置和测量调用委托到采样域；扫描配置路径保持原行为，不额外配置 measurement parameter。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 60 个 `unittest`；对 `AcquisitionService`、`acquisition/__init__.py`、`InstrumentService` 和新测试使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：P2-05 尚未整体完成；扫描运行编排、运动控制、连接创建和数据保存兼容壳仍在 `InstrumentService` 中。真实硬件命令顺序需要后续在硬件环境补一次联调验证。
- 后续：继续 P2-05，优先抽 `MotionService` 或扫描运行编排服务，逐步只让 `InstrumentService` 保留 facade 协调职责。
- 涉及文件：`src/quiet_zone_tester/domains/acquisition/acquisition_service.py`、`src/quiet_zone_tester/domains/acquisition/__init__.py`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_acquisition_service.py`。

### ARCH-TASK-20260709-014 - P2 InstrumentService facade 手动运动抽取

- 目标：继续 `InstrumentService` facade 化，把扫描架手动 jog、位置查询、绝对/相对运动和停止命令迁入运动控制域。
- 完成：新增 `MotionService` 和 `MotionServiceError`；`InstrumentService.jog_positioner_axis()`、`query_positioner_position()`、`move_positioner_absolute()`、`move_positioner_relative()`、`stop_positioner_axis()`、`stop_positioner()` 和 `request_stop()` 保留原 API，但实际运动命令委托到 `MotionService`；运行时配置解析仍暂留 `InstrumentService`，避免与连接配置适配混在同一步重构。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 64 个 `unittest`；对 `MotionService`、`motion_control/__init__.py`、`InstrumentService` 和新测试使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：连续扫描中的轴级运动编排仍留在 `InstrumentService`；本阶段只覆盖 UI 手动运动命令和停止命令。后续抽扫描运行服务时再统一处理轴级扫描运动。
- 后续：继续 P2-05，优先抽扫描运行编排服务或连接创建工厂，逐步降低 `InstrumentService` 的私有方法体量。
- 涉及文件：`src/quiet_zone_tester/domains/motion_control/motion_service.py`、`src/quiet_zone_tester/domains/motion_control/__init__.py`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_motion_service.py`。

### ARCH-TASK-20260710-015 - P2 InstrumentService facade 硬件创建工厂抽取

- 目标：继续 `InstrumentService` facade 化，把 VNA、扫描架和开关箱 controller 创建细节从 service 中移出。
- 完成：新增 `InstrumentControllerFactory` 和 `InstrumentControllerFactoryError`；VNA、扫描架、开关箱的虚拟/真实 controller 创建、真实模式 MOCK 拒绝、必填连接参数校验、扫描架轴号校验和每毫米单位换算迁入仪表管理域；`InstrumentService` 保留原私有创建/校验方法签名，但内部委托工厂，兼容现有调用。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 69 个 `unittest`；对 `InstrumentControllerFactory`、`instrument_management/__init__.py`、`InstrumentService` 和新测试使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：旧 `drivers/` 与 `instruments/` 目录尚未迁入 `hardware/`，本阶段只减少 `InstrumentService` 的硬件创建细节；后续 P2-06 仍需处理硬件层目录和统一接口。
- 后续：继续 P2-05，优先抽扫描运行编排服务，把步进/匀速扫描流程从 `InstrumentService` 中拆出。
- 涉及文件：`src/quiet_zone_tester/domains/instrument_management/controller_factory.py`、`src/quiet_zone_tester/domains/instrument_management/__init__.py`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_instrument_controller_factory.py`。

### ARCH-TASK-20260710-016 - P2 InstrumentService facade 扫描架运行时配置抽取

- 目标：继续收口运动控制职责，把扫描架运行时配置更新从 `InstrumentService` 下沉到运动控制域。
- 完成：`MotionService.update_runtime_config()` 接管 `update_runtime_config` controller 调用、轴号校验、每毫米单位换算和默认速度传递；`InstrumentService.update_positioner_runtime_config()` 保留原 API，但只负责把旧连接配置/dataclass 适配为 dict 并委托 `MotionService`。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 71 个 `unittest`；对 `MotionService`、`InstrumentControllerFactory`、`InstrumentService` 和相关测试使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：扫描流程内部的连续运动控制仍留在 `InstrumentService`；本阶段只迁出运行时配置更新，不改变扫描运动执行顺序。
- 后续：继续 P2-05，优先抽扫描运行编排服务，处理 `_run_step_scan()`、`_run_continuous_scan()` 和相关轴级运动 helper。
- 涉及文件：`src/quiet_zone_tester/domains/motion_control/motion_service.py`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_motion_service.py`。

### ARCH-TASK-20260710-017 - P2 InstrumentService facade 扫描运行几何和轴级运动抽取

- 目标：继续拆分扫描运行职责，把扫描点物理坐标映射、轴移动决策和轴级运动执行从 `InstrumentService` 中移出。
- 完成：新增 `ScanRuntimeGeometry`、`PhysicalOrigin` 和 `PhysicalTarget`，接管逻辑点到物理目标映射、扫描轴移动顺序、连续扫描下一段运动判断和采样前停轴判断；`MotionService` 新增 `move_axis_to()`、`jog_axis_until()`、`stop_axis_by_name_quietly()`、`axis_for_name()` 等轴级运动能力；`InstrumentService` 保留扫描编排和暂停/停止回调，相关私有 helper 改为委托。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 79 个 `unittest`；对 `ScanRuntimeGeometry`、`MotionService`、`InstrumentService` 和相关测试使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：`_run_step_scan()` 和 `_run_continuous_scan()` 的主循环仍在 `InstrumentService` 中，本阶段降低 helper 复杂度但尚未完成扫描运行服务抽取。
- 后续：继续 P2-05，优先抽 `ScanRuntimeService`，让 `InstrumentService.run_scan()` 只负责准备依赖、创建输出目录和调用扫描运行服务。
- 涉及文件：`src/quiet_zone_tester/domains/scan_management/scan_runtime_geometry.py`、`src/quiet_zone_tester/domains/scan_management/__init__.py`、`src/quiet_zone_tester/domains/motion_control/motion_service.py`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_scan_runtime_geometry.py`、`tests/test_motion_service.py`。

### ARCH-TASK-20260710-018 - P2 InstrumentService facade 扫描主循环抽取

- 目标：继续 P2-05，把步进扫描和匀速扫描主循环从 `InstrumentService` 中移到扫描管理域。
- 完成：新增 `ScanRuntimeService` 和 `ScanRuntimeServiceError`；步进/匀速扫描的路径遍历、进度回调、运动调用、采样调用、trace 保存调用、暂停/停止检查和部分结果返回逻辑迁入扫描运行服务；`InstrumentService._run_step_scan()` 与 `_run_continuous_scan()` 保留兼容私有方法，但内部只构造依赖并委托 `ScanRuntimeService`。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 82 个 `unittest`；对 `ScanRuntimeService`、`scan_management/__init__.py`、`InstrumentService` 和新测试使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：连接生命周期仍由 `InstrumentService.connect_*()` 和 `disconnect_*()` 直接编排；因此 P2-05 暂不勾选。后续应抽 `InstrumentConnectionService` 或类似服务收口连接/断开/清理流程。
- 后续：继续 P2-05，优先抽仪器连接生命周期服务，完成后再评估是否可勾选 P2-05。
- 涉及文件：`src/quiet_zone_tester/domains/scan_management/scan_runtime_service.py`、`src/quiet_zone_tester/domains/scan_management/__init__.py`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_scan_runtime_service.py`。

### ARCH-TASK-20260710-019 - P2 InstrumentService facade 连接生命周期抽取并完成 P2-05

- 目标：完成 P2-05，把连接、运动、链路、扫描、采样和数据保存职责都委托到独立 domain service 或工厂。
- 完成：新增 `InstrumentConnectionService` 和 `InstrumentConnectionServiceError`，接管 controller 重连前断开、单设备断开、全部断开、连接失败清理和单 controller 清理；`InstrumentService.connect_*()`、`disconnect_*()`、`disconnect_all()` 和清理方法保留原 API，但连接生命周期委托到 `InstrumentConnectionService`；扫描架静默停机和保存文件名前的位置查询也改为委托 `MotionService`。至此，`InstrumentService` 已成为 facade：连接生命周期委托 `InstrumentConnectionService`，硬件创建委托 `InstrumentControllerFactory`，运动委托 `MotionService`，链路委托 `LinkService`，扫描运行委托 `ScanRuntimeService`，采样委托 `AcquisitionService`，数据保存委托 `TraceStorage`。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 88 个 `unittest`；对 `InstrumentConnectionService`、`ScanRuntimeService`、`MotionService`、`InstrumentService` 和相关测试使用不写 pyc 的源码编译检查，输出 `compile-ok`。
- 风险：`InstrumentService` 仍保留若干兼容私有方法作为旧测试和旧调用路径的委托壳，后续可在 P2-06/P2-07 之后再逐步清理；真实硬件联调仍需在设备环境确认连接、扫描和停止流程。
- 后续：进入 P2-06，迁移 `drivers/` 和 `instruments/` 到 `hardware/`，并设计兼容导入或一次性更新引用。
- 涉及文件：`src/quiet_zone_tester/domains/instrument_management/connection_service.py`、`src/quiet_zone_tester/domains/instrument_management/__init__.py`、`src/quiet_zone_tester/domains/motion_control/motion_service.py`、`src/quiet_zone_tester/services/instrument_service.py`、`tests/test_instrument_connection_service.py`、`tests/test_motion_service.py`、`docs/ARCH_MIGRATION_TODO.md`。

### ARCH-TASK-20260710-020 - P2 硬件层目录迁移

- 目标：完成 P2-06，把旧 `drivers/` 和 `instruments/` 的硬件接口、Mock 实现、真实设备实现和通信 transport 迁移到 `hardware/`，并保持旧导入路径兼容。
- 完成：新增 `hardware/interfaces.py`、`hardware/mock/`、`hardware/vna/`、`hardware/positioner/`、`hardware/switch_box/`、`hardware/transport/`；业务层、UI 和测试改为从 `quiet_zone_tester.hardware` 导入硬件接口和 controller；旧 `drivers/` 与 `instruments/` 改为兼容 re-export，保留旧导入路径可用；新增硬件迁移测试确认新旧导入导出同一批类。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 91 个 `unittest`；对新 `hardware/` 层、旧兼容入口、`InstrumentService` 和硬件迁移测试使用不写 pyc 的源码编译检查，输出 `compile-ok`；主窗口 offscreen 初始化输出 `ok`。
- 风险：`hardware/__init__.py` 当前会导出常用真实硬件类，运行环境仍需要现有串口/VISA 依赖可导入；真实设备通信行为未在无硬件环境验证。
- 后续：进入 P2-07，拆分文档体系，补 APP、仪表、链路、运动、扫描、数据管理设计文档，并保留主文档入口。
- 涉及文件：`src/quiet_zone_tester/hardware/`、`src/quiet_zone_tester/drivers/`、`src/quiet_zone_tester/instruments/`、`src/quiet_zone_tester/domains/instrument_management/controller_factory.py`、`src/quiet_zone_tester/ui/`、`tests/test_hardware_migration.py`、`docs/ARCH_MIGRATION_TODO.md`。

### ARCH-TASK-20260710-021 - P2 文档体系拆分

- 目标：完成 P2-07，从主迁移方案拆出 APP、仪表、链路、运动、扫描、数据管理设计文档，并让主迁移方案回到架构入口职责。
- 完成：新增 `APP_DESIGN.md`、`INSTRUMENT_MANAGEMENT_DESIGN.md`、`LINK_MANAGEMENT_DESIGN.md`、`MOTION_CONTROL_DESIGN.md`、`SCAN_MANAGEMENT_DESIGN.md`、`DATA_MANAGEMENT_DESIGN.md` 和 `HARDWARE_ADAPTER_DESIGN.md`；每个设计文档记录职责、当前实现、边界、关键规则和后续迁移；`architecture_migration_plan.md` 增加文档入口索引，并将“文档治理建议”更新为当前文档治理规则；`ARCH_MIGRATION_TODO.md` 勾选 P2-07。
- 验证：本阶段仅修改文档；使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 91 个 `unittest`。
- 风险：设计文档仍是当前架构快照，后续继续迁移 `application/`、Qt Model/View 或硬件集成测试时需要同步更新对应 `*_DESIGN.md`。
- 后续：P2 当前任务已全部完成；下一阶段可基于业务域文档继续拆 `MainWindow` 顶层路由、应用上下文和剩余兼容壳。
- 涉及文件：`docs/architecture_migration_plan.md`、`docs/APP_DESIGN.md`、`docs/INSTRUMENT_MANAGEMENT_DESIGN.md`、`docs/LINK_MANAGEMENT_DESIGN.md`、`docs/MOTION_CONTROL_DESIGN.md`、`docs/SCAN_MANAGEMENT_DESIGN.md`、`docs/DATA_MANAGEMENT_DESIGN.md`、`docs/HARDWARE_ADAPTER_DESIGN.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-022 - P3 TODO 扩展与 APP 装配迁移

- 目标：根据 P2 后的剩余架构债务继续扩展 TODO，并启动 P3-01，把应用级依赖装配和后台任务运行器迁入 `application/`。
- 完成：`ARCH_MIGRATION_TODO.md` 新增 P3/P4 任务组，覆盖 APP 编排、扫描工作流、位置跟踪、状态模型、兼容清理、硬件验证、ScanRepository 和报告导出；新增 `application/app_context.py` 作为应用级 composition root；新增 `application/task_runner.py` 承接原 UI 侧 QThread 任务运行器；`ui/async_task.py` 改为兼容 re-export；`app.py` 改为通过 AppContext 创建主窗口；`MainWindow` 支持注入 task runner factory；`APP_DESIGN.md` 同步当前状态；新增 APP 装配测试。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest discover -s tests`，通过 94 个 `unittest`。
- 风险：`MainWindow` 仍持有扫描状态布尔组合、位置轮询定时器和多数顶层路由；P3-01 只完成应用装配和任务运行器迁移。
- 后续：继续 P3-02 或 P3-03，优先把扫描工作流状态或位置轮询从 `MainWindow` 中抽出。
- 涉及文件：`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`、`docs/APP_DESIGN.md`、`src/quiet_zone_tester/application/app_context.py`、`src/quiet_zone_tester/application/task_runner.py`、`src/quiet_zone_tester/application/__init__.py`、`src/quiet_zone_tester/app.py`、`src/quiet_zone_tester/ui/async_task.py`、`src/quiet_zone_tester/ui/main_window.py`、`tests/test_application_context.py`。

### ARCH-TASK-20260710-023 - P3 位置跟踪器抽取

- 目标：完成 P3-03，将扫描架运动期间的位置轮询定时器、轮询任务互斥和查询触发逻辑从 `MainWindow` 迁入运动控制 presentation 模块。
- 完成：新增 `PositionTracker`，由它管理 QTimer、当前轮询任务互斥、连接状态判断和位置查询任务触发；`MainWindow` 改为在运动开始/结束/断开/清理时调用 `PositionTracker.start()`、`stop()`、`reset()`，并只处理位置展示和失败日志；运动控制设计文档同步当前实现。
- 验证：使用 uv 环境运行局部测试 `python -m uv run python -m unittest tests.test_position_tracker tests.test_motion_control_view_model`，通过 10 个 `unittest`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 99 个 `unittest`；主窗口 offscreen 初始化输出 `ok`。
- 风险：`MainWindow` 仍直接编排绝对/相对运动命令和手动停止任务；本阶段只抽出运动期间的位置轮询。
- 后续：继续 P3-02 抽扫描工作流，或 P3-04/P3-05 建立连接和链路状态模型。
- 涉及文件：`src/quiet_zone_tester/presentation/modules/motion_control/position_tracker.py`、`src/quiet_zone_tester/presentation/modules/motion_control/__init__.py`、`src/quiet_zone_tester/ui/main_window.py`、`tests/test_position_tracker.py`、`docs/MOTION_CONTROL_DESIGN.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-024 - P3 连接状态模型抽取

- 目标：完成 P3-04，为 VNA、扫描架和开关箱连接状态建立结构化模型，并将连接面板状态文本和按钮启用规则从 Widget 迁入 ViewModel。
- 完成：新增 `ConnectionState` 和 `ConnectionPanelState`；`ConnectionViewModel.panel_state()` 统一派生“未连接/部分已连接/全部已连接/处理中”文本，以及连接/断开按钮启用状态；`ConnectionPanel._refresh_state()` 改为读取 ViewModel 派生结果；仪表管理设计文档同步当前实现。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_connection_view_model`，通过 5 个 `unittest`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 100 个 `unittest`；主窗口 offscreen 初始化输出 `ok`。
- 风险：连接状态事实仍由 `ConnectionPanel` 的三个布尔字段持有；后续可继续迁入 `InstrumentManager` 或 Qt model，供更多 UI 共享。
- 后续：继续 P3-05 建立链路状态模型，或 P3-02 抽扫描工作流。
- 涉及文件：`src/quiet_zone_tester/presentation/modules/connection/connection_view_model.py`、`src/quiet_zone_tester/presentation/modules/connection/__init__.py`、`src/quiet_zone_tester/ui/widgets/connection_panel.py`、`tests/test_connection_view_model.py`、`docs/INSTRUMENT_MANAGEMENT_DESIGN.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-025 - P3 链路图派生状态抽取

- 目标：推进 P3-05，将开关箱链路图高亮 token 等派生状态迁入链路 ViewModel，减少 Widget 中的业务解析。
- 完成：新增 `LinkDiagramState`；`LinkControlViewModel.diagram_state()` 统一规范化当前链路命令并派生高亮 token；`SwitchBoxDiagramWidget` 改为接收 `selected_command` 和 `highlighted_tokens`，只负责绘制；链路管理设计文档同步当前实现。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_link_control_view_model`，通过 6 个 `unittest`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 101 个 `unittest`；主窗口 offscreen 初始化输出 `ok`。
- 风险：当前链路状态事实仍主要由控件当前值和执行结果标签保存；后续可继续建立完整 `LinkState`，供日志、扫描记录和 UI 复用。
- 后续：继续 P3-02 抽扫描工作流，或补 P3-06 扫描点/结果 Qt model。
- 涉及文件：`src/quiet_zone_tester/presentation/modules/link_control/link_control_view_model.py`、`src/quiet_zone_tester/presentation/modules/link_control/__init__.py`、`src/quiet_zone_tester/ui/widgets/switch_box_control_panel.py`、`tests/test_link_control_view_model.py`、`docs/LINK_MANAGEMENT_DESIGN.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-026 - P3 日志展示收口到 LogRecordModel

- 目标：推进 P3-07，让运行日志文本视图只作为 `LogRecordModel` 的展示层，避免 UI 文本框成为第二套日志事实源。
- 完成：`StatusLogPanel.append()` 统一向 `LogRecordModel` 写入结构化日志；文本框改为监听 `rowsInserted` 并按模型记录追加展示；新增 `append_warning()`；测试覆盖直接向模型插入记录时文本视图同步更新。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_log_record_model`，通过 4 个 `unittest`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 102 个 `unittest`；主窗口 offscreen 初始化输出 `ok`。
- 风险：应用中的日志调用仍散落在 `MainWindow` 各流程方法中；后续抽扫描工作流时可继续把日志事件路由迁入 application/controller。
- 后续：继续 P3-02 抽扫描工作流，统一任务失败、业务日志和 UI 状态切换。
- 涉及文件：`src/quiet_zone_tester/ui/widgets/status_log_panel.py`、`tests/test_log_record_model.py`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-027 - P3 扫描点 Qt Model 建立

- 目标：完成 P3-06，建立可供扫描动画、进度统计和后续结果索引复用的扫描点 Qt model。
- 完成：新增 `ScanPointModel` 和 `ScanPointDisplay`，提供扫描点表格数据、完成点计数、状态角色和 volume 到扫描点的装载能力；`ScanAnimationPanel` 持有并同步更新 `point_model`，预览、开始扫描、进度更新和停止扫描都会同步模型状态；扫描管理设计文档同步当前实现。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_scan_point_model`，通过 3 个 `unittest`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 105 个 `unittest`；主窗口 offscreen 初始化输出 `ok`。
- 风险：当前模型只覆盖扫描点和完成状态，trace 结果索引尚未接入；后续可把扫描结果文件、最后一条 trace 或质量标记扩展到 model。
- 后续：继续 P3-02 抽扫描工作流，或扩展扫描结果 model 与报告导出。
- 涉及文件：`src/quiet_zone_tester/presentation/modules/scan_runtime/scan_point_model.py`、`src/quiet_zone_tester/presentation/modules/scan_runtime/__init__.py`、`src/quiet_zone_tester/ui/widgets/scan_animation_panel.py`、`tests/test_scan_point_model.py`、`docs/SCAN_MANAGEMENT_DESIGN.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-028 - P3 扫描工作流状态抽取

- 目标：完成 P3-02，将 `MainWindow` 中扫描启动、暂停、恢复、停止、失败、完成清理和忙碌派生相关布尔组合迁入 application 层。
- 完成：新增 `ScanWorkflowState`，集中管理 `sampling_active`、`paused`、`stop_requested`、`failed`、扫描任务运行、停止扫描架任务、进度计数和 busy 派生；`MainWindow` 改为通过该状态对象执行扫描流程状态更新，保留原任务调用和 UI 更新顺序；APP 和扫描管理设计文档同步当前实现。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_scan_workflow_state`，通过 4 个 `unittest`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 109 个 `unittest`；主窗口 offscreen 初始化输出 `ok`。
- 风险：扫描执行任务本身仍由 `MainWindow._tasks.run(self._service.run_scan, ...)` 发起；本阶段先收口状态，后续可进一步抽 scan workflow controller。
- 后续：继续 P3-08 清理 `InstrumentService` 兼容私有方法，或进入 P4 兼容路径和真实硬件验证治理。
- 涉及文件：`src/quiet_zone_tester/application/scan_workflow_state.py`、`src/quiet_zone_tester/application/__init__.py`、`src/quiet_zone_tester/ui/main_window.py`、`tests/test_scan_workflow_state.py`、`docs/APP_DESIGN.md`、`docs/SCAN_MANAGEMENT_DESIGN.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-029 - P3 InstrumentService 兼容私有壳清理

- 目标：完成 P3-08，删除 P2 facade 化后已无调用点的 `InstrumentService` 私有委托壳，保留明确公共 API 和扫描运行服务所需回调。
- 完成：删除未引用的 `_configure_backends()`、扫描几何委托、轴级运动委托、连续扫描派生委托、位置/轴 helper、旧 positioner scale helper、axis config helper 和 virtual helper；保留公共连接/运动/链路/采样/扫描 API，以及 `ScanRuntimeService` 注入仍使用的回调。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_instrument_connection_service tests.test_instrument_controller_factory tests.test_scan_runtime_service tests.test_motion_service`，通过 23 个 `unittest`；对 `InstrumentService` 使用不写 pyc 的源码编译检查，输出 `compile-ok`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 109 个 `unittest`；主窗口 offscreen 初始化输出 `ok`。
- 风险：真实硬件环境仍需联调确认扫描停止、暂停和连续运动行为；本阶段只删除静态确认无调用点的私有壳。
- 后续：P3 当前任务已全部完成；进入 P4 兼容路径、硬件验证、ScanRepository、报告导出和文档/运行说明治理。
- 涉及文件：`src/quiet_zone_tester/services/instrument_service.py`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-030 - P4 旧硬件导入路径 deprecated 标记

- 目标：完成 P4-01，为旧 `drivers/` 和 `instruments/` 兼容 re-export 增加清晰 deprecated 说明，并在硬件适配层设计文档中明确新代码导入规则。
- 完成：为 `drivers/`、`instruments/` 包入口和兼容模块增加 deprecated docstring；不添加运行时 warning，避免旧脚本导入时产生额外输出或测试噪声；`HARDWARE_ADAPTER_DESIGN.md` 更新为旧路径只保留 deprecated re-export，新实现只进入 `hardware/`。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_hardware_migration`，通过 3 个 `unittest`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 116 个 `unittest`，其中硬件集成入口默认跳过 1 个；主窗口 offscreen 初始化输出 `ok`。
- 风险：旧路径仍可导入；移除旧路径需要等外部脚本迁移完成后单独确认。
- 后续：继续 P4-02/P4-03，补真实硬件手动验证清单和可跳过集成测试入口。
- 涉及文件：`src/quiet_zone_tester/drivers/`、`src/quiet_zone_tester/instruments/`、`docs/HARDWARE_ADAPTER_DESIGN.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-031 - P4 硬件验证清单和集成测试入口

- 目标：完成 P4-02/P4-03，补充真实硬件手动验证清单，并建立默认跳过的硬件集成测试入口。
- 完成：新增 `HARDWARE_VALIDATION_CHECKLIST.md`，覆盖环境准备、连接验证、VNA、扫描架、开关箱、步进/匀速扫描、暂停/停止和失败恢复；新增 `tests/test_hardware_integration_smoke.py`，仅在 `RUN_HARDWARE_INTEGRATION=1` 时启用，并要求显式配置硬件环境变量；硬件适配层设计文档同步验证入口。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_hardware_integration_smoke`，默认无硬件环境通过并跳过 1 个测试；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 116 个 `unittest`，其中硬件集成入口默认跳过 1 个；主窗口 offscreen 初始化输出 `ok`。
- 风险：当前集成入口只验证环境显式配置，不自动执行真实连接和运动，避免误动硬件；真实设备行为仍需按清单人工验证。
- 后续：继续 P4-04 建立 `ScanRepository`，收口扫描事实写入。
- 涉及文件：`docs/HARDWARE_VALIDATION_CHECKLIST.md`、`tests/test_hardware_integration_smoke.py`、`docs/HARDWARE_ADAPTER_DESIGN.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-032 - P4 ScanRepository 建立

- 目标：完成 P4-04，让 `ScanSession`、`TraceRecord`、metadata、trace index 和文件输出具备统一事实写入入口。
- 完成：新增 `ScanRepository`，封装 `TraceStorage` 并提供 `create_session()`、`save_trace()`、`append_event()`、`finalize()`；创建 session 时写 metadata 和 trace index header，保存 trace 时写 CSV/index 并追加 `TraceRecord`；数据管理设计文档同步当前实现。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_scan_repository`，通过 3 个 `unittest`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 116 个 `unittest`，其中硬件集成入口默认跳过 1 个；主窗口 offscreen 初始化输出 `ok`。
- 风险：现有扫描主流程仍直接使用 `TraceStorage` 保存结果；后续可把 `InstrumentService` 的扫描保存路径切到 `ScanRepository`。
- 后续：继续 P4-05 增加报告导出服务。
- 涉及文件：`src/quiet_zone_tester/domains/data_management/scan_repository.py`、`src/quiet_zone_tester/domains/data_management/__init__.py`、`tests/test_scan_repository.py`、`docs/DATA_MANAGEMENT_DESIGN.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-033 - P4 报告导出服务

- 目标：完成 P4-05，基于扫描事实提供报告导出服务，避免 UI 直接读写结果文件。
- 完成：新增 `ReportExporter`，支持从 `ScanSession` 导出 Markdown 报告，包含会话概览、扫描范围、trace 记录和事件记录；数据管理设计文档同步当前实现。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_report_exporter`，通过 1 个 `unittest`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 116 个 `unittest`，其中硬件集成入口默认跳过 1 个；主窗口 offscreen 初始化输出 `ok`。
- 风险：当前报告为基础 Markdown 汇总，尚未包含图表、统计指标或模板配置。
- 后续：继续 P4-06 清理旧 dict 兼容层，或 P4-07 更新 README 和用户运行说明。
- 涉及文件：`src/quiet_zone_tester/domains/data_management/report_exporter.py`、`src/quiet_zone_tester/domains/data_management/__init__.py`、`tests/test_report_exporter.py`、`docs/DATA_MANAGEMENT_DESIGN.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-034 - P4 dataclass 边界收口

- 目标：完成 P4-06，让核心 domain service 边界优先接受 dataclass，同时保留 UI/旧调用路径 dict 兼容。
- 完成：`ScanRuntimeService.run_step_scan()` 和 `run_continuous_scan()` 支持 `ScanSettings | dict`，入口统一通过 `ScanSettings` 规范化；`AcquisitionService.configure_for_scan()` 支持 `ScanSettings`，同时保留只传 sweep 字段 dict 的旧行为；新增测试覆盖 dataclass 入参。
- 验证：使用 uv 环境运行 `python -m uv run python -m unittest tests.test_acquisition_service tests.test_scan_runtime_service`，通过 10 个 `unittest`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 116 个 `unittest`，其中硬件集成入口默认跳过 1 个；主窗口 offscreen 初始化输出 `ok`。
- 风险：UI 层仍以旧 dict signal 作为兼容载荷；这是外部兼容边界，后续大版本可再统一切换。
- 后续：继续 P4-07 更新 README 和用户运行说明。
- 涉及文件：`src/quiet_zone_tester/domains/acquisition/acquisition_service.py`、`src/quiet_zone_tester/domains/scan_management/scan_runtime_service.py`、`tests/test_acquisition_service.py`、`tests/test_scan_runtime_service.py`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-035 - P4 README 和运行说明更新

- 目标：完成 P4-07，更新 README，记录当前架构、uv 环境、启动命令、测试命令、硬件验证入口和旧路径兼容策略。
- 完成：README 的分层架构和项目结构更新为 `application/domains/hardware/presentation/ui` 当前结构；补充 `unittest` 命令、主窗口 offscreen 初始化命令、硬件验证清单链接和默认跳过的硬件集成测试环境变量；明确 `drivers/` 与 `instruments/` 仅为 deprecated re-export。
- 验证：文档更新；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 116 个 `unittest`，其中硬件集成入口默认跳过 1 个；主窗口 offscreen 初始化输出 `ok`；`git diff --check` 无 whitespace error，仅有 CRLF 行尾提示。
- 风险：README 仍需随 UI 现代化阶段继续补充截图或用户操作说明。
- 后续：P4 当前任务已全部完成；进入 UI 现代化阶段。
- 涉及文件：`README.md`、`docs/ARCH_MIGRATION_TODO.md`、`docs/ARCH_TASK_PROGRESS.md`。

### ARCH-TASK-20260710-036 - UI 现代浅色风格更新

- 目标：完成架构重构后的首轮 UI 现代化，让界面更接近现代开源 Qt/Fluent 风格的浅色工作台。
- 完成：更新全局 Qt stylesheet，统一字体 fallback、浅色中性背景、白色面板、8px 圆角、按钮 hover/pressed/disabled 状态、输入框 focus 状态、菜单、滚动条、splitter、日志框、表格和状态栏样式；不改变业务逻辑和控件布局。
- 验证：使用 offscreen 启动主窗口并保存截图到 `test_results/ui_checks/main_window_modern.png`，输出 `ok`；运行全量 `python -m uv run python -m unittest discover -s tests`，通过 116 个 `unittest`，其中硬件集成入口默认跳过 1 个；`git diff --check` 无 whitespace error，仅有 CRLF 行尾提示。
- 风险：offscreen 截图环境中文字体可能回退为方框；已在 stylesheet 中增加 Microsoft YaHei/SimSun/Segoe UI/Arial fallback，实际 Windows 桌面环境应使用可用中文字体。
- 后续：如需进一步提升，可单独做信息密度优化、图标体系统一、扫描结果表格视图和主题切换。
- 涉及文件：`src/quiet_zone_tester/app.py`、`docs/ARCH_TASK_PROGRESS.md`。
