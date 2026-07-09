# 架构迁移进度记录

Status: Active
Domain: ARCH
Canonical: `docs/ARCH_TASK_PROGRESS.md`
Related: `docs/architecture_migration_plan.md`, `docs/ARCH_MIGRATION_TODO.md`
Last updated: 2026-07-09

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
