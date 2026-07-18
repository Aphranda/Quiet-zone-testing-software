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
