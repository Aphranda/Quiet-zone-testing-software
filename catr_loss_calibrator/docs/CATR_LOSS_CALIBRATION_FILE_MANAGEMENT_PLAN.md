# CATR 路损校准文件管理方案

Status: Draft
Domain: CATR_LOSS_CALIBRATOR
Canonical: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`
Related: `CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`, `CATR_LOSS_CALIBRATION_UI_TODO.md`
更新时间：2026-07-19

本文定义 `catr_loss_calibrator` 的校准文件空间、session 命名、metadata 关联和结果索引策略。目标是解决同一软件导入不同链路配置、同一配置服务多个项目、同一项目多阶段/多轮校准时的文件混淆问题。

## 设计目标

- 不同链路配置生成不同校准文件空间。
- 同一链路配置下，不同项目/样机/阶段/轮次有独立 session。
- 任意 raw、loss、metadata 文件都能反查配置、项目、阶段、轮次、校准项和来源步骤。
- 结果页默认只显示当前配置空间和当前 session，不混入历史目录。
- 保留旧版 `catr_loss_calibrator_output/raw|loss|metadata` 兼容读取，但新运行不再写入旧结构。

## 外部方案参考

| 方案 | 可借鉴点 | 不直接采用原因 |
|---|---|---|
| QCoDeS Dataset | 用 experiment name、sample name、run id 组合识别数据集；明确提示仅靠局部 run id 不适合跨库长期识别。 | QCoDeS 偏数据库式实验平台，本软件现阶段更适合文件目录 + manifest。 |
| Bluesky / Databroker | 每次 run 有唯一 UID、开始/结束 metadata、exit status；用户 metadata 用于回答 who/what/why/when。 | Bluesky 的 document stream 和 Tiled/Databroker 体系较重，超出当前桌面校准软件需要。 |
| PyMeasure Results | CSV 文件可带 Procedure 参数和 metadata header，文件名支持日期时间和过程参数占位符。 | 适合单过程测量文件；本软件需要 raw/loss/metadata 多文件 session 聚合。 |

参考链接：

- QCoDeS Dataset 文档：`https://microsoft.github.io/Qcodes/api/dataset/index.html`
- QCoDeS DataSet walkthrough：`https://microsoft.github.io/Qcodes/examples/DataSet/DataSet-class-walkthrough.html`
- Bluesky Documents：`https://blueskyproject.io/bluesky/v1.14.3/documents.html`
- Bluesky Metadata：`https://blueskyproject.io/bluesky/v1.14.0/metadata.html`
- PyMeasure Results：`https://pymeasure.readthedocs.io/en/latest/api/experiment/results.html`
- PyMeasure Metadata：`https://pymeasure.readthedocs.io/en/stable/tutorial/procedure.html`

## 推荐目录结构

```text
catr_loss_calibrator_output/
  workspaces/
    {workspace_id}/
      workspace.json
      projects/
        {project_code}/
          sessions/
            {session_id}/
              raw/
              loss/
              metadata/
              session_manifest.json
          latest/
            {item_id}.json
  legacy/
    raw/
    loss/
    metadata/
```

### workspace_id

`workspace_id` 由链路配置内容决定：

```text
{safe_config_name}_{config_hash_8}
```

- `safe_config_name`：优先使用 JSON 的 `name`，没有则使用 `display_name`，再没有则使用文件名。
- `config_hash_8`：对链路配置 JSON 文件内容计算 SHA256，取前 8 位。
- 同名但内容不同的配置会进入不同 workspace。

### project_code

`project_code` 来自校准界面必填输入，用于区分同一配置下的不同项目、样机或任务。

建议默认值：

```text
DEFAULT_PROJECT
```

现场建议填写：

```text
P2026-CATR-A
客户A-整机01
ANT-ARRAY-02
```

### session_id

`session_id` 由时间、校准项、阶段和轮次组成：

```text
{YYYYMMDD_HHMMSS}_{item_id}_{stage}_{run_label}
```

示例：

```text
20260719_153012_LINK-CAL-001_initial_R01
20260719_170522_LINK-CAL-001_retest_R02
```

内部 metadata 仍应额外记录 `run_uid`，用 UUID 保证全局唯一。

## 校准界面新增字段

建议在“校准执行”页的频段配置附近增加“校准批次”区域。

| 字段 | 控件 | 必填 | 用途 |
|---|---|---|---|
| 项目代号 `project_code` | 文本框 | 是 | 区分项目、样机、任务。 |
| 校准阶段 `calibration_stage` | 可编辑下拉框 | 是 | 区分初始校准、复测、维修后、变更后、交付前、问题排查。 |
| 批次/轮次 `run_label` | 文本框 | 否 | 区分同阶段多次运行，例如 R01、R02、换线后。 |
| 操作员 `operator` | 文本框 | 否 | 记录执行人。 |
| 备注 `operator_note` | 文本框 | 否 | 记录环境、接线变化、异常说明。 |

## session_manifest.json

每次运行生成一个 session manifest：

```json
{
  "schema_version": "catr-session-manifest.v1",
  "run_uid": "...",
  "session_id": "20260719_153012_LINK-CAL-001_initial_R01",
  "workspace_id": "catr_chamber_loss_calibration_9f3a21c8",
  "config_hash": "9f3a21c8...",
  "config_name": "catr_chamber_loss_calibration",
  "config_display_name": "CATR 暗室路损校准",
  "config_source_path": "...",
  "project_code": "P2026-CATR-A",
  "calibration_stage": "initial",
  "run_label": "R01",
  "operator": "",
  "operator_note": "",
  "item_id": "LINK-CAL-001",
  "state": "DONE",
  "started_at": "2026-07-19T15:30:12+08:00",
  "finished_at": "2026-07-19T15:32:44+08:00",
  "raw_files": [],
  "loss_files": [],
  "metadata_files": []
}
```

## 单步 metadata 扩展

每个小步骤 metadata 在现有字段基础上增加：

```json
{
  "run_uid": "...",
  "workspace_id": "...",
  "workspace_root": "...",
  "session_id": "...",
  "session_root": "...",
  "config_hash": "...",
  "config_source_path": "...",
  "project_code": "...",
  "calibration_stage": "...",
  "run_label": "...",
  "operator": "...",
  "operator_note": "..."
}
```

## latest 索引

每个 project 下维护最近一次成功输出索引：

```text
projects/{project_code}/latest/{item_id}.json
```

内容示例：

```json
{
  "item_id": "LINK-CAL-001",
  "session_id": "20260719_153012_LINK-CAL-001_initial_R01",
  "state": "DONE",
  "loss_files": [],
  "updated_at": "2026-07-19T15:32:44+08:00"
}
```

规则：

- 只有 `DONE` / `RESUMED_DONE` session 更新 latest。
- `PARTIAL` / `FAILED` / `CANCELLED` 保留 session，但不覆盖 latest。
- 结果页可以提供“当前 session”和“最新成功 session”两个视图。

## 兼容策略

- 新运行默认写入 workspace 结构。
- 旧版根目录 `raw/loss/metadata` 只读展示，标记为“旧版未绑定配置输出”。
- 如需迁移旧文件，单独提供导入工具，不在正常校准流程中自动移动旧文件。

## 文件管理 TODO

- [X] FM-01 建立 `CalibrationRunContext` 模型，包含 `project_code`、`calibration_stage`、`run_label`、`operator`、`operator_note`。
- [X] FM-02 对导入链路配置计算 `config_hash`，生成稳定 `workspace_id`。
- [X] FM-03 建立 workspace/session 生成模块，负责生成 `workspace_root`、`project_root`、`session_root`。
- [X] FM-04 校准执行页增加“校准批次”区域，项目代号和校准阶段必填。
- [X] FM-05 `MockCalibrationRunner` 输出目录改为 `workspace/projects/{project_code}/sessions/{session_id}`。
- [X] FM-06 单步 metadata 增加配置、workspace、project、session、阶段、轮次、操作员和备注字段。
- [X] FM-07 每次运行生成 `session_manifest.json`，汇总 raw/loss/metadata 文件、状态、失败信息和 hash。
- [X] FM-08 成功完成后更新 `latest/{item_id}.json`；失败或取消不覆盖 latest。
- [X] FM-09 结果页增加当前 workspace、project、session 显示，并支持打开 workspace/project/session 目录。
- [X] FM-10 结果页支持切换“当前 session / 最新成功 session / 历史 session”。
- [X] FM-11 保留旧版输出目录只读兼容展示，并明确标记“未绑定配置”。
- [X] FM-12 增加单元测试：同名不同配置进入不同 workspace。
- [X] FM-13 增加单元测试：同配置不同 project/stage/run_label 进入不同 session。
- [X] FM-14 增加 GUI smoke 测试：填写批次字段后完成 Mock 校准，结果页显示对应 workspace/session。
- [X] FM-15 增加失败路径测试：FAILED/CANCELLED session 保留 manifest，但不更新 latest。
- [X] FM-16 更新用户文档，说明项目代号、阶段、轮次如何填写和如何查找历史校准文件。
- [X] FM-17 建立 exe 打包后的文件管理策略：识别 PyInstaller/源码运行模式，区分内置资源目录、用户配置目录、用户资源目录和校准输出目录；首次启动可复制默认 JSON/CSV 到用户配置目录，JSON 相对 CSV 路径优先按 JSON 所在目录解析，并以内置资源目录作为只读兜底。
- [x] FM-18 为 `session_manifest.json` 增加 `resume_source`、`substep_status`、`reused_files`、`new_files`、`invalid_files` 字段，用于记录历史导入和续测来源。
- [ ] FM-19 建立历史 session 文件索引器，能从 manifest、metadata、raw、loss 反查每个细分步骤的数据文件和校验状态。
- [ ] FM-20 建立历史数据有效性校验：校验 config_hash、item/step/substep、feed/horn/band、频率范围、点数、文件 hash 和曲线可读性。
- [x] FM-21 调整 latest 更新策略：只有 `DONE` / `RESUMED_DONE` 更新 latest，`PARTIAL` / `SKIPPED_NOT_MEASURED` / `CANCELLED` / `FAILED` 不更新 latest。
- [x] FM-22 支持在新 session 中引用历史文件而不复制文件，同时在 manifest 中明确记录引用来源；如需导出完整包，再执行显式归档。
- [ ] FM-23 支持基于已有 raw 的 final/loss 复算输出，并记录复算输入和输出 hash。（已完成复算输出；输入/输出 hash manifest 扩展待接入。）
- [ ] FM-24 在 `substep_status` 中记录曲线质量字段 `curve_quality`、异常原因 `quality_reason` 和人工强制沿用原因 `override_reason`。
