# CATR Loss Calibrator 文档索引

Status: Active  
Domain: Documentation  
Canonical: `catr_loss_calibrator/docs/README.md`  
Related: `catr_loss_calibrator/docs/DOCS_NAMING_STRUCTURE_PLAN.md`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`  
Last updated: 2026-07-18

本目录保存独立路损校准软件相关文档，便于新软件脱离当前静区测试软件后仍能完整追溯设计依据。

## Canonical 主文档

| 领域 | 当前 canonical 主文档 | 说明 |
|---|---|---|
| SOFTWARE | `CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md` | 独立路损校准软件总体设计入口。 |
| CALIBRATION_PLAN | `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` | CATR 暗室校准测试方案报告版，定义 5 个校准项和测试项链路。 |
| DOCS | `DOCS_NAMING_STRUCTURE_PLAN.md` | 文档命名、层级、元数据和新增文件规则。 |
| DEVELOPMENT | `CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md` | 软件开发待办，按 P0-P5 跟踪。 |
| PROGRESS | `CATR_LOSS_CALIBRATION_TASK_PROGRESS.md` | 软件任务进度、闭环验证和决策记录。 |
| OPERATION | `CATR_CHAMBER_OPERATION_PLAYBOOK.md` | 当前校准/测试操作口径汇总。 |
| REPORT_CHECK | `REPORT_SCREENSHOT_CHECK_PLAYBOOK.md` | HTML 报告截图检查复用指南。 |

## 进度记录路由

| 类型 | 当前进度入口 | 规则 |
|---|---|---|
| 软件开发任务 | `CATR_LOSS_CALIBRATION_TASK_PROGRESS.md` | 完成 P0-P5 任一正式任务后追加记录。 |
| 开发待办 | `CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md` | 只维护任务勾选、优先级和验收标准。 |
| 校准方案待办 | `CATR_CHAMBER_CALIBRATION_TEST_PLAN_TODO.md` | 跟踪报告方案本身的历史操作和遗留事项。 |

## 01 软件设计

| 文档 | 用途 |
|---|---|
| `CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md` | 独立路损校准软件设计方案。 |
| `CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md` | CATR 路损校准软件 P0-P5 开发 TODO。 |
| `CATR_LOSS_CALIBRATION_TASK_PROGRESS.md` | CATR 路损校准软件任务进度记录。 |

## 00 文档治理

| 文档 | 用途 |
|---|---|
| `DOCS_NAMING_STRUCTURE_PLAN.md` | 文档命名格式、层级关系、元数据和新增文件规则。 |

## 02 校准测试方案

| 文档 | 用途 |
|---|---|
| `CATR_CHAMBER_CALIBRATION_TEST_PLAN.md` | CATR 暗室校准测试方案 Markdown 版。 |
| `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` | CATR 暗室校准测试方案 HTML 报告版。 |
| `CATR_CHAMBER_OPERATION_PLAYBOOK.md` | 当前校准/测试操作口径汇总。 |
| `CATR_CHAMBER_CALIBRATION_TEST_PLAN_TODO.md` | 当前方案历史操作、待办和新软件开发计划。 |

## 03 报告与检查

| 文档 | 用途 |
|---|---|
| `REPORT_SCREENSHOT_CHECK_PLAYBOOK.md` | HTML 报告截图检查复用指南。 |

## 快速查找规则

- 查软件边界和目录结构：先读 `CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md`。
- 查文档命名和新增文件规则：先读 `DOCS_NAMING_STRUCTURE_PLAN.md`。
- 查当前开发优先级：先读 `CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`。
- 查已经做过什么：先读 `CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`。
- 查校准项、测试项、链路和文件命名：先读 `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`。
- 查当前人工操作口径：先读 `CATR_CHAMBER_OPERATION_PLAYBOOK.md`。
- 查报告截图检查方法：先读 `REPORT_SCREENSHOT_CHECK_PLAYBOOK.md`。

## 注意

- `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` 中的图片路径可能仍指向原报告资源目录；如需独立离线打开 HTML 图页，需要同步复制图片资源文件夹。
- 新软件代码不得依赖当前静区测试软件运行时；这些文档只作为设计依据和验收依据。
