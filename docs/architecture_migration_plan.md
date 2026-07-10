# 架构迁移方案：业务域 + MVVM + Qt Model/View + 状态机

Status: Active
Domain: ARCH
Canonical: `docs/architecture_migration_plan.md`
Related: `README.md`, `docs/ARCH_MIGRATION_TODO.md`, `docs/ARCH_TASK_PROGRESS.md`
Last updated: 2026-07-10

本文档定义静区测试软件的架构迁移方向。迁移目标不是一次性重写，而是在保持现有功能可运行的前提下，先建立清晰目录骨架，再逐步把 `MainWindow` 和 `InstrumentService` 中的职责拆入稳定业务域。

核心结论：

- 目录结构优先按业务域划分，不优先按 `ui/services/models` 这类技术层平铺。
- `main.py` 是唯一程序主入口，`run.py` 只作为开发期便捷启动脚本。
- MVVM 管 UI，状态机管流程，数据管理管事实，硬件适配层管协议。
- 新架构借鉴 HAOFV 的边界治理方式，但使用 Qt 原生机制实现，不照搬嵌入式 Active Object。

## 文档入口

本文档作为架构迁移主入口，负责说明总体方向、边界原则和阶段策略。具体设计、任务清单和实施记录拆分到以下文档：

| 文档 | 职责 |
|---|---|
| [APP_DESIGN.md](APP_DESIGN.md) | 应用入口、QApplication 生命周期、主窗口装配和全局任务边界。 |
| [INSTRUMENT_MANAGEMENT_DESIGN.md](INSTRUMENT_MANAGEMENT_DESIGN.md) | VNA、扫描架、开关箱的连接生命周期、controller 创建和连接配置边界。 |
| [LINK_MANAGEMENT_DESIGN.md](LINK_MANAGEMENT_DESIGN.md) | 开关箱链路操作、历史 S 参数兼容路由、profile 和链路控制边界。 |
| [MOTION_CONTROL_DESIGN.md](MOTION_CONTROL_DESIGN.md) | 扫描架手动运动、轴级运动、运行时配置和位置显示边界。 |
| [SCAN_MANAGEMENT_DESIGN.md](SCAN_MANAGEMENT_DESIGN.md) | 扫描配置、路径规划、状态机和扫描运行边界。 |
| [DATA_MANAGEMENT_DESIGN.md](DATA_MANAGEMENT_DESIGN.md) | 扫描事实、trace 文件、metadata、trace index 和文件命名边界。 |
| [HARDWARE_ADAPTER_DESIGN.md](HARDWARE_ADAPTER_DESIGN.md) | 硬件接口、Mock 实现、真实协议实现和旧导入兼容策略。 |
| [ARCH_MIGRATION_TODO.md](ARCH_MIGRATION_TODO.md) | 稳定任务清单和验收标准。 |
| [ARCH_TASK_PROGRESS.md](ARCH_TASK_PROGRESS.md) | 已完成任务的实施记录、验证结果、风险和后续事项。 |

## 1. 当前架构判断

当前项目已经具备基础分层：

- `ui/`：窗口、控件、曲线、动画、日志显示。
- `services/`：仪器连接、扫描流程、采样、文件保存等业务编排。
- `drivers/`：统一接口与 Mock 后端。
- `instruments/`：真实仪器通信实现。
- `models/`：跨层共享数据结构。

主要问题：

- [main_window.py](../src/quiet_zone_tester/ui/main_window.py) 同时承担布局、信号连接、任务调度、状态切换、日志路由和错误处理。
- [instrument_service.py](../src/quiet_zone_tester/services/instrument_service.py) 同时承担连接管理、扫描流程、运动规划、VNA 采样、文件存储、metadata 和 controller 创建。
- UI 与 Service 之间大量传递 `dict`，字段变更缺少类型保护。
- 扫描状态依赖多个布尔变量组合，后续暂停、停止、异常恢复、重连会越来越难推理。
- 数据管理目前偏“保存 CSV”，还没有形成以 `ScanSession` 为中心的事实模型。

## 2. HAOFV 的可取之处

HAOFV 对本项目最有价值的不是具体嵌入式机制，而是架构治理方式。

可借鉴：

- **管理域优先**：HAOFV 用 `system_manager`、`ota_manager`、`storage_manager` 等责任域组织系统。本项目也应有 `instrument_management`、`link_management`、`motion_control`、`scan_management`。
- **接口与实现分离**：HAOFV 将平台无关核心、port 适配层和硬件服务拆开。本项目应拆成 `domains/`、`hardware/interfaces.py`、`hardware/*/`。
- **资源仲裁显式化**：HAOFV 有 Resource Arbiter。本项目也需要管理 VNA、扫描架、开关箱、串口/TCP、扫描会话、文件写入等互斥资源。
- **事实和流程分离**：HAOFV 用 Vector 保存事实，用 AO/状态机管理流程。本项目应使用 dataclass 保存事实，用 Qt 状态机或轻量状态类管理流程。
- **文档治理清晰**：HAOFV 将 `_ARCHITECTURE`、`_DESIGN`、`_PLAN`、`_TODO`、`_TASK_PROGRESS` 分离。本项目后续也应拆分架构、设计、任务和进度文档。

不照搬：

- Active Object、调度预算、Vector Blackboard 是嵌入式硬实时语境下的实现机制。
- 本项目是 PySide6 桌面应用，更适合使用 `QObject`、Signal/Slot、`QStateMachine`、`QAbstractItemModel`、`QThread`。

## 3. 目标架构

目标架构：

```text
Presentation(View)
  只负责 Qt Widget 布局、显示、用户输入事件。

ViewModel(QObject)
  保存 UI 状态，提供 Signal/Slot，执行输入校验，发起用户意图。

Domain Service
  执行业务流程，不依赖 Qt Widget。

State Machine
  管理连接、运动、扫描、存储等流程状态和合法转换。

Data Model(dataclass)
  保存配置、运行事实、测量记录、metadata、日志记录。

Qt Model/View
  管理日志、仪表状态、扫描点、结果索引等可展示集合。

Hardware Adapter
  统一仪器接口、Mock 后端、真实协议实现。
```

依赖方向：

```text
presentation -> viewmodel -> domains -> hardware
                         \-> data models
```

约束：

- View 不直接调用硬件 controller。
- Domain 不依赖 Qt Widget。
- 状态机不保存大体量测量数据。
- 数据管理不决定流程跳转。
- 硬件适配层不关心 UI 状态和文件输出。

## 4. 入口与 APP 管理

入口必须先收口，再迁移业务代码。

入口约定：

```text
python -m quiet_zone_tester
quiet-zone-tester
python run.py
```

三种方式最终都进入：

```text
quiet_zone_tester.main:main
```

职责划分：

```text
run.py
  仅负责开发期把 src 加入 sys.path，并调用 quiet_zone_tester.main.main。

src/quiet_zone_tester/__main__.py
  仅负责支持 python -m quiet_zone_tester，并调用 quiet_zone_tester.main.main。

src/quiet_zone_tester/main.py
  程序主入口，负责调用 app.run_app。

src/quiet_zone_tester/app.py
  QApplication 创建、全局样式、主窗口启动。

application/
  应用上下文、全局状态机、任务调度、全局错误类型。
```

验收标准：

- 所有启动路径都经过 `quiet_zone_tester.main:main`。
- `run.py` 不承载业务逻辑。
- APP 装配逻辑逐步从 `main_window.py` 移入 `application/app_context.py`。

## 5. 业务域划分

业务域是新目录的第一原则。

```text
APP 管理
  程序入口、QApplication、主窗口装配、全局状态机、后台任务调度。

仪表管理
  VNA、扫描架、开关箱的连接、断开、状态查询、Mock/真实后端选择。

链路管理
  极化链路、DUT 目标链路、原始命令发送、历史 S 参数兼容路由、链路箱型号差异、链路可视化。

运动控制管理
  扫描架当前位置、点动、停止、绝对/相对运动、轴映射、运动状态轮询。

扫描管理
  扫描配置、路径规划、步进/匀速扫描、暂停/恢复/停止、扫描进度。

采样管理
  VNA 扫频配置、单次采样、扫描过程采样、曲线数据校验。

数据管理
  ScanSession、TraceRecord、metadata、trace index、输出目录、文件命名、报告导出。

日志与诊断
  LogRecord、运行日志模型、错误事件、诊断信息。

硬件适配层
  统一接口、Mock 后端、真实仪器协议。

表现层
  Qt Widgets、ViewModel、Qt Model/View、信号槽绑定。
```

## 6. 推荐目录结构

最终目标：

```text
src/quiet_zone_tester/
  main.py
  app.py

  application/
    app_context.py
    app_state.py
    app_state_machine.py
    task_runner.py
    errors.py

  domains/
    instrument_management/
      models.py
      instrument_manager.py
      connection_service.py
      instrument_registry.py

    link_management/
      models.py
      link_service.py
      link_router.py
      switch_box_profiles.py

    motion_control/
      models.py
      motion_service.py
      position_tracker.py

    scan_management/
      models.py
      scan_planner.py
      scan_runner.py
      scan_session.py
      scan_state_machine.py

    acquisition/
      models.py
      acquisition_service.py
      vna_sweep_service.py

    data_management/
      models.py
      scan_repository.py
      trace_storage.py
      metadata_writer.py
      filename_policy.py
      export_service.py

    diagnostics/
      models.py
      log_service.py
      error_reporter.py

  hardware/
    interfaces.py
    mock/
      mock_vna.py
      mock_positioner.py
      mock_switch_box.py
    vna/
      visa_scpi.py
      scpi_vna.py
    positioner/
      modbus_rtu.py
      icl_positioner.py
    switch_box/
      lcd74000f.py
      tc500.py

  presentation/
    main_window.py
    shell/
      main_shell_view.py
      main_shell_view_model.py
    modules/
      connection/
        connection_view.py
        connection_view_model.py
        instrument_status_model.py
      scan_setup/
        scan_setup_view.py
        scan_setup_view_model.py
      scan_runtime/
        scan_animation_view.py
        scan_runtime_view_model.py
        scan_point_model.py
      motion_control/
        motion_control_view.py
        motion_control_view_model.py
      link_control/
        link_control_view.py
        link_control_view_model.py
      acquisition/
        vna_control_view.py
        vna_control_view_model.py
        live_plot_view.py
      logs/
        log_view.py
        log_view_model.py
        log_record_model.py

  shared/
    serialization.py
    filename.py
    qt_utils.py
    time_utils.py
```

第一阶段只创建目录骨架，不立刻移动全部旧代码。现有 `ui/`、`services/`、`drivers/`、`instruments/` 暂时保留，避免大规模回归。新功能优先进入新目录，旧功能按阶段迁移。

## 7. 关键业务域边界

### 7.1 仪表管理

职责：

- 创建 VNA、扫描架、开关箱 controller。
- 连接、断开、查询连接状态。
- 维护仪表状态和连接配置快照。

不负责：

- 极化链路和 DUT 目标链路命令。
- 历史 S 参数兼容路由。
- 扫描路径规划。
- 文件保存。

单一写权限：

- 仪表连接状态只能由 `InstrumentManager` 写。

### 7.2 链路管理

职责：

- 极化 H/V 到链路命令的映射。
- DUT 目标 VNA2/SA 到链路命令的映射。
- `S11/S21/S12/S22` 到链路命令的历史兼容映射。
- LCD74000F、TC500 等型号 profile。
- 链路切换和当前链路状态。

不负责：

- TCP/Serial 底层通信细节。
- VNA 采样。

单一写权限：

- 当前链路状态只能由 `LinkService` 写。

### 7.3 运动控制管理

职责：

- 查询当前位置。
- 点动、停止、绝对/相对运动。
- 轴 ID 与 X/Y 语义映射。
- 运动轮询和安全停止。

不负责：

- 扫描路径业务规划。
- VNA 采样。
- 文件保存。

单一写权限：

- 当前位置和运动状态只能由 `MotionService` 或 `PositionTracker` 写。

### 7.4 扫描管理

职责：

- 校验扫描参数。
- 生成扫描计划。
- 编排步进/匀速扫描。
- 管理暂停、恢复、停止、失败、完成。

不负责：

- 真实仪器协议。
- 文件命名规则。
- UI 绘图。

单一写权限：

- 扫描运行状态只能由 `ScanStateMachine` 写。
- 当前扫描进度只能由 `ScanRunner` 写入 `ScanSession`。

### 7.5 数据管理

职责：

- 创建 `ScanSession`。
- 追加 `TraceRecord`。
- 保存 CSV、metadata、trace index。
- 管理输出目录和文件命名。
- 后续扩展报告导出。

不负责：

- 控制硬件。
- 更新 UI。
- 决定流程跳转。

单一写权限：

- 测量记录只能由 `ScanRepository` 或 `TraceStorage` 追加。
- metadata 只能由 `MetadataWriter` 输出。

## 8. 数据管理设计

数据管理不是“保存 CSV”，而是保存测试系统的事实。

数据分五类：

```text
配置数据
  仪表连接配置、扫描参数、探头位置、链路箱型号。

运行期状态数据
  当前连接状态、当前位置、当前扫描点、暂停状态、错误状态。

测量数据
  VNA trace、频率轴、幅度、相位、S 参数。

元数据
  扫描时间、软件版本、文件 flag、探头偏置、链路状态、连接配置快照。

UI 派生数据
  实时曲线、二维动画点、日志表格显示。
```

核心模型建议：

```python
@dataclass(frozen=True)
class ScanSessionConfig:
    scan_settings: ScanSettings
    connection_config: InstrumentConnectionConfig
    output_root: Path
    file_flag: str

@dataclass
class ScanSession:
    session_id: str
    config: ScanSessionConfig
    planned_points: list[ScanPoint]
    records: list[TraceRecord]
    events: list[ScanEvent]
    output_dir: Path
    started_at: datetime
    finished_at: datetime | None = None
    final_state: str | None = None

@dataclass(frozen=True)
class TraceRecord:
    point_index: int
    position_mm: tuple[float, float] | None
    parameter: str
    trace: SParameterTrace
    file_path: Path | None
    acquired_at: datetime

@dataclass(frozen=True)
class ScanEvent:
    timestamp: datetime
    level: str
    event_type: str
    message: str
```

数据管理原则：

- 扫描开始时创建 `ScanSession`。
- 所有 trace、metadata、日志事件、路径点都挂在 session 上。
- UI 可以展示 session，但不能直接修改 session 的核心事实。
- Trace 保存成功后，`TraceRecord.file_path` 才可写入。
- 扫描完成或失败都必须 finalize metadata。

## 9. 状态机设计

状态机不是几个 bool 的替代品，而是定义系统允许发生什么。

建议分层状态机：

```text
AppStateMachine
  Idle
  Connecting
  Ready
  Busy
  Error

InstrumentStateMachine
  Disconnected
  Connecting
  Connected
  Disconnecting
  Fault

ScanStateMachine
  Idle
  Planning
  Running
  Paused
  Stopping
  Completed
  Failed

MotionStateMachine
  Idle
  Moving
  Jogging
  Stopping
  Fault

StorageStateMachine
  Idle
  SessionOpen
  WritingTrace
  Finalizing
  Failed
```

状态机原则：

- 状态机管理流程，不保存大体量数据。
- `ScanSession` 保存事实，`ScanStateMachine` 保存当前阶段。
- 状态转换必须由明确事件触发。
- UI 按状态机派生按钮可用性。
- Service 在非法状态下拒绝执行命令。

扫描状态示例：

```text
Idle
  start_scan -> Planning

Planning
  plan_ready -> Running
  plan_failed -> Failed

Running
  pause -> Paused
  stop -> Stopping
  point_completed -> Running
  scan_completed -> Completed
  error -> Failed

Paused
  resume -> Running
  stop -> Stopping

Stopping
  stopped -> Completed
  stop_failed -> Failed
```

资源互锁示例：

```text
扫描中不能手动点动扫描架。
扫描中不能重新连接仪表。
采样中不能由 UI 手动切换链路，除非由 ScanRunner 控制。
停止过程中不能再次开始扫描。
StorageStateMachine 未 Finalizing 完成前不能开启新 session。
```

## 10. 推荐调用链

仪表连接：

```text
ConnectionView
  -> ConnectionViewModel.connect_requested
  -> InstrumentManager.connect_all
  -> ConnectionService
  -> hardware controller
```

链路切换：

```text
LinkControlView
  -> LinkControlViewModel / MainWindow emits polarization or DUT target
  -> InstrumentService.select_switch_box_polarization / select_switch_box_dut_path
  -> LinkService.select_polarization / select_dut_path
  -> SwitchBoxController.send_command
```

手动运动：

```text
MotionControlView
  -> MotionControlViewModel.move_absolute / jog / stop
  -> MotionService
  -> PositionerController
  -> PositionTracker
```

扫描：

```text
ScanSetupView
  -> ScanSetupViewModel.build_scan_settings
  -> ScanRuntimeViewModel.start_scan
  -> ScanStateMachine.start
  -> ScanRunner
  -> ScanPlanner
  -> MotionService
  -> LinkService
  -> AcquisitionService
  -> TraceStorage
```

数据保存：

```text
ScanRunner
  -> ScanRepository.append_trace
  -> TraceStorage.save_trace
  -> FilenamePolicy
  -> MetadataWriter
```

## 11. 当前代码迁移映射

```text
当前 app.py
  -> application/app_context.py + app.py

当前 ui/async_task.py
  -> application/task_runner.py

当前 ui/main_window.py
  -> presentation/main_window.py
  -> presentation/shell/main_shell_view_model.py

当前 ui/widgets/connection_panel.py
  -> presentation/modules/connection/connection_view.py
  -> presentation/modules/connection/connection_view_model.py
  -> domains/instrument_management/

当前 ui/widgets/switch_box_control_panel.py
  -> presentation/modules/link_control/link_control_view.py
  -> presentation/modules/link_control/link_control_view_model.py
  -> domains/link_management/

当前 ui/widgets/positioner_control_panel.py
  -> presentation/modules/motion_control/motion_control_view.py
  -> presentation/modules/motion_control/motion_control_view_model.py
  -> domains/motion_control/

当前 ui/widgets/test_setup_panel.py
  -> presentation/modules/scan_setup/scan_setup_view.py
  -> presentation/modules/scan_setup/scan_setup_view_model.py
  -> domains/scan_management/models.py

当前 ui/widgets/scan_animation_panel.py
  -> presentation/modules/scan_runtime/scan_animation_view.py
  -> presentation/modules/scan_runtime/scan_point_model.py
  -> domains/scan_management/scan_planner.py

当前 ui/widgets/live_plot_panel.py
  -> presentation/modules/acquisition/live_plot_view.py
  -> domains/acquisition/models.py

当前 ui/widgets/status_log_panel.py
  -> presentation/modules/logs/log_view.py
  -> presentation/modules/logs/log_record_model.py

当前 services/instrument_service.py
  -> domains/instrument_management/
  -> domains/link_management/
  -> domains/motion_control/
  -> domains/scan_management/
  -> domains/acquisition/
  -> domains/data_management/

当前 drivers/
  -> hardware/interfaces.py
  -> hardware/mock/

当前 instruments/
  -> hardware/vna/
  -> hardware/positioner/
  -> hardware/switch_box/
```

## 12. 迁移阶段

### 阶段 0：入口和目录骨架

目标：

- 确认 `main.py` 是唯一程序主入口。
- 创建 `application/`、`domains/`、`hardware/`、`presentation/`、`shared/` 骨架。
- 保持旧代码路径不动。

验收：

- `python run.py` 可启动。
- `python -m quiet_zone_tester` 可启动。
- `py_compile` 通过。

### 阶段 1：数据模型和状态机骨架

目标：

- 新增 `ScanSession`、`TraceRecord`、`ScanEvent`。
- 新增轻量 `ScanStateMachine`。
- 先不替换现有扫描逻辑，只建立模型和测试。

验收：

- 扫描状态转换可单元测试。
- `ScanSession` 可 JSON metadata 序列化。

### 阶段 2：TraceStorage 和 FilenamePolicy

目标：

- 从 `InstrumentService` 抽出 CSV 保存、metadata、trace index、文件命名。
- 保持原 Service API 不变。

验收：

- 文件保存逻辑可独立测试。
- 原扫描流程输出文件名和目录规则不回归。

### 阶段 3：ScanPlanner 和 MotionPlanner

目标：

- 抽出扫描点规划、X/Y 线段、二维区域路径。
- 抽出轴运动顺序和连续扫描运动判断。

验收：

- X 线段、Y 线段、反向扫描、二维蛇形路径都有测试。
- 二维动画和 ScanRunner 使用同一份规划结果。

### 阶段 4：ViewModel 和 Qt Model/View

目标：

- `ConnectionPanel` 迁入 `ConnectionViewModel`。
- `TestSetupPanel` 迁入 `ScanSetupViewModel`。
- 运行日志迁入 `LogRecordModel(QAbstractTableModel)`。

验收：

- Widget 不直接拼业务配置。
- 日志记录结构化。
- MainWindow 只做装配和顶层路由。

### 阶段 5：Service 拆分

目标：

- 把 `InstrumentService` 变成 facade。
- 业务分别进入 InstrumentManager、LinkService、MotionService、ScanRunner、AcquisitionService、TraceStorage。

验收：

- `InstrumentService` 不再包含文件命名、路径规划、硬件创建细节。
- 每个域可以单独测试核心逻辑。

## 13. 测试计划

新增：

```text
tests/
  test_scan_state_machine.py
  test_scan_session.py
  test_scan_planner.py
  test_motion_planner.py
  test_trace_storage.py
  test_filename_policy.py
  test_link_router.py
  test_connection_config.py
```

优先覆盖：

- `ScanVolume.scan_points()` 起点/终点方向。
- X 线段、Y 线段、二维面扫描路径。
- 探头偏置文件名 tag。
- 开关箱型号到连接类型映射。
- metadata 可 JSON 序列化。
- Trace CSV 文件名合法化。
- 扫描状态机非法转换拒绝。

## 14. 风险与控制

| 风险 | 控制方式 |
|---|---|
| 一次性改动过大 | 每次迁移一个职责，保留旧 API，先新增后替换 |
| UI 行为回归 | 每阶段保留 offscreen 初始化检查 |
| 硬件环境不可用 | Mock controller 和纯逻辑测试优先 |
| Qt Model/View 引入过早 | 只对日志、扫描点、结果索引等集合数据使用 |
| 目录大搬家导致历史混乱 | 第一阶段只建骨架，新代码进新目录，旧代码逐步迁移 |
| 状态机过度复杂 | 先用轻量 QObject 状态类，复杂后再引入 QStateMachine |

## 15. 文档治理

```text
docs/architecture_migration_plan.md
docs/APP_DESIGN.md
docs/INSTRUMENT_MANAGEMENT_DESIGN.md
docs/LINK_MANAGEMENT_DESIGN.md
docs/MOTION_CONTROL_DESIGN.md
docs/SCAN_MANAGEMENT_DESIGN.md
docs/DATA_MANAGEMENT_DESIGN.md
docs/HARDWARE_ADAPTER_DESIGN.md
docs/ARCH_MIGRATION_TODO.md
docs/ARCH_TASK_PROGRESS.md
```

参考 HAOFV 文档体系，架构迁移文档已拆分为主入口、业务域设计、任务清单和进度记录四类。

治理规则：

- `architecture_migration_plan.md` 只保留总体架构方向、迁移原则和入口索引。
- `*_DESIGN.md` 记录业务域职责、边界、当前实现和后续迁移。
- `ARCH_MIGRATION_TODO.md` 记录稳定任务清单和验收标准，不堆实施过程。
- `ARCH_TASK_PROGRESS.md` 记录每个任务的完成内容、验证结果、风险和后续事项。
- 新增跨域设计时，先判断是否需要独立设计文档，再更新本文档入口索引。

## 16. 近期最小可落地版本

下一步建议只做小闭环：

1. 创建新目录骨架和 `__init__.py`。
2. 确认入口职责：`run.py`、`__main__.py`、`main.py`、`app.py`。
3. 新增 `ScanSession`、`TraceRecord`、`ScanEvent` 草案模型。
4. 新增轻量 `ScanStateMachine` 草案。
5. 不改 UI 行为，不改硬件流程。
6. 跑 `py_compile` 和主窗口 offscreen 初始化检查。

完成后，新代码有稳定落点，数据事实和流程状态也有清晰边界，后续迁移可以按业务域逐步推进。
