# 架构迁移 TODO

Status: Active
Domain: ARCH
Canonical: `docs/ARCH_MIGRATION_TODO.md`
Related: `docs/architecture_migration_plan.md`
Last updated: 2026-07-09

本文档跟踪静区测试软件架构迁移任务。TODO 只记录尚未完成或需要持续跟踪的事项；已经发生的实施过程、验证结果、风险和决策，应记录到后续 `ARCH_TASK_PROGRESS.md`，避免任务清单变成流水账。

## TODO 规则

- 任务按 P0/P1/P2 优先级分组。
- 任务编号使用 `P0-01`、`P1-01`、`P2-01` 格式，编号稳定，不复用。
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
- [ ] P1-03 抽出 `ScanPlanner`：X 线段、Y 线段、二维蛇形路径统一由 planner 输出，动画和扫描执行共用同一规划结果。
- [ ] P1-04 抽出 `LinkRouter`：`S11/S21/S12/S22` 到开关箱命令映射独立成模块，支持 LCD74000F/TC500 profile。
- [ ] P1-05 引入连接配置 dataclass：VNA、扫描架、开关箱连接配置从 `dict` 逐步迁移到 dataclass，保留旧 API 适配。
- [ ] P1-06 引入扫描配置 dataclass：`ScanSettings`、`ProbeOffset`、`SweepSettings` 替代散落 `dict` 字段。
- [ ] P1-07 建立 `LogRecordModel`：运行日志从纯文本追加迁移为结构化 Qt Model，保留当前日志视图行为。

### P1 验收

- 文件命名规则有单元测试。
- Trace CSV、metadata、trace index 输出格式不回归。
- 扫描路径规划可不连接仪器独立测试。
- 链路路由可不连接开关箱独立测试。
- 新 dataclass 与旧 `dict` API 可以共存一段时间。
- 日志记录具备结构化字段：时间、等级、来源、消息。

## P2 - ViewModel、Facade 和硬件层迁移

- [ ] P2-01 `ConnectionPanel` 迁移到 ViewModel：Widget 只负责显示和发信号；连接配置、串口刷新、开关箱型号逻辑进入 ViewModel。
- [ ] P2-02 `TestSetupPanel` 迁移到 ViewModel：扫描参数校验、探头位置、默认值和预览配置进入 ViewModel。
- [ ] P2-03 `PositionerControlPanel` 迁移到运动控制域：手动运动命令、当前位置显示、轮询逻辑由 Motion ViewModel 和 MotionService 管理。
- [ ] P2-04 `SwitchBoxControlPanel` 迁移到链路管理域：链路控制 UI 使用 LinkViewModel 和 LinkService，不直接拼命令。
- [ ] P2-05 `InstrumentService` 变成 facade：连接、运动、链路、扫描、采样、数据保存都委托到独立 domain service。
- [ ] P2-06 硬件层目录迁移：当前 `drivers/` 和 `instruments/` 迁移到 `hardware/`，并保持兼容导入或一次性更新引用。
- [ ] P2-07 文档体系拆分：从主迁移方案拆出 APP、仪表、链路、运动、扫描、数据管理设计文档。

### P2 验收

- `MainWindow` 只做主窗口装配和顶层路由。
- Widget 不直接拼业务配置。
- `InstrumentService` 不再包含文件命名、路径规划、硬件创建细节。
- 真实硬件实现和 Mock 实现都通过 `hardware/interfaces.py` 暴露统一接口。
- 文档主入口、设计文档、TODO、进度记录职责清晰。

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
