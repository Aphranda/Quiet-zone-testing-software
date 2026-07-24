# CATR 路损校准历史补测流程设计

## 背景

当前路损校准软件支持导入历史校准数据，并支持对单个细分步骤执行“重测当前”和“生成/更新结果”。但导入历史后，主按钮“开始校准”仍然走全量新测流程：新建 session，并从当前校准项第一个细分步骤开始执行。

这会导致现场补测缺失项时出现两个问题：

- 已测曲线和补测曲线分散在不同 session 文件中。
- 操作员容易误以为“开始校准”会基于历史数据继续补测，实际却是新开完整校准。

目标是在导入历史校准项后，将主流程切换为“开始补测”：按照正常校准确认流程执行，但只跳转到历史数据中未测、异常或人工判定需重测的细分步骤，并将补测数据写回原历史 session。

## 现场问题补充

2026-07-24 排查 `LINK-CAL-002` 历史 session 时发现：

- `loss` 目录和结果页中可以看到辅助线、回传段以及最终计算结果。
- `raw` 目录中实际存在对应原始 CSV。
- `session_manifest.json` 的 `raw_files`、`completed_substep_ids` 和 `current_retested_substep_ids` 缺少对应条目。
- `substep_status` 中对应 key 被标记为 `MISSING`。

因此导入历史数据时，界面无法识别这些细分步骤已完成。根因不是曲线被删除，而是历史索引文件与磁盘文件不一致。

这一问题需要纳入设计约束：历史导入、补测目标计算、重新计算结果都必须以 `session_manifest.json` 为主要索引，同时具备从 session 目录反查 raw/loss/metadata 文件并修复索引的能力。

## 当前行为审查

### 开始校准

入口：

- `presentation/main.py::_confirm_start_calibration`
- `presentation/viewmodels.py::CalibrationViewModel.start_selected`
- `calibration/mock_runner.py::CalibrationRunner.run`

行为：

- 创建新的 session。
- 从当前校准项第一个 step/substep 开始全量遍历。
- 每个细分步骤都执行链路箱配置、网分配置、读数、保存 raw/loss/metadata。
- 不读取 `_history_data_summary`，不会自动跳过历史已有曲线。

### 单项重测

入口：

- `presentation/main.py::_retest_selected_substep`
- `presentation/viewmodels.py::CalibrationViewModel.run_single_substep`

行为：

- 如果传入 `history_summary`，会复用历史 session 上下文。
- 只重测当前选中的一个细分步骤。
- 通过 `_write_in_place_history_manifest` 将新文件与历史文件合并写回原 session。

### 续测结果生成

入口：

- `presentation/main.py::_generate_resume_results`
- `presentation/viewmodels.py::CalibrationViewModel.generate_resume_results`

行为：

- 根据人工判断和当前已重测项加载历史 raw 文件。
- 重新计算可用输出。
- 写回历史 session manifest。
- 仅当所有必需细分步骤都有可用数据时，状态变为 `RESUMED_DONE`。

### 历史曲线识别

入口：

- `storage/workspace.py::load_session_summary_from_manifest`
- `storage/workspace.py::_summary_from_manifest`
- `presentation/main.py::_history_curve_path_for_ids`
- `presentation/main.py::_history_file_candidates`

当前行为：

- 导入 workspace/session 时读取 `session_manifest.json`。
- 细分步骤曲线查找只遍历 summary 中的 `raw_files`。
- 结果页曲线展示可以遍历 summary 中的 `loss_files`。
- 如果磁盘上存在 raw CSV，但 manifest 没有登记，历史导入仍会认为对应步骤缺失。
- 如果 manifest 登记了不存在的 CSV，导入后会在候选路径过滤阶段忽略该文件。

结论：

- `loss_files` 只能证明结果文件存在，不能证明某个测试项已完成。
- `completed_substep_ids` 和 `completed_step_ids` 应由可解析的 raw 文件反推或校验，不能长期信任陈旧 manifest。
- 补测前应执行一次轻量索引一致性检查，避免把“索引丢失”误判为“需要重新采样”。

## 目标行为

导入历史数据后：

- 主按钮显示为“开始补测”。
- 点击后不新建 session，而是在导入的历史 session 原地更新。
- 执行顺序仍按配置中的 step/substep 顺序。
- 只对需要补测的细分步骤弹出确认并执行。
- 已有且可沿用的历史细分步骤不进入确认流程。
- 补测完成后刷新曲线状态、步骤状态和结果概览。
- 如果仍有缺失项，状态保持 `PARTIAL`。
- 如果所有必需项齐全，可继续点击“生成/更新结果”完成最终汇总。

## 数据契约

### manifest 是导入入口

workspace/session 格式的历史数据以 `session_manifest.json` 为入口。导入时 summary 至少应保留：

- `session_root`
- `workspace_root`
- `item_id`
- `state`
- `raw_files`
- `loss_files`
- `metadata_files`
- `substep_status`
- `completed_substep_ids`
- `completed_step_ids`
- `current_retested_substep_ids`
- `measurement_settings`
- `resume_compatibility_warnings`

### raw 是完成状态依据

细分步骤完成状态以 raw CSV 为准：

- 期望文件名：`{item_id}_{step_id}_{substep_id_safe}.csv`。
- key 格式：`{step_id}:{substep_id}`。
- raw CSV 存在且可解析时，才能进入 `completed_substep_ids`。
- step 下所有 substep 都完成时，step 才能进入 `completed_step_ids`。

### loss 是结果展示依据

`loss_files` 用于结果页展示和导出，不直接决定补测目标。某些输出可以由多个 raw 输入计算得到，因此 loss 文件存在不等于某个 raw 测试项已完成。

### metadata 是追溯依据

`metadata_files` 用于追溯测试设置、仪表状态、异常记录。补测和重新计算时应保留历史 metadata，并将新 metadata 按文件名合并写回。

## 索引一致性检查

导入历史 session 或点击“开始补测”前，应检查 manifest 与磁盘目录是否一致。

检查规则：

- 对当前校准项枚举所有 `step/substep`。
- 根据配置生成期望 raw 文件名。
- 在 manifest `raw_files` 与 `session_root/raw` 中同时查找。
- 如果磁盘存在但 manifest 缺失，标记为 `INDEX_MISSING`。
- 如果 manifest 存在但磁盘缺失，标记为 `FILE_MISSING`。
- 如果 raw CSV 存在但无法解析，标记为 `BROKEN_FILE`。
- 如果 manifest 的 `substep_status` 与 raw 实际状态不一致，标记为 `STATUS_STALE`。

处理建议：

- `INDEX_MISSING`：自动修复 manifest，避免误触发重新采样。
- `FILE_MISSING`：保留缺失状态，纳入补测目标。
- `BROKEN_FILE`：纳入补测目标，同时保留坏文件路径和错误原因。
- `STATUS_STALE`：按 raw 实际结果重建 `substep_status`。

自动修复必须满足：

- 不删除 raw/loss/metadata 文件。
- 只补齐或替换 manifest 索引字段。
- 写入前备份 `session_manifest.json`。
- 使用 UTF-8 无 BOM 写回。
- 在 `last_event` 中记录 `manifest_repair` 或更具体事件。

## 补测目标判定

待补测集合建议使用 `step_id:substep_id` 作为 key。

需要补测：

- 历史 raw 文件不存在。
- 历史 raw 文件存在但曲线质量为 `BROKEN` 或 `NO_CURVE`。
- 操作员人工判定为 `retest`。

默认跳过：

- 历史 raw 文件存在，曲线质量为 `OK`。
- 历史 raw 文件存在，曲线质量为 `SUSPECT`，但操作员未判定重测。
- 操作员人工判定为 `accept`。
- 当前历史 session 中已经补测过且 raw 文件存在。

说明：

- `SUSPECT` 默认先保留给人工判断，避免软件自动重测可能仍可用的数据。
- 如果现场希望更严格，可后续增加设置项：可疑曲线是否自动纳入补测。

## 结果重新计算

补测完成后，raw 文件齐全并不代表最终结果已更新。需要区分两类操作：

- `开始补测`：执行缺失或需重测细分步骤，保存新的 raw/loss/metadata，并更新 manifest。
- `重新计算`：不重新采样，只读取当前 session 的 raw 和人工判定结果，重新生成所有可计算 loss 输出。

重新计算按钮应在以下条件满足时可点击：

- 当前有导入的 workspace/session 历史数据，或结果页选中了 workspace/session 历史 session。
- `state` 不是 `LEGACY_READONLY`。
- `session_root` 和 `manifest_file` 存在。

重新计算输出应包含：

- 原有辅助线、回传段、主链路和馈源链路输出。
- 去掉标准喇叭增益之后的完整链路损耗：
  - `L_VNA_H_DEEMB`
  - `L_VNA_V_DEEMB`
  - `L_VNA_H_AMP1_DEEMB`
  - `L_VNA_V_AMP1_DEEMB`
  - `L_VNA_H_AMP2_DEEMB`
  - `L_VNA_V_AMP2_DEEMB`

其中 `DEEMB` 表示从包含馈源、DUT 整个环路的主链路结果中去掉标准喇叭增益，但不去掉馈源和 DUT 回传段。

## 网分功率策略

当前自动流程在每个细分步骤执行前都会重新配置 VNA：

- 配置扫频范围。
- 配置输出功率。
- 配置 IFBW。
- 配置测量参数 S21/S12/S11/S22。
- 触发 sweep 并读取曲线。

功率来源优先级为：

1. `vna_settings.substep_power_dbm` 或 `vna_settings.vna_power_dbm_by_substep` 中匹配当前 `step/substep` 的覆盖值。
2. substep 配置中的 `vna_power_dbm`。
3. step 配置中的 `vna_power_dbm`。
4. UI 全局 `vna_power_dbm`。
5. 默认值 `DEFAULT_VNA_POWER_DBM = -30.0 dBm`。

当前默认配置中，CAL002/003/004/005 的 AUX、回传段和三工况各 substep 都已显式配置 `vna_power_dbm`。配置文件会成为每条测试链路的明确功率来源。

对于“回传段用线缆直接连接形成环路”的工况，建议明确写入配置，而不是依赖全局默认值：

- 辅助线和回传段默认保持 `-30.0 dBm`。
- 主链路三工况考虑空间损耗：直通工况使用 `0.0 dBm`，带放大器工况使用 `-20.0 dBm`。
- 如需按现场增益/衰减余量调整，在对应 step/substep 修改 `vna_power_dbm`，不需要改代码。
- 曲线界面和确认弹窗应显示当前细分步骤实际 VNA 功率。
- metadata 中应记录实际使用的 VNA 功率，便于历史导入和补测时复核。

CAL002 默认功率表：

| 工况 | 配置位置 | 默认功率 |
| --- | --- | --- |
| AUX-D 辅助线 | `CAL002-AUX-D.vna_power_dbm` | `-30.0 dBm` |
| DUT 到 VNA2 回传段 | `CAL002-DUT-VNA2.vna_power_dbm` | `-30.0 dBm` |
| DUT 经 AMP1 到 VNA2 回传段 | `CAL002-DUT-AMP1-VNA2.vna_power_dbm` | `-30.0 dBm` |
| H/V 主链路直通 | `CAL002-MAIN:H-THRU` / `V-THRU` | `0.0 dBm` |
| H/V DUT 侧 AMP1 回传 | `CAL002-MAIN:H-DUTAMP1` / `V-DUTAMP1` | `-20.0 dBm` |
| H/V 馈源侧 AMP2 | `CAL002-MAIN:H-AMP2` / `V-AMP2` | `-20.0 dBm` |

CAL003 默认功率表：

| 工况 | 配置位置 | 默认功率 |
| --- | --- | --- |
| AUX-E 辅助线 | `CAL003-AUX-E.vna_power_dbm` | `-30.0 dBm` |
| DUT 到 SA 直通 | `CAL003-DUT-SA:DUT-SA` | `-30.0 dBm` |
| DUT 经 AMP1 到 SA | `CAL003-DUT-SA:DUT-AMP1-SA` | `-30.0 dBm` |

CAL004 默认功率表：

| 工况 | 配置位置 | 默认功率 |
| --- | --- | --- |
| AUX-F 辅助线 | `CAL004-AUX-F.vna_power_dbm` | `-30.0 dBm` |
| AUX-F 回传段 | `CAL004-DUT-VNA2.vna_power_dbm` | `-30.0 dBm` |
| H/V 到 SA 直通接收 | `CAL004-SA-HV-THRU:H-SA` / `V-SA` | `0.0 dBm` |
| H/V 经 AMP2 到 SA | `CAL004-SA-HV-AMP2:H-AMP2-SA` / `V-AMP2-SA` | `-20.0 dBm` |
| H/V DUT 侧 AMP1 校验 | `CAL004-SA-HV-DUTAMP1-CHECK:H-SA-DUTAMP1-CHECK` / `V-SA-DUTAMP1-CHECK` | `-20.0 dBm` |

CAL005 默认功率表：

| 工况 | 配置位置 | 默认功率 |
| --- | --- | --- |
| AUX-G 辅助线 | `CAL005-AUX-G.vna_power_dbm` | `-30.0 dBm` |
| AUX-G 回传段 | `CAL005-DUT-VNA2.vna_power_dbm` | `-30.0 dBm` |
| H/V SG 到 DUT 直通 | `CAL005-SG:H-SG` / `V-SG` | `0.0 dBm` |
| H/V SG 到 DUT，DUT 侧 AMP1 | `CAL005-SG:H-SG-DUTAMP1` / `V-SG-DUTAMP1` | `-20.0 dBm` |
| H/V 经 AMP2 到 SG | `CAL005-SG:H-AMP2-SG` / `V-AMP2-SG` | `-20.0 dBm` |

这样后续如果直通链路损耗很大、放大链路增益很大，可以通过 JSON 配置对每条测试链路独立设定功率，避免把所有工况绑在同一个全局 VNA 输出功率上。

## 实现方案

### 1. 历史索引检查与修复

新增历史索引检查函数，建议放在 ViewModel 或 storage 层：

- 输入：当前校准项、history summary、session root。
- 输出：修正后的 summary、诊断列表、是否写回 manifest。
- 复用 `_completed_substep_ids_from_raw_files(...)` 的命名规则。
- 对 `raw_files`、`completed_substep_ids`、`completed_step_ids`、`current_retested_substep_ids`、`substep_status` 做一致化。
- 保留 `loss_files` 和 `metadata_files`，并补充磁盘上存在但 manifest 缺失的同名文件。

该函数应在两个场景调用：

- 导入历史数据成功后，刷新界面前。
- 点击“开始补测”前，计算补测目标前。

### 2. UI 按钮状态

修改 `MainWindow._sync_start_button_state`：

- 当前校准项存在。
- `_history_data_summary` 不为空。
- `history_summary.item_id` 与当前校准项一致。
- 当前不在运行中。

满足条件时：

- 按钮文本显示 `开始补测`。
- 按钮属性标记为 `resumeRetestAction=True`。
- 点击后进入补测确认流程。

清除历史数据、切换校准项或历史项不匹配时，恢复 `开始校准`。

### 3. 补测确认入口

新增 `MainWindow._confirm_resume_retest_calibration`：

- 校验已导入历史数据。
- 读取当前 VNA 设置。
- 计算待补测集合。
- 如果待补测集合为空，提示“没有需要补测的项目”。
- 弹窗展示待补测数量、历史 session、扫频设置。
- 确认后调用 `vm.start_resume_missing(...)`。

### 4. 批量补测入口

新增 `CalibrationViewModel.start_resume_missing(...)`：

输入：

- `vna_settings`
- `history_summary`
- `manual_judgments`
- `target_substep_keys`

行为：

- 校验当前无 worker 正在运行。
- 校验历史 session 可原地更新。
- 使用 `_session_context_from_history_summary(...)` 创建历史 session 上下文。
- 创建 `CalibrationRunner`，传入目标细分步骤集合。
- worker 复用现有确认机制。
- 完成时将本次 raw/loss/metadata 与历史文件合并写回 manifest。

### 5. Runner 支持目标过滤

修改 `CalibrationRunner`：

- 增加字段 `target_substep_keys: set[str] | None = None`。
- `run()` 遍历 step/substep 时，如果目标集合不为空且当前 key 不在集合内，则直接跳过，不发确认提示。
- `overview()` 中保留本次实际完成的 substep。

这样可以复用现有的：

- 开始前确认
- 保存完成确认
- retry/skip/cancel
- 链路箱和网分配置
- raw/loss/metadata 保存
- 错误处理

### 6. 原地写回历史 session

补测完成后不能直接使用 runner 自己的新 overview 作为最终历史状态，因为 runner 只知道本次补测文件。

需要调用 `_write_in_place_history_manifest(...)`：

- 合并历史 raw 文件和本次 raw 文件。
- 合并历史 loss 文件和本次 loss 文件。
- 合并历史 metadata 文件和本次 metadata 文件。
- 更新 `current_retested_substep_ids`。
- 根据合并后的 raw 文件重新计算 `completed_substep_ids` 和 `completed_step_ids`。
- 全部齐全时状态为 `RESUMED_DONE`，否则为 `PARTIAL`。

写回时还需要保留或重建：

- `substep_status`
- `reused_files`
- `new_files`
- `invalid_files`
- `resume_compatibility_warnings`
- `measurement_settings`
- `measurement_warnings`

如果写回前发现 manifest 与磁盘不一致，应先执行索引修复，再合并本次补测结果。

### 7. 补测完成后的界面刷新

worker 完成后：

- 更新 `_history_data_summary` 为合并后的 summary。
- 清空曲线质量缓存。
- 刷新校准项列表、步骤列表、细分步骤列表、结果概览。
- 仍保留人工判断记录。
- 提示本次补测完成数量，以及是否还存在缺失项。

### 8. 配置驱动的链路方向

CAL002 三工况中，不同 step/substep 的 VNA 数据方向必须来自配置：

- 测量参数使用 substep/step 的 `parameter` 字段。
- 例如需要读取 S12 时，配置中应写为 `parameter: "S12"`。
- 代码不应针对 CAL002 STEP3、STEP6 写硬编码分支。
- 曲线界面应显示当前细分步骤实际测量参数，避免 S21/S12 混淆。

这样默认配置更新后，导入默认配置即可获得正确方向；后续其他链路也可以通过 JSON 配置扩展。

## 待办拆分

1. 增加历史索引检查与 manifest 修复函数。
2. 增加历史补测目标计算函数。
3. 修改主按钮状态，在导入历史后显示“开始补测”。
4. 新增补测确认弹窗。
5. 新增 `CalibrationViewModel.start_resume_missing`。
6. 修改 `CalibrationRunner.run` 支持 `target_substep_keys`。
7. 修改 worker 完成回调，使补测完成后写回历史 manifest。
8. 刷新 UI 状态和历史曲线缓存。
9. 增加测试：
   - 导入历史时 manifest 缺 raw 索引但磁盘存在 raw，能自动修复并识别完成。
   - 导入历史后主按钮变为“开始补测”。
   - 补测只执行缺失项，不执行已有项。
   - 补测写回原 session，不新建 `_RETEST` session。
   - manifest 合并历史文件和新文件。
   - 全部必需项齐全后状态变为 `RESUMED_DONE`。
   - 重新计算后生成 `DEEMB` 输出。

## 风险点

- 如果历史 session 是旧版只读目录，应禁止批量补测，并提示先导入 workspace/session 格式数据。
- 如果历史配置与当前配置不一致，应继续给出兼容性 warning，不应静默覆盖。
- 如果操作员对 `SUSPECT` 曲线没有人工判定，默认不自动补测，避免误删可用历史数据。
- 如果补测中途取消，应保留已完成补测文件，并将 manifest 写为 `PARTIAL`。
- 如果某个细分步骤补测失败，应保留错误信息，不覆盖其它历史曲线。
- 如果 manifest 索引缺失但 raw 文件存在，不能直接判为未测；应先提示或自动修复索引。
- 如果结果页存在 loss 文件但 raw 文件缺失，不能判为已完成；应提示结果可查看但不能作为补测完成依据。
- 如果配置中测量方向改变，历史 raw 的参数名和当前配置不一致，应记录 compatibility warning。

## 建议交互文案

导入历史后的按钮：

- `开始补测`

补测确认弹窗：

```text
确认开始补测 CAL002 - 三工况校准？

历史 Session: 20260723_164538_LINK-CAL-002_initial_R01
待补测细分步骤: 4 项

网分扫频: 10.000 GHz 到 17.000 GHz，71 点。
补测数据将写回导入的历史 session，不会新建校准 session。
```

无待补测项：

```text
当前历史数据没有需要补测的细分步骤。

如需重新测量某一项，请在曲线界面将其人工判定为“异常需重测”，再点击开始补测。
```

补测完成：

```text
补测完成。

本次补测: 4 项
当前完成: 9/9 项

可以点击“生成/更新结果”重新汇总最终曲线。
```

索引修复完成：

```text
已修复历史 session 索引。

从 raw 目录找回: 2 项
当前完成: 9/9 项

曲线文件未被移动或删除。
```

索引不一致但不能自动修复：

```text
历史 session 索引与磁盘文件不一致。

manifest 中登记的部分 raw 文件不存在，已将这些细分步骤纳入补测。
请确认历史目录是否完整。
```
