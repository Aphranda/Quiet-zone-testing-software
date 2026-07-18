# CATR 路损校准软件任务进度记录

Status: Active  
Domain: CATR_LOSS_CALIBRATOR  
Canonical: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`  
Related: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md`  
Last updated: 2026-07-18

本文档记录 `catr_loss_calibrator` 的正式开发任务进度。每完成一个正式任务后，在“任务记录”章节顶部追加记录，说明任务目标、完成内容、验证结果、剩余工作和下一步计划。

## 记录规则

- 每个正式任务使用独立编号：`CATR-CAL-TASK-YYYYMMDD-NNN`。
- 只记录已经进入文档、代码或测试的正式任务，不记录临时讨论。
- 如果任务只完成阶段性目标，状态写为 `进行中`，不能写成 `完成`。
- 如果没有执行测试，需要在验证结果中明确写出“未执行测试”或原因。
- 涉及真实硬件但未接入设备时，应明确写出“仅完成 Mock/导入验证，未做真实硬件验证”。
- 最新记录追加在最前面。

## 状态定义

| 状态 | 含义 |
|---|---|
| `完成` | 当前任务目标已经达成，并完成必要验证。 |
| `进行中` | 已完成阶段性工作，但任务闭环还未完成。 |
| `阻塞` | 当前无法继续，需要外部条件、硬件、资料或决策。 |
| `暂停` | 暂时不推进，但不是技术阻塞。 |

## 记录模板

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

## 任务记录

### CATR-CAL-TASK-20260718-014 - 通用控制台与 JSON catalog 导入基础

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将 UI/CLI 名称从“CATR 路损校准操作台”调整为“通用路损校准控制台”。
  - 生成当前 CATR 五个 `LINK-CAL` 校准项的内置 JSON 配置。
  - 建立链路配置 JSON loader，并让默认 catalog 从内置 JSON 加载。
- 完成内容：
  - 新增 `calibration/configs/catr_chamber_loss_calibration.json`，包含 `LINK-CAL-001` 至 `LINK-CAL-005` 的校准项、大步骤、细分步骤、链路命令和输出/依赖参数。
  - 新增 `calibration/config_loader.py`，支持校验 schema 版本、加载 JSON 并转换为 `CalibrationCatalog`。
  - 扩展 `CalibrationCatalog`、`CalibrationStep`、`CalibrationSubStep`，为后续 JSON 驱动节点图预留 `node_catalog`、`path_templates`、`path_template` 和 `path` 字段。
  - `default_calibration_catalog()` 已改为加载内置 JSON，原 Python catalog 保留为 `legacy_python_calibration_catalog()` 供迁移期测试对照。
  - UI/CLI 标题改为“通用路损校准控制台”，当前 CATR 作为已加载配置显示。
  - 更新开发 TODO 与 UI TODO，标记已完成阶段并保留 JSON 节点图迁移任务。
- 验证结果：
  - `py_compile` 通过：`models.py`、`config_loader.py`、`definitions.py`、`presentation/main.py`。
  - 通过测试：`test_calibration_catalog.py`、`test_mock_runner.py`、`test_link_management.py`、`test_presentation_viewmodels.py`，共 25 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - 为内置 CATR JSON 补齐 `node_catalog`、`path_templates` 和每个步骤/细分步骤的 `path_template` 引用。
  - 将 UI 接线路径节点图从 presentation 层硬编码模板迁移到 JSON 配置。
  - 增加用户可选文件的“导入链路配置”入口和错误提示。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/config_loader.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/configs/catr_chamber_loss_calibration.json`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/definitions.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_calibration_catalog.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 执行 P1-13 / P1-12 / UI-71，先把 HTML 节点图落入 JSON，再让 UI 使用 JSON 路径绘制。

### CATR-CAL-TASK-20260718-013 - P5 追溯与导出基础

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 建立校准 session 管理、日志与错误报告、结果导出基础。
  - 让最终结果和运行记录具备追溯与浏览能力。
- 完成内容：
  - 扩展 `CalibrationSessionRepository`，支持会话记录保存。
  - 扩展 `ErrorReport` 与 `LogRecord`，支持 JSON 落盘。
  - 新增 `report_exporter.py`，支持 session 报告 JSON/CSV 导出。
  - 新增 `tests/test_p5_reporting.py`。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - 生成的 session、log、error、report 文件可正常写出。
- 还需完成：
  - P5-04 / P5-05：长期稳定性测试与版本管理。
  - P5-06：继续跟随 HTML 方案同步文档变更。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/calibration_session_repository.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/diagnostics/error_report.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/diagnostics/log_record.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/report_exporter.py`
  - `catr_loss_calibrator/tests/test_p5_reporting.py`
- 下一步：
  - 推进 P5-04 / P5-05，补长期稳定性和版本管理。

### CATR-CAL-TASK-20260718-012 - P4 超时回滚与硬件验证记录

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 建立真实硬件连接失败后的超时/回滚策略。
  - 建立真实硬件验证记录模型。
  - 固化真实硬件验证 checklist。
- 完成内容：
  - 新增 `ConnectionRecoveryPolicy`，支持连接重试与回滚清理。
  - `InstrumentConnectionService` 连接失败后会自动清理已连接仪表，并支持按策略重试。
  - 新增 `HardwareValidationRecord` 与 `save_hardware_validation_record()`。
  - 新增 `tests/test_hardware_validation.py`。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - 未接入真实 VNA/LCD74000F，未做真实硬件验证。
- 还需完成：
  - P4-01 / P4-02：真实设备实机联调。
  - 若现场需要，可继续补充更细的命令级错误映射。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/instrument_management/recovery.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/instrument_management/connection_service.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/diagnostics/hardware_validation.py`
  - `catr_loss_calibrator/tests/test_instrument_management.py`
  - `catr_loss_calibrator/tests/test_hardware_validation.py`
- 下一步：
  - 回到 P4-01 / P4-02，等真实设备信息补全后做上机验证。

### CATR-CAL-TASK-20260718-011 - P4 硬件适配与连接管理骨架

- 状态：进行中
- 日期：2026-07-18
- 任务目标：
  - 建立真实 VNA VISA adapter 和真实 LCD74000F 链路箱 adapter。
  - 建立仪表连接管理、状态快照、资源互锁和失败回滚。
  - 准备真实硬件验证清单。
- 完成内容：
  - 新增 `PyVisaVna`，支持真实 VNA 连接、扫频配置、触发和读取接口骨架。
  - 新增 `Lcd74000fLinkBox`，支持真实链路箱连接与命令下发骨架。
  - 重构 `InstrumentConnectionService`，支持 mock / real-capable 配置、连接快照和异常回滚。
  - 新增 `InstrumentManagementService`，提供资源独占、连接管理与统一快照。
  - 新增 `HARDWARE_VALIDATION_CHECKLIST.md`。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - 未接入真实 VNA/LCD74000F，未做真实硬件验证。
- 还需完成：
  - P4-01 / P4-02：真实设备上机验证与命令兼容性确认。
  - P4-05：超时、失败恢复和人工取消的完整策略。
  - P4-06：真实硬件验证记录落地。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/hardware/vna/pyvisa_vna.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/hardware/link_box/lcd74000f.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/instrument_management/connection_service.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/instrument_management/instrument_management_service.py`
  - `catr_loss_calibrator/docs/HARDWARE_VALIDATION_CHECKLIST.md`
- 下一步：
  - 推进真实硬件接入验证，优先补 P4-01 / P4-02 的实机联调。

### CATR-CAL-TASK-20260718-010 - P3 状态展示与非法操作防护

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 让 UI/CLI 显示当前校准项、步骤、接线说明、链路命令和运行状态。
  - 对未连接仪表、重复启动等非法操作进行阻止。
- 完成内容：
  - 为 `MockCalibrationRunner` 增加 `overview()` 和 `format_step_status()`。
  - 在 runner 中加入运行前连接检查，并禁止 busy 状态重复启动。
  - `presentation.main` 在 demo 和交互模式下输出状态概览。
  - 新增测试覆盖状态概览和未连接仪表异常。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - CLI demo 输出状态概览正常。
  - 未执行真实硬件验证。
- 还需完成：
  - 进入 P4，开始真实硬件适配与可靠性。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
- 下一步：
  - 推进 P4-01 / P4-02，接真实 VNA 和 LCD74000F adapter。

### CATR-CAL-TASK-20260718-009 - P3 人工确认与交互入口

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 建立人工接线确认步骤，支持暂停、跳过、重试和取消。
  - 建立一期 UI/CLI 操作入口，面向操作人员逐步执行。
- 完成内容：
  - 扩展 `MockCalibrationRunner`，支持 `confirm_step` 回调与 `continue/skip/retry/cancel` 行为。
  - `presentation.main` 增加 `--interactive` 模式，可按步骤输出接线说明、链路命令并接收操作员选择。
  - 新增/扩展 `tests/test_mock_runner.py`，覆盖 skip/cancel 流程。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - CLI demo 和交互入口均可运行。
  - 未执行真实硬件验证。
- 还需完成：
  - P3-05 / P3-06：UI 状态展示与非法操作阻止。
  - 后续可把交互入口从 CLI 扩展为正式图形界面。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
- 下一步：
  - 推进 P3-05 / P3-06，把 UI 状态展示和非法操作防护补上。

### CATR-CAL-TASK-20260718-008 - P3 Mock 流程与状态机

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 建立 Mock VNA 与 Mock 链路箱的完整校准流程模拟。
  - 建立校准执行状态机。
  - 提供一个最简 UI/CLI 入口展示校准项与执行状态。
- 完成内容：
  - 新增 `CalibrationStateMachine`，支持 `IDLE -> WAIT_MANUAL_CONFIRM -> CONFIGURE_LINK -> CONFIGURE_VNA -> TRIGGER_SWEEP -> READ_TRACE -> SAVE_RAW -> COMPUTE_OUTPUT -> SAVE_OUTPUT -> DONE` 的受控迁移。
  - 新增 `MockCalibrationRunner`，可按步骤执行 Mock 校准、保存 raw trace 和 metadata。
  - `presentation.main.run()` 现在会展示校准项，并跑一遍 demo Mock 流程。
  - 新增 `tests/test_mock_runner.py` 覆盖状态机、Mock runner 和 CLI 入口。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - CLI demo 可运行并输出校准项与 Mock runner 状态。
  - 未执行真实硬件验证。
- 还需完成：
  - P3-03：人工接线确认步骤的暂停、跳过、重试和取消。
  - P3-04：正式 UI 主窗口或 CLI/TUI 操作入口。
  - P3-05 / P3-06：UI 状态展示与非法操作阻止。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/state_machine.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
- 下一步：
  - 推进 P3-03 / P3-04，把人工确认和 UI 入口做成真正可操作的流程。

### CATR-CAL-TASK-20260718-007 - P2 文件命名与频段交集闭环

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将最终路损文件命名规则串到保存流程。
  - 建立馈源/喇叭有效频段交集校验。
- 完成内容：
  - 在 `LossFilePolicy` 中新增 `validate_feed_horn()`、`filename_for()`、`path_for()`。
  - 在 `save_loss_record_with_policy()` 中自动推导 band 并写回最终记录。
  - 扩展 `tests/test_loss_file_policy.py` 和 `tests/test_storage_models.py`。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - 未执行真实硬件验证。
- 还需完成：
  - 进入 P3：Mock 流程与操作员 UI。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/loss_file_policy.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/loss_file_storage.py`
  - `catr_loss_calibrator/tests/test_loss_file_policy.py`
  - `catr_loss_calibrator/tests/test_storage_models.py`
- 下一步：
  - 推进 P3-01 / P3-02，开始 Mock 校准流程与状态机。

### CATR-CAL-TASK-20260718-006 - P2 公式与 metadata 闭环

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将 5 个校准项的最终输出公式落到代码。
  - 建立 metadata 保存策略，记录项目、仪表、链路命令和文件追溯信息。
  - 为每个最终输出参数建立带符号 dB 的单元测试。
- 完成内容：
  - 在 `calibration/formulas.py` 中补齐 `LINK-CAL-001` 至 `LINK-CAL-005` 的核心最终输出公式。
  - 新增 `aux_loss()`、`link_cal_002_*()`、`link_cal_003_*()`、`link_cal_004_*()`、`link_cal_005_*()` 等公式入口。
  - 新增 `storage.models.MetadataRecord`，并让 `write_metadata()` 支持直接写出 dataclass。
  - 扩展 `tests/test_formulas.py` 与 `tests/test_storage_models.py`，覆盖带符号 dB 计算和 metadata 落盘。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动加载并调用当前测试函数通过。
  - 未执行真实硬件验证。
- 还需完成：
  - P2-06：进一步打通最终路损文件命名规则与保存流程。
  - P2-07：补齐馈源/喇叭频段交集校验。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/formulas.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/metadata_writer.py`
  - `catr_loss_calibrator/tests/test_formulas.py`
  - `catr_loss_calibrator/tests/test_storage_models.py`
- 下一步：
  - 继续推进 P2-06 / P2-07，并开始把 metadata 串到 session 级保存流程。

### CATR-CAL-TASK-20260718-001 - 项目骨架与开发 TODO 建立

- 状态：进行中
- 日期：2026-07-18
- 任务目标：
  - 建立 `catr_loss_calibrator` 独立项目骨架。
  - 将 UI / presentation 层提前，面向操作人员组织入口。
  - 建立 P0-P5 开发 TODO 与任务进度记录机制。
- 完成内容：
  - 补齐 `presentation`、`application`、`instrument_management`、`link_management`、`hardware`、`storage`、`project`、`diagnostics` 等基础目录。
  - 新增 `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`。
  - 新增 `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`。
  - 将校准 catalog 调整为 `LINK-CAL-001` 至 `LINK-CAL-005`。
  - 初步建立链路端口枚举、链路命令模板和 LCD74000F profile 骨架。
- 验证结果：
  - `PYTHONPATH=src python -m catr_loss_calibrator` 可运行，并列出 5 个校准项。
  - 当前环境未安装 `pytest`，未执行 pytest 测试。
  - 未做真实硬件验证。
- 还需完成：
  - 按 `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` 逐项核对 catalog、公式和输出参数。
  - 建立 import 边界测试，确认不依赖 `quiet_zone_tester.*`。
  - 增加链路模板和公式单元测试。
- 关联文件：
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/definitions.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/link_management/`
- 下一步：
  - 优先执行 P0-05 和 P0-06，收口 catalog 与公式口径。

### CATR-CAL-TASK-20260718-002 - P0 口径收口与边界测试

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将 `LINK-CAL-001` 至 `LINK-CAL-005` 的 catalog 与 HTML 方案对齐。
  - 检查并固定公式口径，避免引入 `AUX_CORR` 或将 `L_AUX_*` 误改成正损耗约定。
  - 建立项目级 import 边界测试。
- 完成内容：
  - 修正 `calibration/definitions.py` 中 `LINK-CAL-003`、`LINK-CAL-004`、`LINK-CAL-005` 的名称与输出参数。
  - 增加 catalog 单元测试，覆盖 `LINK-CAL-003`、`LINK-CAL-004`、`LINK-CAL-005` 的关键输出。
  - 增加公式源代码检查测试，确认未出现 `AUX_CORR` 或正损耗转换口径。
  - 增加项目边界测试，确认 `src/catr_loss_calibrator` 与 `tests` 中不包含旧运行时导入依赖。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用所有测试函数通过。
  - `python -m pytest` 在当前环境中末尾卡住，未作为最终验证依据。
- 还需完成：
  - 后续继续推进 P1：链路箱 profile 数据化和每个校准步骤的输入/输出/接线定义。
  - 进一步将 `LINK-CAL-002/003/004/005` 的公式实现补齐到 `calibration/formulas.py`。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/definitions.py`
  - `catr_loss_calibrator/tests/test_calibration_catalog.py`
  - `catr_loss_calibrator/tests/test_formulas.py`
  - `catr_loss_calibrator/tests/test_project_boundaries.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
- 下一步：
  - 进入 P1-03 / P1-04，开始把链路箱 profile 和各校准步骤字段数据化。

### CATR-CAL-TASK-20260718-003 - 链路箱 profile 数据化

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将 `resource/LCD74000F.md` 中的常用链路命令整理为软件内 profile 数据。
  - 让 `LinkService` 能按 route_id 直接应用链路。
  - 为后续校准步骤模型提供稳定的链路模板入口。
- 完成内容：
  - 在 `link_management/lcd74000f_profile.py` 中建立默认 route catalog，覆盖 DUT/SA、DUT/VNA2、H/V、AMP1、AMP2、SG 等常用链路。
  - 为 `LinkService` 增加 `apply_route_id()`。
  - 增加 `test_link_management.py`，验证 route catalog、route_id 应用和命令生成。
  - 修复 `LinkService` 默认 profile 共享实例问题，改为 `default_factory`。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用全部测试函数通过。
  - `pytest` 在该环境中仍存在收集/运行卡顿问题，未作为最终依据。
- 还需完成：
  - 继续 P1-04：为每个 `LINK-CAL` 步骤补齐输入端口、输出端口、人工接线说明和链路箱指令。
  - 后续根据 HTML 方案进一步细化 CAL-004 / CAL-005 的路由对应关系。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/link_management/lcd74000f_profile.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/link_management/link_service.py`
  - `catr_loss_calibrator/tests/test_link_management.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
- 下一步：
  - 进入 P1-04，开始把每个校准步骤的数据字段补齐。

### CATR-CAL-TASK-20260718-004 - 校准步骤结构化字段补齐

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 为每个 `LINK-CAL` 步骤补齐输入端口、输出端口、人工接线说明和链路箱指令字段。
  - 让校准 catalog 不再只依赖自然语言说明，而是提供可编排的结构化数据。
- 完成内容：
  - 扩展 `CalibrationStep`，新增 `input_port`、`output_port` 和 `route_ids` 字段。
  - 为 `LINK-CAL-001` 至 `LINK-CAL-005` 的各个步骤补齐结构化端口信息。
  - 为 `LINK-CAL-003/004/005` 关键步骤补齐 route IDs，便于后续 UI / runner 直接复用链路模板。
  - 新增 `tests/test_link_management.py` 的步骤字段测试。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用全部测试函数通过。
  - 未执行真实硬件验证。
- 还需完成：
  - 继续 P2：把 `CalibrationStep` 的结构化字段连接到 raw trace、metadata 和最终输出保存链路。
  - 进一步把 `LINK-CAL-002` 的三工况和 `LINK-CAL-004/005` 的一致性校验量补成执行器可直接消费的模型。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/definitions.py`
  - `catr_loss_calibrator/tests/test_link_management.py`
- 下一步：
  - 转入 P2-01 / P2-02，开始做 trace 与 raw/final 存储闭环。

### CATR-CAL-TASK-20260718-005 - trace 模型与 raw/final 存储边界

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 建立统一 trace 数据模型。
  - 建立原始 S21 保存策略，区分 raw trace 和最终路损文件。
- 完成内容：
  - 新增 `storage/models.py`，定义 `TraceRecord` 作为统一 trace 记录。
  - 扩展 `raw_trace_storage.py`，增加 `trace_record_from_sparameter()`。
  - 新增 `loss_file_storage.py` 的 `save_loss_record()`，统一最终路损 CSV 保存入口。
  - 新增 `tests/test_storage_models.py`，覆盖 trace 记录生成与最终文件保存。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用全部测试函数通过。
  - 未执行真实硬件验证。
- 还需完成：
  - P2-03：补齐 metadata 保存策略，记录项目配置、仪表信息、链路命令和 hash。
  - P2-04：将 5 个校准项的最终输出公式逐项落到 `calibration/formulas.py`。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/raw_trace_storage.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/loss_file_storage.py`
  - `catr_loss_calibrator/tests/test_storage_models.py`
- 下一步：
  - 进入 P2-03 / P2-04，开始补 metadata 和公式闭环。
