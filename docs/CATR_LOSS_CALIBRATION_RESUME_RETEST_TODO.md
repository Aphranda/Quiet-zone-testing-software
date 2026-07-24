# CATR 路损校准历史补测模式 TODO

关联设计文档：

- `docs/CATR_LOSS_CALIBRATION_RESUME_RETEST_DESIGN.md`

## 目标

导入历史校准项后，主按钮从“开始校准”切换为“开始补测”。补测时沿用正常逐步骤确认流程，但只执行历史中缺失、损坏或人工判定需重测的细分步骤，并将补测数据写回原历史 session。

## 待办清单

### 0. 历史索引检查与修复

- [ ] 新增历史索引一致性检查函数。
- [ ] 输入当前校准项、history summary、session root。
- [ ] 按 `{item_id}_{step_id}_{substep_id_safe}.csv` 生成期望 raw 文件名。
- [ ] 检查 manifest `raw_files` 与 `session_root/raw` 是否一致。
- [ ] 磁盘存在但 manifest 缺失时标记 `INDEX_MISSING`。
- [ ] manifest 存在但磁盘缺失时标记 `FILE_MISSING`。
- [ ] raw CSV 无法解析时标记 `BROKEN_FILE`。
- [ ] `substep_status` 与 raw 实际状态不一致时标记 `STATUS_STALE`。
- [ ] 对 `INDEX_MISSING` 自动补齐 `raw_files`。
- [ ] 对 `INDEX_MISSING` 自动补齐 `completed_substep_ids`。
- [ ] 对 `INDEX_MISSING` 自动重算 `completed_step_ids`。
- [ ] 对 `INDEX_MISSING` 自动修复 `substep_status`。
- [ ] 写回 manifest 前创建备份。
- [ ] 写回 manifest 使用 UTF-8 无 BOM。
- [ ] 导入历史成功后执行一次索引检查。
- [ ] 点击 `开始补测` 前再执行一次索引检查。

### 1. 补测目标计算

- [ ] 在 ViewModel 或 MainWindow 中新增补测目标计算函数。
- [ ] 输入当前校准项、历史 summary、人工判断记录。
- [ ] 输出 `step_id:substep_id` 集合。
- [ ] raw 文件不存在时纳入补测。
- [ ] manifest 索引缺失但磁盘 raw 存在时，先修复索引，不纳入补测。
- [ ] 曲线质量为 `BROKEN` 或 `NO_CURVE` 时纳入补测。
- [ ] 人工判定为 `retest` 时纳入补测。
- [ ] 人工判定为 `accept` 时跳过。
- [ ] 曲线质量为 `OK` 时默认跳过。
- [ ] 曲线质量为 `SUSPECT` 且无人工重测判定时默认跳过。

### 2. 主按钮状态切换

- [ ] 修改 `MainWindow._sync_start_button_state`。
- [ ] 导入历史且历史 `item_id` 与当前校准项一致时，按钮显示 `开始补测`。
- [ ] 设置按钮属性 `resumeRetestAction=True`。
- [ ] 未导入历史、历史不匹配、切换校准项后恢复 `开始校准`。
- [ ] 运行中仍显示 `校准中` 并禁用按钮。
- [ ] 普通已完成/失败状态仍保留 `重新校准` 行为。

### 3. 补测确认入口

- [ ] 修改 `MainWindow._confirm_start_button`，根据按钮属性分流。
- [ ] 新增 `MainWindow._confirm_resume_retest_calibration`。
- [ ] 校验历史数据存在且可原地更新。
- [ ] 读取当前 VNA 设置。
- [ ] 计算待补测集合。
- [ ] 待补测集合为空时弹窗提示“没有需要补测的项目”。
- [ ] 确认弹窗展示历史 session、待补测数量、扫频设置。
- [ ] 确认后调用 ViewModel 批量补测入口。

### 4. ViewModel 批量补测入口

- [ ] 新增 `CalibrationViewModel.start_resume_missing(...)`。
- [ ] 参数包含 `vna_settings`、`history_summary`、`manual_judgments`、`target_substep_keys`。
- [ ] 校验当前没有 worker 正在运行。
- [ ] 校验当前校准项存在。
- [ ] 使用 `_session_context_from_history_summary(...)` 复用历史 session。
- [ ] 创建 `CalibrationRunner` 并传入 `target_substep_keys`。
- [ ] 复用现有 `CalibrationRunWorker`。
- [ ] worker 完成后合并历史 manifest。

### 5. Runner 目标过滤

- [ ] 给 `CalibrationRunner` 增加 `target_substep_keys: set[str] | None`。
- [ ] `run()` 遍历 step/substep 时判断当前 key。
- [ ] 如果目标集合存在且当前 key 不在集合内，直接跳过，不弹确认。
- [ ] 目标集合为空时应直接完成或由上层阻止启动。
- [ ] 保持现有 confirm/retry/skip/cancel 行为不变。
- [ ] 保持现有链路箱、网分、raw、loss、metadata 保存流程不变。

### 6. 原地写回历史 session

- [ ] 补测完成后调用 `_write_in_place_history_manifest(...)`。
- [ ] 合并历史 raw 文件和本次 raw 文件。
- [ ] 合并历史 loss 文件和本次 loss 文件。
- [ ] 合并历史 metadata 文件和本次 metadata 文件。
- [ ] 保留历史 `loss_files`，并合并本次重新计算生成的 loss 文件。
- [ ] 保留或重建 `substep_status`。
- [ ] 保留 `reused_files`、`new_files`、`invalid_files`。
- [ ] 更新 `current_retested_substep_ids`。
- [ ] 重新计算 `completed_substep_ids`。
- [ ] 重新计算 `completed_step_ids`。
- [ ] 所有必需项齐全时状态为 `RESUMED_DONE`。
- [ ] 仍有缺失项时状态为 `PARTIAL`。
- [ ] 不创建 `_RETEST` 或新的普通校准 session。

### 7. UI 刷新与提示

- [ ] 补测完成后更新 `_history_data_summary`。
- [ ] 清空 `_curve_quality_cache`。
- [ ] 刷新校准项列表。
- [ ] 刷新步骤列表。
- [ ] 刷新细分步骤列表。
- [ ] 刷新结果概览。
- [ ] 当前选中细分步骤有曲线时刷新曲线预览。
- [ ] 弹窗提示本次补测数量和当前完成数量。
- [ ] 全部齐全时提示可点击 `生成/更新结果`。

### 8. 异常与边界

- [ ] 旧版只读历史目录禁止补测，提示导入 workspace/session 格式数据。
- [ ] 历史 item 与当前 item 不匹配时禁止补测。
- [ ] 历史 session 路径不存在时禁止补测。
- [ ] 补测中途取消时保留已测数据，并写回 `PARTIAL`。
- [ ] 单个细分步骤失败时保留错误状态，避免覆盖其它历史数据。
- [ ] 配置 hash 或扫频参数不一致时保留 compatibility warning。
- [ ] 结果页存在 loss 文件但 raw 缺失时，不将该细分步骤判为已完成。
- [ ] manifest 与磁盘不一致时，在历史导入状态或 tooltip 中提示修复/缺失情况。
- [ ] 历史 raw 参数名与当前配置测量方向不一致时，记录 compatibility warning。

### 8.1 VNA 功率策略

- [ ] 确认默认 UI 全局 VNA 功率为 `-30.0 dBm`。
- [ ] 在确认弹窗中显示当前细分步骤实际 VNA 功率。
- [ ] 在曲线界面中显示当前细分步骤实际 VNA 功率。
- [ ] 在 metadata 中记录当前细分步骤实际 VNA 功率。
- [x] 支持通过 JSON step/substep `vna_power_dbm` 配置回传段、直通段、放大链路不同功率。
- [ ] 支持通过 `vna_settings.substep_power_dbm` 或 `vna_power_dbm_by_substep` 临时覆盖单个细分步骤功率。
- [x] 默认 JSON 中 CAL002 各 VNA 工况显式配置功率。
- [x] CAL002 辅助线和回传段显式配置 `-30.0 dBm`。
- [x] CAL002 主链路直通工况显式配置 `0.0 dBm`。
- [x] CAL002 主链路带放大器工况显式配置 `-20.0 dBm`。
- [x] CAL003 辅助线和 DUT 到 SA 工况显式配置 `-30.0 dBm`。
- [x] CAL004 辅助线和回传段显式配置 `-30.0 dBm`。
- [x] CAL004 SA-H/V 空间直通工况显式配置 `0.0 dBm`。
- [x] CAL004 SA-H/V 带放大器工况显式配置 `-20.0 dBm`。
- [x] CAL005 辅助线和回传段显式配置 `-30.0 dBm`。
- [x] CAL005 SG 空间直通工况显式配置 `0.0 dBm`。
- [x] CAL005 SG 带放大器工况显式配置 `-20.0 dBm`。
- [ ] 测试 `CAL002-DUT-VNA2` 显式配置 `-30.0 dBm`。
- [ ] 测试 step/substep 配置覆盖时优先于 UI 全局功率。

### 9. 测试

- [ ] 历史索引修复：磁盘 raw 存在但 manifest `raw_files` 缺失时自动补齐。
- [ ] 历史索引修复：`completed_substep_ids` 跟随 raw 文件重建。
- [ ] 历史索引修复：`substep_status` 从 `MISSING` 修复为 `VALID_CURRENT` 或 `VALID_HISTORY`。
- [ ] 历史索引修复：manifest 写回前生成备份。
- [ ] 补测目标计算：缺失 raw 会被纳入补测。
- [ ] 补测目标计算：仅 loss 文件存在但 raw 不存在时仍纳入补测。
- [ ] 补测目标计算：`BROKEN` / `NO_CURVE` 会被纳入补测。
- [ ] 补测目标计算：人工 `retest` 会被纳入补测。
- [ ] 补测目标计算：人工 `accept` 会被跳过。
- [ ] 导入历史后主按钮显示 `开始补测`。
- [ ] 补测只执行目标小步骤，不执行已有项。
- [ ] 补测写回原 session。
- [ ] 补测不创建 `_RETEST` session。
- [ ] manifest 合并历史文件与本次补测文件。
- [ ] 全部必需项齐全后状态变为 `RESUMED_DONE`。
- [ ] 仍有缺失项时状态保持 `PARTIAL`。
- [ ] 重新计算结果：补测完成后重新生成最终 loss 输出。
- [ ] 重新计算结果：生成 `L_VNA_H_DEEMB` / `L_VNA_V_DEEMB`。
- [ ] 重新计算结果：生成 `L_VNA_H_AMP1_DEEMB` / `L_VNA_V_AMP1_DEEMB`。
- [ ] 重新计算结果：生成 `L_VNA_H_AMP2_DEEMB` / `L_VNA_V_AMP2_DEEMB`。
- [ ] 配置驱动方向：substep `parameter=S12` 时读取 S12，不硬编码 CAL002 step。
- [ ] 配置驱动功率：step/substep `vna_power_dbm` 时自动流程使用该功率。

## 建议实现顺序

1. 先实现历史索引一致性检查与 manifest 修复。
2. 再实现补测目标计算，确保不会把索引缺失误判为需要重测。
3. 实现 `CalibrationRunner.target_substep_keys`。
4. 实现 ViewModel 的批量补测入口和 manifest 原地合并。
5. 接入 MainWindow 按钮状态和确认弹窗。
6. 补齐重新计算结果输出和 `DEEMB` 验证。
7. 最后补 UI 刷新、提示文案和测试。

## 验收标准

- 导入历史 session 后，如果 manifest 漏记但 raw 文件存在，软件能识别并修复索引。
- 导入历史 session 后，主按钮显示 `开始补测`。
- 点击 `开始补测` 后，只跳转到缺失或需重测的小步骤。
- 已有历史曲线不会再次弹确认。
- 补测数据写入导入的历史 session。
- 原历史 raw/loss/metadata 不丢失。
- 补测完成后曲线界面能看到新测曲线。
- 结果页仍能查看同一个 session 中的历史曲线和补测曲线。
- 全部项目齐全后，可以通过 `生成/更新结果` 汇总最终结果。
- 重新计算后，结果中包含去掉标准喇叭增益的完整链路损耗 `DEEMB` 输出。
