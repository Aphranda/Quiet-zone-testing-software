# 文档命名与层级规则

Status: Active  
Domain: Documentation  
Canonical: `catr_loss_calibrator/docs/DOCS_NAMING_STRUCTURE_PLAN.md`  
Related: `catr_loss_calibrator/docs/README.md`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`  
Last updated: 2026-07-18

本文档定义 `catr_loss_calibrator/docs/` 下文档的命名格式、层级关系、交叉引用规则和新增文件规则。所有文档按 UTF-8 读取和写入。

## 基本原则

- `README.md` 是文档总入口，新增文档后必须更新索引。
- 新 Markdown 文档优先使用 ASCII、全大写领域前缀、下划线分隔和明确类型后缀。
- 报告交付类 HTML 可保留项目约定名称，但需要在 `README.md` 中明确 canonical 入口。
- 一个文档只承担一种主职责：设计、方案、TODO、进度、操作、检查或报告。
- 设计文档不长期堆积任务日志；任务清单放入 `*_TODO.md`，验证记录放入 `*_TASK_PROGRESS.md` 或 `TASK_PROGRESS.md`。
- 涉及校准公式、链路箱指令、仪表命令、文件命名和 CSV 字段的文档，应优先使用表格或固定字段描述。

## 文件名格式

新 Markdown 文件统一使用：

```text
<DOMAIN>_<SUBJECT>_<TYPE>.md
```

示例：

```text
CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md
CALIBRATION_DOMAIN_DESIGN.md
LINK_BOX_COMMANDS.md
HARDWARE_VALIDATION_CHECKLIST.md
```

命名字段规则：

| 字段 | 规则 |
|---|---|
| `DOMAIN` | 领域前缀，使用全大写 ASCII，例如 `CATR`、`CALIBRATION`、`LINK_BOX`。 |
| `SUBJECT` | 主题名，使用全大写 ASCII 和下划线，表达具体对象。 |
| `TYPE` | 文档类型后缀，必须从允许列表中选择。 |

## 领域前缀

| 前缀 | 领域 |
|---|---|
| `CATR` | CATR 暗室、总体方案、校准测试方案。 |
| `CALIBRATION` | 校准项、校准流程、公式和参数。 |
| `LINK_BOX` | 链路箱端口、指令、profile 和链路模板。 |
| `INSTRUMENT` | VNA、SG、SA 等仪表连接和资源管理。 |
| `HARDWARE` | 硬件适配、真实设备验证和可靠性。 |
| `STORAGE` | raw trace、metadata、最终路损文件和 session 追溯。 |
| `UI` | 操作人员界面、交互流程和页面状态。 |
| `REPORT` | HTML 报告、截图检查和交付格式。 |
| `DOCS` | 文档体系、命名规则和索引。 |

## 类型后缀

| 后缀 | 用途 |
|---|---|
| `_ARCHITECTURE.md` | 顶层或跨模块架构，说明边界、依赖方向和长期原则。 |
| `_DESIGN.md` | 具体功能、状态机、数据结构、硬件适配或公式设计。 |
| `_PLAN.md` | 阶段性实施计划、迁移计划、重构计划。 |
| `_TODO.md` | 可执行任务清单，按 P0/P1/P2 或 P0-P5 拆分。 |
| `_TASK_PROGRESS.md` | 任务进度、闭环验证、风险和决策记录。 |
| `_CHECKLIST.md` | 真实硬件验证、发布或评审门禁检查表。 |
| `_PLAYBOOK.md` | 可重复执行的操作手册或迁移手册。 |
| `_COMMANDS.md` | 仪表命令、链路箱命令或用户可调用命令列表。 |
| `_ANALYSIS.md` | 链路、数据、性能、风险或问题分析。 |

不得随意新增近义后缀，例如 `_NOTE.md`、`_DOC.md`、`_SPEC.md`。确需新增时，先更新本文档。

## 层级关系

当前 `catr_loss_calibrator/docs/` 采用平铺文件存放，逻辑层级由 `README.md` 维护。

逻辑层级如下：

```text
00 文档治理
01 软件设计
02 校准测试方案
03 校准域与链路箱
04 仪表与硬件验证
05 数据存储与文件命名
06 UI 与操作流程
07 报告与截图检查
08 开发 TODO 与任务进度
```

若后续文档数量明显增加，再评估迁移为子目录：

```text
docs/calibration/
docs/hardware/
docs/report/
```

迁移到子目录前必须列出旧路径、新路径和引用影响，并同步更新所有引用。

## 文档元数据

新 Markdown 文档标题下方应包含固定元数据块：

```text
Status: Draft | Active | Frozen | Deprecated
Domain: <DOMAIN>
Canonical: `catr_loss_calibrator/docs/<FILE>.md`
Related: `catr_loss_calibrator/docs/<RELATED>.md`
Last updated: YYYY-MM-DD
```

## 新增文件规则

新增文档前按以下顺序判断：

1. 能否补充到现有 canonical 文档中。
2. 是否需要独立生命周期，例如独立 TODO、独立进度、独立硬件验证。
3. 是否已有同域同类型文件，避免重复创建近义文档。
4. 文件名是否符合 `<DOMAIN>_<SUBJECT>_<TYPE>.md`。
5. 新文件是否已加入 `README.md` 索引。
6. 新文件是否在相关主文档中被引用。

## TODO 与进度规则

`*_TODO.md` 用于还没完成的工作，推荐格式：

```text
## P0 - 必须完成
- [ ] P0-01 任务标题：验收标准。

## P1 - 应该完成
- [ ] P1-01 任务标题：验收标准。
```

`*_TASK_PROGRESS.md` 或 `TASK_PROGRESS.md` 用于记录已经发生的工作，推荐格式：

```text
### CATR-CAL-TASK-YYYYMMDD-NNN - 任务标题

- 状态：
- 日期：
- 任务目标：
- 完成内容：
- 验证结果：
- 还需完成：
- 关联文件：
- 下一步：
```

设计文档中可以保留简短未决问题，但不应把大量任务过程堆在设计正文里。

## 交叉引用规则

- 从仓库根目录引用新软件文档时，使用 `catr_loss_calibrator/docs/<FILE>`。
- 从 `catr_loss_calibrator/docs/` 内部文档引用同目录文件时，可直接使用 `<FILE>`。
- 文件改名或移动时，必须全文搜索旧文件名并同步引用。
- 禁止只写“见前文/见上文”而不提供文件名。

引用检查建议：

```powershell
rg -n "CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN|CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO|CATR_LOSS_CALIBRATION_TASK_PROGRESS" catr_loss_calibrator/docs
```

## 评审规则

新增或重构文档时，至少检查：

- 文件名符合规则。
- 顶部元数据齐全。
- 已加入 `README.md`。
- 与相关设计、TODO、进度文件互相可追踪。
- 校准公式、链路箱指令、仪表命令和文件命名没有语义冲突。
- 文档采用 UTF-8，中文内容没有乱码。
