# 架构迁移 TODO

Status: Active
Domain: ARCH
Canonical: `docs/ARCH_MIGRATION_TODO.md`
Related: `docs/architecture_migration_plan.md`
Last updated: 2026-07-10

本文档跟踪静区测试软件架构迁移任务。TODO 只记录尚未完成或需要持续跟踪的事项；已经发生的实施过程、验证结果、风险和决策，应记录到后续 `ARCH_TASK_PROGRESS.md`，避免任务清单变成流水账。

## TODO 规则

- 任务按 P0/P1/P2/P3/P4 优先级分组。
- 任务编号使用 `P0-01`、`P1-01`、`P2-01`、`P3-01` 格式，编号稳定，不复用。
- 每条任务必须包含明确验收标准。
- 完成任务时只把 `[ ]` 改为 `[x]`，不要在 TODO 中堆长篇过程记录。
- 若任务执行中产生重要结论，追加到 `ARCH_TASK_PROGRESS.md`。
- 如果新增任务不属于当前迁移范围，应先判断是否需要独立 `*_TODO.md`。
- 涉及代码结构变更时，每阶段必须保留可运行状态。

## 验收标准摘要

| 优先级 | 验收标准 |
|---|---|
| P0 | 入口职责收口、目标目录骨架建立、扫描事实模型和状态机草案可测试；不改变现有 UI 和硬件流程。 |
| P1 | 文件命名、TraceStorage、ScanPlanner、LinkRouter、dataclass 配置和日志模型从大类中抽出，并有最小测试覆盖。 |
| P2 | Widget 逐步迁移到 ViewModel，`InstrumentService` 变成 facade，硬件层迁移到 `hardware/`，文档体系拆分完成。 |
| P3 | APP 层承接装配、任务运行、全局状态、位置轮询和扫描编排；MainWindow 继续瘦身。 |
| P4 | 清理旧兼容路径、补齐硬件集成验证、报告导出和发布前文档治理。 |
| P5 | 收口重构债务：统一默认值来源、清理 S 参数链路旧语义、继续瘦身 MainWindow，并整理当前项目样式。 |

## P0 - 入口、目录骨架、事实模型和状态机

- [x] P0-01 确认程序入口职责：`run.py` 只做开发启动；`__main__.py` 和脚本入口都进入 `quiet_zone_tester.main:main`；`app.py` 只负责 QApplication 和主窗口启动。
- [x] P0-02 创建新目录骨架：创建 `application/`、`domains/`、`hardware/`、`presentation/`、`shared/` 及各业务域子目录；暂不移动旧代码。
- [x] P0-03 建立扫描数据事实模型草案：新增 `ScanSession`、`TraceRecord`、`ScanEvent` 草案模型；不接入现有扫描流程。
- [x] P0-04 建立扫描状态机草案：新增轻量 `ScanStateMachine`，支持 `Idle/Planning/Running/Paused/Stopping/Completed/Failed` 转换测试。
- [x] P0-05 明确单一写权限规则：仪表状态、链路状态、当前位置、扫描状态、测量记录分别只有一个业务域拥有写权限。
- [x] P0-06 添加基础测试目录：新建 `tests/`，加入扫描状态机、ScanSession 序列化、ScanVolume 路径规划的最小测试。
- [x] P0-07 保持现有启动验证：每次 P0 迁移后运行 `py_compile` 和主窗口 offscreen 初始化检查。

### P0 验收

- `python run.py` 可启动。
- `python -m quiet_zone_tester` 可启动。
- 新目录骨架存在，但旧功能导入路径不被破坏。
- `ScanSession`、`TraceRecord`、`ScanEvent` 可被导入。
- `ScanStateMachine` 非法转换会被拒绝。
- 主窗口 offscreen 初始化通过。

## P1 - 核心职责抽取

- [x] P1-01 抽出 `FilenamePolicy`：文件名清洗、探头偏置 tag、trace 文件名规则从 `InstrumentService` 移出并可单元测试。
- [x] P1-02 抽出 `TraceStorage`：CSV 保存、trace index、metadata 输出从 `InstrumentService` 移出；原扫描输出不回归。
- [x] P1-03 抽出 `ScanPlanner`：X 线段、Y 线段、二维蛇形路径统一由 planner 输出，动画和扫描执行共用同一规划结果。
- [x] P1-04 抽出 `LinkRouter`：`S11/S21/S12/S22` 到开关箱命令映射独立成模块，支持 LCD74000F/TC500 profile。
- [x] P1-05 引入连接配置 dataclass：VNA、扫描架、开关箱连接配置从 `dict` 逐步迁移到 dataclass，保留旧 API 适配。
- [x] P1-06 引入扫描配置 dataclass：`ScanSettings`、`ProbeOffset`、`SweepSettings` 替代散落 `dict` 字段。
- [x] P1-07 建立 `LogRecordModel`：运行日志从纯文本追加迁移为结构化 Qt Model，保留当前日志视图行为。

### P1 验收

- 文件命名规则有单元测试。
- Trace CSV、metadata、trace index 输出格式不回归。
- 扫描路径规划可不连接仪器独立测试。
- 链路路由可不连接开关箱独立测试。
- 新 dataclass 与旧 `dict` API 可以共存一段时间。
- 日志记录具备结构化字段：时间、等级、来源、消息。

## P2 - ViewModel、Facade 和硬件层迁移

- [x] P2-01 `ConnectionPanel` 迁移到 ViewModel：Widget 只负责显示和发信号；连接配置、串口刷新、开关箱型号逻辑进入 ViewModel。
- [x] P2-02 `TestSetupPanel` 迁移到 ViewModel：扫描参数校验、探头位置、默认值和预览配置进入 ViewModel。
- [x] P2-03 `PositionerControlPanel` 迁移到运动控制域：手动运动命令、当前位置显示、轮询逻辑由 Motion ViewModel 和 MotionService 管理。
- [x] P2-04 `SwitchBoxControlPanel` 迁移到链路管理域：链路控制 UI 使用 LinkViewModel 和 LinkService，不直接拼命令。
- [x] P2-05 `InstrumentService` 变成 facade：连接、运动、链路、扫描、采样、数据保存都委托到独立 domain service。
- [x] P2-06 硬件层目录迁移：当前 `drivers/` 和 `instruments/` 迁移到 `hardware/`，并保持兼容导入或一次性更新引用。
- [x] P2-07 文档体系拆分：从主迁移方案拆出 APP、仪表、链路、运动、扫描、数据管理设计文档。

### P2 验收

- `MainWindow` 只做主窗口装配和顶层路由。
- Widget 不直接拼业务配置。
- `InstrumentService` 不再包含文件命名、路径规划、硬件创建细节。
- 真实硬件实现和 Mock 实现都通过 `hardware/interfaces.py` 暴露统一接口。
- 文档主入口、设计文档、TODO、进度记录职责清晰。

## P3 - APP 编排、状态模型和 MainWindow 瘦身

- [x] P3-01 建立 `application/app_context.py` 和 `application/task_runner.py`：应用级依赖由 AppContext 装配，后台任务运行器迁出 `ui/`，旧 `ui.async_task` 仅作为兼容导入。
- [x] P3-02 抽出应用级扫描工作流：将 `MainWindow` 中扫描启动、暂停、恢复、停止、失败处理和按钮状态派生迁入 application 或 scan presentation controller。
- [x] P3-03 抽出位置跟踪器：将 `MainWindow` 中扫描架运动期间的位置轮询、轮询任务互斥和位置显示更新迁入运动控制 ViewModel 或 `PositionTracker`。
- [x] P3-04 建立连接状态模型：为 VNA、扫描架、开关箱连接状态建立结构化 state/model，`ConnectionPanel` 从模型读取状态，不再由 `MainWindow` 拼接状态文本。
- [x] P3-05 建立链路状态模型：将当前 S 参数、开关箱 profile、路由结果和链路图派生状态迁入链路 ViewModel/model，Widget 只负责绘制。
- [x] P3-06 建立扫描点/结果 Qt model：扫描动画、进度统计和结果索引共用扫描点 model，避免 UI 各自维护完成点计数。
- [x] P3-07 收口日志路由：全局错误、任务失败和业务日志统一进入 `LogRecordModel`，文本日志视图只作为展示层。
- [x] P3-08 收口 `InstrumentService` 兼容私有方法：清理只服务旧测试或旧路径的委托壳，保留明确的 facade 公共 API。

### P3 验收

- `app.py` 不直接创建业务 service 或 UI 依赖，只创建 QApplication 并调用 AppContext。
- `ui.async_task` 旧路径仍可导入，但实现位于 `application/task_runner.py`。
- `MainWindow` 不直接管理后台任务细节、位置轮询细节或扫描状态布尔组合。
- 连接、链路、扫描点和日志至少各有一个结构化 model 或 ViewModel 作为 UI 数据源。
- 全量 `unittest` 通过，主窗口 offscreen 初始化通过。

## P4 - 兼容清理、集成验证和交付治理

- [x] P4-01 标记旧硬件导入路径 deprecated：为 `drivers/` 和 `instruments/` 兼容 re-export 增加清晰注释或 warning 策略，并在文档中说明迁移期限。
- [x] P4-02 制定真实硬件手动验证清单：覆盖 VNA 连接、扫描架运动、开关箱路由、步进扫描、匀速扫描、暂停/停止和失败恢复。
- [x] P4-03 补充硬件集成测试入口：建立可跳过的硬件集成测试或手动脚本入口，默认不影响无硬件 CI/本地单元测试。
- [x] P4-04 建立 `ScanRepository`：让 `ScanSession`、`TraceRecord`、metadata、trace index 和文件输出形成统一事实写入入口。
- [x] P4-05 增加报告导出服务：基于扫描事实和 trace index 导出后处理报告，避免 UI 直接读写结果文件。
- [x] P4-06 清理旧 dict 兼容层：在 ViewModel 和 domain service 边界优先使用 dataclass，旧 dict 仅保留外部兼容入口。
- [x] P4-07 更新 README 和用户运行说明：记录 uv 环境、启动命令、测试命令、真实/虚拟硬件模式和常见故障处理。

### P4 验收

- 新代码不再从 `quiet_zone_tester.drivers` 或 `quiet_zone_tester.instruments` 导入硬件实现。
- 无硬件环境下全量 `unittest` 稳定通过；真实硬件环境有明确手动验证清单或可跳过集成测试入口。
- 扫描事实写入、报告导出和结果索引不依赖 UI 控件。
- README、设计文档、TODO 和进度记录一致，用户可按文档完成环境创建、启动和测试。

## P5 - 重构收口和旧语义清理

- [ ] P5-01 统一仪器默认值来源：新增仪器默认配置模块，VNA、扫描架、开关箱的 IP、端口、超时、波特率、轴号、每毫米单位和默认速度只保留一个权威定义。
- [ ] P5-02 收口 `ConnectionPanel` 默认值：控件构造不再直接写业务默认值，初始 UI 状态全部来自 `ConnectionViewModel` 或统一默认配置。
- [ ] P5-03 清理 S 参数链路旧语义：S 参数只属于 VNA 测量；开关箱主链路接口改为极化、DUT 目标和原始命令，`select_s_parameter()` 仅保留 deprecated 兼容路径或移除。
- [ ] P5-04 更新链路文档：README、链路设计文档和迁移方案不再把“按 S 参数切换开关箱”描述为当前行为。
- [ ] P5-05 抽出实时曲线 FLAG 识别模型：主线条 X/Y、位置 L/R/U/D/M 和四分之一边界判断迁入 presentation model，并修正非 0 起点扫描区间的识别逻辑。
- [ ] P5-06 继续瘦身 `MainWindow`：DUT 链路命令拼接、任务结果处理、状态栏和日志路由逐步迁入 application/presentation controller。
- [ ] P5-07 整理当前项目样式：从参考 `style.css` 中提炼当前项目实际使用规则，避免长期依赖末尾覆盖大字号和无关控件规则。
- [ ] P5-08 建立收口回归验证：每完成 P5 子任务后运行全量 `unittest`，涉及 UI 时补充主窗口 offscreen 初始化检查。

### P5 验收

- 仪器默认值修改只需要改一个模块，UI、domain、factory 和 hardware config 不再漂移。
- 开关箱链路不再与 S 参数绑定，文档和代码命名一致表达当前行为。
- 实时曲线 FLAG 识别可用单元测试覆盖，并支持非 0 起点扫描区间。
- `MainWindow` 只保留主窗口装配和顶层信号连接，业务决策迁入 application/presentation。
- 样式文件只包含当前项目需要的规则，界面密度不依赖末尾大范围覆盖。

## 进度记录规则

完成任一任务后，如果只是简单改动，可以只勾选任务。如果产生实现决策、验证记录或风险，应记录到：

```text
docs/ARCH_TASK_PROGRESS.md
```

推荐记录格式：

```text
### ARCH-TASK-YYYYMMDD-NNN - 任务标题

- 目标：
- 完成：
- 验证：
- 风险：
- 后续：
- 涉及文件：
```

## 验证命令

基础检查：

```powershell
& 'D:\Microsoft\Miniconda\envs\TEST\python.exe' -m py_compile src\quiet_zone_tester\main.py src\quiet_zone_tester\app.py
```

涉及 UI 时额外执行主窗口 offscreen 初始化检查：

```powershell
$env:QT_QPA_PLATFORM='offscreen'; $env:PYTHONPATH='src'; & 'D:\Microsoft\Miniconda\envs\TEST\python.exe' -c "from PySide6.QtWidgets import QApplication; from quiet_zone_tester.ui.main_window import MainWindow; app=QApplication([]); w=MainWindow(); w.resize(1200, 800); w.show(); app.processEvents(); print('ok')"
```

## 迁移边界

- P0 阶段不移动旧业务代码，只建骨架和基础模型。
- 未完成 dataclass 适配前，旧 `dict` API 不删除。
- 未完成 ViewModel 前，旧 Widget 信号不删除。
- 未完成 hardware 兼容导入前，旧 `drivers/` 和 `instruments/` 不删除。
- 每个阶段必须保持应用可启动。
