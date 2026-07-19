# CATR 路损校准历史导入与细分步骤续测方案

Status: Draft
Domain: CATR_LOSS_CALIBRATOR
Canonical: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_RESUME_PLAN.md`
Related: `CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`, `CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`, `CATR_LOSS_CALIBRATION_UI_TODO.md`
更新时间：2026-07-19

## 背景

现场校准可能不会一次完成全部细分步骤。操作员需要导入之前测了一半的结果，直接看到哪些细分步骤已有有效数据，哪些还缺失，然后点击单个细分步骤进行补测或重测。

现有 `skip` 语义不够清楚：它既可能表示“已有历史数据，所以不用测”，也可能表示“这一步不测”。这两种情况对正式结果的影响完全不同，不能混用同一个状态。

## 目标

- 支持导入 workspace/session/latest 作为续测来源。
- 每个细分步骤能独立显示数据状态、历史曲线和依赖状态。
- 每个细分步骤能基于曲线是否存在、CSV 是否可读、点数和频率轴等客观信息给出读取状态；“可沿用 / 需重测”由操作员人工判定。
- 操作员可以直接选择一个细分步骤独立测试，不必从第一步一路执行到目标步骤。
- 已有有效历史数据可以被沿用；真正未测或主动跳过的数据不能让 session 误判为正式成功。
- 只有所有必需细分步骤都有有效数据时，才能标记 `DONE` 并更新 latest。

## 状态模型

| 状态 | 含义 | 是否可计入正式完成 |
|---|---|---|
| `MISSING` | 未找到该细分步骤需要的 raw/final/metadata。 | 否 |
| `VALID_HISTORY` | 从导入 session/latest 中找到历史数据，且操作员人工判定可沿用。 | 是 |
| `VALID_CURRENT` | 本次运行新测得有效数据。 | 是 |
| `STALE_CONFIG` | 文件存在，但 config_hash、频段、馈源、喇叭或点数不匹配。 | 否 |
| `BROKEN_FILE` | 文件路径存在记录但实际文件缺失，或 hash 校验失败。 | 否 |
| `NO_CURVE` | metadata 存在，但未找到可展示的 raw/final 曲线。 | 否 |
| `SUSPECT_CURVE` | 曲线可读，但存在 NaN/Inf、点数不匹配、频率非递增等客观异常提示。 | 否，除非人工判定可沿用 |
| `REMEASURE_REQUIRED` | 依赖输入更新后，该步骤输出需要重算或重测。 | 否 |
| `SKIPPED_NOT_MEASURED` | 操作员明确标记“不测”。 | 否 |

session 建议使用以下完成状态：

| 状态 | 含义 | 是否更新 latest |
|---|---|---|
| `DONE` | 全部必需细分步骤均有效，且不依赖旧配置。 | 是 |
| `RESUMED_DONE` | 部分数据来自历史沿用，部分来自本次补测，最终完整有效。 | 是 |
| `PARTIAL` | 存在缺失、跳过不测、配置不匹配或文件损坏。 | 否 |
| `CANCELLED` | 操作员取消。 | 否 |
| `FAILED` | 执行失败。 | 否 |

## 导入与校验规则

导入历史结果时，软件应读取：

- `workspace.json`
- `config/link_config_snapshot.json`
- `session_manifest.json`
- 单步 `metadata/*.json`
- `raw/*.csv`
- `loss/*.csv`

每个细分步骤至少校验：

- `config_hash` 与当前配置一致，或明确标记为可迁移配置。
- `item_id`、`step_id`、`substep_id` 或等价 `source_step` 匹配。
- `feed`、`horn`、`band`、频率范围、点数符合当前设置。
- raw/final 文件存在。
- metadata 中记录的 hash 与文件实际 hash 一致。
- 依赖输入没有被本次重测更新为新版本。
- 曲线能被解析，频率轴单调递增，点数与设置一致。
- 曲线值不含 NaN/Inf，且未超出配置允许范围。
- 软件只提示曲线读取状态和客观可疑点；曲线业务质量由操作员结合现场经验决定是否重测。

不满足校验时，不允许自动沿用，只能重测或保持 `PARTIAL`。

## 曲线读取检查与人工质量判定

历史数据导入后，软件不应只看文件是否存在，还要显示客观读取状态。曲线是否正常由操作员人工判定：

| 判断 | 触发条件 | 默认动作 |
|---|---|---|
| `READABLE` | 文件存在，频率轴和 dB 数据可读。 | 等待人工判定 |
| `NO_CURVE` | 找不到 raw/final CSV，或 CSV 中无可绘制 dB 列。 | 重测或重新导入 |
| `BROKEN` | 文件缺失、hash 不匹配、CSV 无法解析。 | 重测或重新导入 |
| `SUSPECT` | 曲线存在但有客观可疑点，例如 NaN/Inf、频率非递增、点数不足。 | 等待人工判定 |
| `STALE` | 配置、频段、馈源、喇叭或点数与当前设置不一致。 | 重测或人工确认 |

异常阈值应先做成配置项，不在代码中写死。初期可使用保守规则：

- 频率点数与当前 sweep points 不一致，标记 `SUSPECT` 或 `STALE`，由人工决定是否沿用。
- 频率轴非递增，标记 `BROKEN`。
- dB 列存在 NaN/Inf，标记 `BROKEN`。
- 相邻点跳变超过阈值，标记 `SUSPECT`。
- 曲线标准差过低且不符合预期，标记 `SUSPECT`。
- 幅度超出配置上下限，标记 `SUSPECT`。

## 操作流程

1. 用户在校准执行页的 `校准批次` 区域后侧点击 `导入历史数据`。
2. 选择 workspace、session 或 latest。
3. 软件生成细分步骤状态表。
4. 校准执行页自动定位到第一个 `MISSING` / `STALE_CONFIG` / `REMEASURE_REQUIRED` 步骤。
5. 用户也可以手动点击任意细分步骤。
6. 右侧显示接线路径、链路命令、已有曲线、曲线质量和状态原因。
7. 用户点击 `测试当前细分步骤` 或 `重测当前细分步骤`。
8. 新 raw 写入当前 session，依赖 final/loss 失效并重算。
9. 所有必需细分步骤有效后，用户点击 `生成/更新结果`。
10. 软件将 session 标为 `DONE` 或 `RESUMED_DONE`，并更新 latest。

## 按钮语义

- `导入历史数据`：放在校准批次输入栏后面，选择 workspace/session/latest 作为续测来源；导入后刷新细分步骤状态和数据展示页签。
- `沿用历史数据`：仅当当前细分步骤为 `VALID_HISTORY` 时可用。
- `强制沿用`：仅对 `SUSPECT_CURVE` 开放，必须记录人工确认原因；不建议默认显示。
- `测试当前细分步骤`：对 `MISSING` 或 `STALE_CONFIG` 步骤进行单步测量。
- `重测当前细分步骤`：对已有数据重新采样并覆盖当前 session 中该步骤数据。
- `生成/更新结果`：基于当前有效 raw 和历史沿用 raw 计算 final/loss。
- `标记不测`：显式设置 `SKIPPED_NOT_MEASURED`，session 只能是 `PARTIAL`。

## 文件记录

`session_manifest.json` 建议新增：

```json
{
  "resume_source": {
    "workspace_root": "...",
    "session_id": "...",
    "manifest_file": "..."
  },
  "substep_status": {
    "CAL001-AUX:AUX-A": {
      "status": "VALID_HISTORY",
      "source": "history",
      "raw_files": ["..."],
      "loss_files": ["..."],
      "metadata_files": ["..."],
      "curve_quality": "OK",
      "reason": ""
    }
  },
  "reused_files": ["..."],
  "new_files": ["..."],
  "invalid_files": ["..."]
}
```

## 实施顺序

1. 建立细分步骤状态模型、曲线质量模型和历史文件索引。
2. 实现导入 session/latest 后的状态扫描。
3. UI 在校准批次后侧提供 `导入历史数据` 按钮，并显示细分步骤状态、原因、历史曲线和曲线质量。
4. 增加单个细分步骤执行入口。
5. 实现历史数据沿用与依赖失效/重算。
6. 修改 session 完成规则：含 `SKIPPED_NOT_MEASURED` 或 `MISSING` 不更新 latest。
7. 补充 Mock 回归测试和 GUI smoke。
