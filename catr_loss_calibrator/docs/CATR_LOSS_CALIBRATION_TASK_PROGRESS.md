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
