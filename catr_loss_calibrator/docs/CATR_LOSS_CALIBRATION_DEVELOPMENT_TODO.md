# CATR 路损校准软件开发 TODO

Status: Active  
Domain: CATR_LOSS_CALIBRATOR  
Canonical: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`  
Related: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md`, `catr_loss_calibrator/docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`  
更新时间：2026-07-18

本文档跟踪 `catr_loss_calibrator` 独立软件的开发任务。任务按 P0-P5 优先级排列，优先保证“架构边界正确、校准流程可跑、数据可追溯”，再逐步完善 UI、真实硬件和长期可靠性。

## TODO 规则

- 任务编号使用 `P0-01`、`P1-01` 等稳定编号，不复用编号。
- 每个任务必须有可验证的完成条件。
- 完成任务时只修改勾选状态；详细过程写入 `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`。
- 文档、代码、测试三者不一致时，优先暂停实现并更新 TODO 或设计文档。
- 涉及真实仪表、链路箱或射频输出的任务必须默认使用 Mock；真实硬件验证需显式启用并记录设备信息。
- 校准公式口径不得在普通重构中顺手修改；如需修改公式，必须先更新校准方案并单独评审。

## 验收标准摘要

| 优先级 | 验收标准 |
|---|---|
| P0 | 项目边界清楚，目录骨架完整，5 个校准项可列出，且不依赖 `quiet_zone_tester`。 |
| P1 | 链路端口、链路箱 profile、校准步骤命令和人工接线说明可由软件模型表达。 |
| P2 | 5 个校准项能用 Mock 数据生成 raw trace、metadata 和最终带符号路损文件。 |
| P3 | 操作人员可通过 UI/CLI 按步骤完成 Mock 校准，非法操作被状态机阻止。 |
| P4 | 真实 VNA + LCD74000F 至少完成一个校准项闭环，并有硬件验证记录。 |
| P5 | 软件具备 session 追溯、复算、报告导出、长期稳定性验证和版本管理。 |

## 推荐执行顺序

| 顺序 | 待办 | 原因 |
|---|---|---|
| 1 | P0-05 catalog 与 HTML 方案一致性 | 先固定 5 个校准项的真实边界，否则后续模型都会漂。 |
| 2 | P0-06 公式口径检查 | 公式是后续数据文件的根，必须先防止符号口径分裂。 |
| 3 | P1-03 链路箱 profile 数据化 | 自动化校准依赖稳定的链路模板。 |
| 4 | P1-04 校准步骤输入/输出/接线定义 | 这是 UI 引导和 runner 执行的共同数据源。 |
| 5 | P2-01/P2-02 trace 与 raw/final 存储 | 先保证数据事实能落盘，再谈真实硬件。 |
| 6 | P3-02 状态机 | 防止 UI 和执行流在人工确认、采样、保存阶段互相绕过。 |
| 7 | P4 真实硬件适配 | 在 Mock 闭环稳定后再接真实设备，降低现场风险。 |

## P0 - 架构边界与基础骨架

- [x] P0-01 建立独立项目 `catr_loss_calibrator`，避免依赖 `quiet_zone_tester` 运行时。
- [x] P0-02 按业务域建立基础目录：`presentation`、`app`、`application`、`calibration`、`instrument_management`、`link_management`、`hardware`、`storage`、`project`、`diagnostics`。
- [x] P0-03 将 UI / presentation 层提前，作为面向操作人员的交互入口。
- [x] P0-04 定义 `LINK-CAL-001` 至 `LINK-CAL-005` 五个校准项 catalog。
- [x] P0-05 检查并修正 catalog 中所有校准项名称、步骤编号、输出参数，使其与 `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` 完全一致。
- [x] P0-06 检查公式实现，确保不引入 `AUX_CORR`，不把 `L_AUX_*` 改成正损耗口径。
- [x] P0-07 建立项目级 import 边界测试，确认新软件不 import `quiet_zone_tester.*`。

### P0 验收

- `python -m catr_loss_calibrator` 可在 `PYTHONPATH=src` 下运行。
- 输出包含 `LINK-CAL-001` 至 `LINK-CAL-005`。
- `rg "quiet_zone_tester" catr_loss_calibrator/src catr_loss_calibrator/tests` 无业务依赖。
- 公式相关测试明确覆盖 `L_AUX_*` 带符号直接相加。

## P1 - 校准项模型与链路箱命令

- [x] P1-01 建立链路端口枚举与 `CONFigure:LINK ...` 命令生成器。
- [x] P1-02 建立 LCD74000F profile 基础端口校验。
- [x] P1-03 将 `resource/LCD74000F.md` 中的链路命令整理为软件内 profile 数据。
- [x] P1-04 为每个 `LINK-CAL` 步骤定义明确的输入端口、输出端口、人工接线说明、链路箱指令。
- [ ] P1-05 区分正式输出参数、原始 `S21_*`、临时追溯参数 `T_*`。
- [ ] P1-06 为链路模板增加单元测试，覆盖直通、AMP1、AMP2、SG、SA、VNA1/VNA2 工况。

### P1 验收

- 每个校准步骤都能列出：步骤 ID、人工接线说明、链路箱指令、原始输出、最终输出、依赖输入。
- `CONFigure:LINK ...` 命令生成器对非法端口给出稳定错误。
- LCD74000F profile 能校验 AMP1/AMP2 的方向约束。

## P2 - 数据与公式闭环

- [x] P2-01 建立统一 trace 数据模型，保存频率、幅度、相位、参数名、来源步骤。
- [x] P2-02 建立原始 S21 保存策略，区分 raw trace 与最终路损文件。
- [ ] P2-03 建立 metadata 保存策略，记录项目配置、仪表信息、链路命令、人工确认、输入文件 hash、输出文件 hash。
- [ ] P2-04 将 5 个校准项的最终输出公式逐项落到 `calibration/formulas.py`。
- [ ] P2-05 为每个最终输出参数建立单元测试，验证带符号 dB 计算。
- [ ] P2-06 落实文件命名规则：`{PARAM}_{BAND}_{FEED}_{HORN}.csv`。
- [ ] P2-07 建立馈源/喇叭有效频段交集校验。

### P2 验收

- 每个正式 `L_*` 输出均能追溯到来源校准项、来源步骤、原始 S21 和依赖输入。
- 每个输出 CSV 包含 `freq_hz`、`value_db`、`param`、`band`、`feed`、`horn`、`source_cal`。
- metadata 记录公式版本、profile 版本、输入文件 hash 和输出文件 hash。

## P3 - Mock 流程与操作员 UI

- [ ] P3-01 建立 Mock VNA 与 Mock 链路箱的完整校准流程模拟。
- [ ] P3-02 建立校准执行状态机：`IDLE → WAIT_MANUAL_CONFIRM → CONFIGURE_LINK → CONFIGURE_VNA → TRIGGER_SWEEP → READ_TRACE → SAVE_RAW → COMPUTE_OUTPUT → SAVE_OUTPUT → DONE`。
- [ ] P3-03 建立人工接线确认步骤，支持暂停、跳过、重试和取消。
- [ ] P3-04 建立一期 UI 主窗口或 CLI/TUI 操作入口，优先满足操作人员按步骤执行。
- [ ] P3-05 UI 显示当前校准项、当前步骤、接线说明、链路箱命令、输出文件。
- [ ] P3-06 UI 禁止非法操作：采样中修改配置、未连接硬件执行链路切换、校准中重复启动。

### P3 验收

- 操作人员能看到当前校准项、当前步骤、接线说明、链路命令、采样状态和输出文件。
- 人工确认步骤必须显式确认后才能继续。
- 取消、失败、完成三种结局在 UI/CLI 和 session 中可区分。

## P4 - 真实硬件适配与可靠性

- [ ] P4-01 实现真实 VNA VISA adapter，支持连接、配置 sweep、单次触发、读取 S21。
- [ ] P4-02 实现真实 LCD74000F 链路箱 adapter，支持命令下发、响应检查、错误提示。
- [ ] P4-03 建立仪表连接管理：VNA、链路箱、SG、SA 的连接配置、状态快照和失败清理。
- [ ] P4-04 建立资源互锁：校准中独占 VNA 和链路箱，禁止与静区测试软件同时操作。
- [ ] P4-05 建立超时和失败恢复策略：VNA 采样超时、链路箱无响应、保存失败、人工取消。
- [ ] P4-06 建立真实硬件验证 checklist，覆盖连接、链路切换、采样、保存、错误恢复。

### P4 验收

- 真实硬件测试默认不运行，必须显式启用。
- 验证记录包含日期、操作者、VNA 型号/序列号/固件、链路箱型号、连接方式。
- 链路切换、VNA 触发、采样点数、保存文件、错误恢复均有记录。

## P5 - 工程化、报告与长期维护

- [ ] P5-01 建立校准 session 管理，支持历史记录、复算和结果追溯。
- [ ] P5-02 建立日志与错误报告，能回答“哪一步、哪条命令、哪个文件、为什么失败”。
- [ ] P5-03 建立校准结果浏览和导出功能。
- [ ] P5-04 建立长期稳定性测试，覆盖多频段、多喇叭、多校准项循环执行。
- [ ] P5-05 建立版本管理：公式版本、profile 版本、报告版本、软件版本。
- [ ] P5-06 与 `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` 保持同步，文档变更后更新 catalog、公式和测试。

### P5 验收

- 任意最终路损文件都能追溯到 session、输入文件、公式版本和校准步骤。
- 支持只复算、不重新采样。
- 长时间 Mock 或真实硬件循环验证有统计记录。

## 验收原则

- P0 完成后，项目结构正确，入口可运行，5 个校准项可列出。
- P1 完成后，每个校准步骤的链路命令和人工接线说明可由软件生成。
- P2 完成后，Mock 数据可生成完整 raw trace、metadata 和最终路损 CSV。
- P3 完成后，操作人员可按 UI/CLI 引导完成一次 Mock 校准。
- P4 完成后，可在真实 VNA + LCD74000F 环境中完成至少一个完整校准项。
- P5 完成后，软件具备可追溯、可复算、可维护的工程交付能力。

## 任务进度记录规则

完成任一任务后，在 `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md` 顶部追加记录：

```markdown
### CATR-CAL-TASK-YYYYMMDD-NNN - 任务标题

- 状态：进行中 / 完成 / 阻塞 / 暂停
- 日期：YYYY-MM-DD
- 任务目标：
  - ...
- 完成内容：
  - ...
- 验证结果：
  - ...
- 还需完成：
  - ...
- 关联文件：
  - `path/to/file`
- 下一步：
  - ...
```
