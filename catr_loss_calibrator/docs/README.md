# CATR Loss Calibrator 文档索引

Status: Active  
Domain: Documentation  
Canonical: `catr_loss_calibrator/docs/README.md`  
Related: `catr_loss_calibrator/docs/DOCS_NAMING_STRUCTURE_PLAN.md`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`  
Last updated: 2026-07-19

本目录保存独立路损校准软件相关文档，便于新软件脱离当前静区测试软件后仍能完整追溯设计依据。

## Canonical 主文档

| 领域 | 当前 canonical 主文档 | 说明 |
|---|---|---|
| SOFTWARE | `CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md` | 独立路损校准软件总体设计入口。 |
| UI | `CATR_LOSS_CALIBRATION_UI_DESIGN.md` | 面向操作员的 PySide6/MVVM 界面设计入口。 |
| LINK_CONFIG_JSON | `CATR_LOSS_CALIBRATION_LINK_CONFIG_JSON.md` | 通用化链路配置 JSON 导入契约，定义校准项、步骤、细分步骤和节点图生成规则。 |
| HISTORY | `CATR_LOSS_CALIBRATION_HISTORY_PLAYBOOK.md` | 现场查看当前 session、latest、历史 session 和旧版输出目录的操作手册。 |
| RESUME | `CATR_LOSS_CALIBRATION_RESUME_PLAN.md` | 历史结果导入、细分步骤续测、曲线质量判断和是否重测的方案。 |
| UI TODO | `CATR_LOSS_CALIBRATION_UI_TODO.md` | UI 实现待办，按 P0-P3 跟踪。 |
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
| `CATR_LOSS_CALIBRATION_UI_DESIGN.md` | 独立路损校准软件 UI 设计方案。 |
| `CATR_LOSS_CALIBRATION_LINK_CONFIG_JSON.md` | 通用链路配置 JSON 导入规范。 |
| `CATR_LOSS_CALIBRATION_HISTORY_PLAYBOOK.md` | 历史校准文件查找、workspace 导入和旧版输出只读查看操作手册。 |
| `CATR_LOSS_CALIBRATION_RESUME_PLAN.md` | 历史结果导入、细分步骤续测、曲线质量判断和是否重测方案。 |
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
- 查 UI 设计和 UI 实现待办：先读 `CATR_LOSS_CALIBRATION_UI_DESIGN.md` 与 `CATR_LOSS_CALIBRATION_UI_TODO.md`。
- 查导入链路配置 JSON 结构：先读 `CATR_LOSS_CALIBRATION_LINK_CONFIG_JSON.md`。
- 查历史校准文件、latest 或旧版输出目录查看方法：先读 `CATR_LOSS_CALIBRATION_HISTORY_PLAYBOOK.md`。
- 查导入历史结果后如何续测、如何判断曲线是否需要重测：先读 `CATR_LOSS_CALIBRATION_RESUME_PLAN.md`。
- 查文档命名和新增文件规则：先读 `DOCS_NAMING_STRUCTURE_PLAN.md`。
- 查当前开发优先级：先读 `CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`。
- 查已经做过什么：先读 `CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`。
- 查校准项、测试项、链路和文件命名：先读 `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`。
- 查当前人工操作口径：先读 `CATR_CHAMBER_OPERATION_PLAYBOOK.md`。
- 查报告截图检查方法：先读 `REPORT_SCREENSHOT_CHECK_PLAYBOOK.md`。

## 注意

- `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` 中的图片路径可能仍指向原报告资源目录；如需独立离线打开 HTML 图页，需要同步复制图片资源文件夹。
- 新软件代码不得依赖当前静区测试软件运行时；这些文档只作为设计依据和验收依据。
