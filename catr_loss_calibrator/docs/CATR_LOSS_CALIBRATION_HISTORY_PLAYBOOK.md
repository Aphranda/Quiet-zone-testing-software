# CATR 路损校准历史文件查找手册

Status: Active  
Domain: STORAGE  
Canonical: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_HISTORY_PLAYBOOK.md`  
Related: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_LINK_CONFIG_JSON.md`  
Last updated: 2026-07-19

本文面向现场操作人员，说明如何填写校准批次字段、如何找到新 workspace 输出、以及软件关闭后如何重新打开历史校准数据。

## 1. 校准批次字段怎么填

校准执行页需要用三个字段把一次校准运行唯一地区分出来。

| 字段 | 建议填写 | 作用 |
|---|---|---|
| 项目代号 | `P2026-CATR-A`、`客户A-整机01`、`ANT-ARRAY-02` | 区分同一链路配置下的不同项目、样机或任务。 |
| 校准阶段 | 界面中文选项，例如“初始校准”“复测”“维修后”“变更后”“交付前”“问题排查” | 区分同一项目在不同阶段产生的校准结果。 |
| 批次/轮次 | `R01`、`R02`、`换线后`、`低温前` | 区分同一项目同一阶段内的多次运行。 |

推荐规则：

- 项目代号尽量稳定，同一项目后续复测继续使用同一个项目代号。
- 校准阶段用于表达为什么重新校准。
- 批次/轮次用于表达第几次或现场条件变化。
- 文件名允许中文，但长期归档建议使用短码或中英文混合，避免跨电脑路径兼容问题。

## 2. 新版输出目录在哪里

新版校准文件不再直接混放在旧的 `raw/loss/metadata` 根目录，而是按链路配置和项目分空间保存：

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
```

关键含义：

| 名称 | 含义 |
|---|---|
| `workspace_id` | 由链路配置 JSON 内容计算出来。不同链路配置进入不同 workspace。 |
| `workspace.json` | workspace 清单，记录配置 hash、配置来源和配置快照路径。 |
| `config/link_config_snapshot.json` | 校准时保存的链路配置快照。新生成的 workspace 可用它自动恢复配置。 |
| `project_code` | 校准界面填写的项目代号。 |
| `session_id` | 一次校准运行的目录名，包含时间、校准项、阶段和轮次。 |
| `session_manifest.json` | 本次运行的总清单，记录状态、配置、项目、阶段、轮次和生成文件。 |
| `latest/{item_id}.json` | 当前项目下某个校准项最近一次成功完成的索引。失败或取消不会覆盖 latest。 |

## 3. 结果页视图怎么选

结果页的“结果视图”用于决定当前表格、摘要和曲线显示哪一组文件。

| 视图 | 适用场景 | 数据来源 |
|---|---|---|
| 当前Session | 刚完成一次校准后立即查看 | 当前软件内存中的本次运行结果 |
| 最新成功 | 查看当前项目、当前校准项最近一次成功结果 | `projects/{project_code}/latest/{item_id}.json` |
| 历史Session | 软件关闭后重新打开，或想查看更早的某一次运行 | `projects/{project_code}/sessions/*/session_manifest.json` |
| 旧版目录 | 查看旧版 `raw/loss/metadata` 输出 | 旧版输出目录，只读展示，不绑定配置 |

注意：

- “最新成功”和“历史Session”依赖当前加载的链路配置与当前项目代号。
- 如果项目代号填错，历史列表可能为空。
- 旧版目录没有 `workspace_id`、`project_code`、`session_id` 绑定，结果页会标记为 `LEGACY_READONLY` 和“未绑定配置”。

## 4. 重新打开软件后查看历史 session

按下面顺序操作：

1. 打开软件。
2. 切到结果页。
3. 在“校准工作空间”文本框填写或点击“浏览Workspace”选择 workspace 目录。
4. 点击“加载历史”。

新版 workspace 如果包含 `config/link_config_snapshot.json`，软件会自动导入该链路配置。旧 workspace 没有配置快照时，结果页仍会扫描所有项目的 `session_manifest.json`，用于独立预览文件和曲线。

如需按当前配置继续校准，仍建议确认或手动导入正确的链路配置。

## 5. 按项目和 session 查看历史数据

常规查看顺序：

1. 打开软件。
2. 加载 workspace，或手动加载和历史数据对应的链路配置 JSON。
3. 如需按项目过滤，确认校准执行页的项目代号。
4. 切到结果页。
5. “校准工作空间”文本框填写或浏览选择：

```text
catr_loss_calibrator_output/workspaces/{workspace_id}
```

6. 点击“加载历史”。
7. “结果视图”选择“历史Session”。
8. 在历史 session 下拉框选择要查看的记录。
9. 文件表选择 CSV 后，可在曲线区域预览；需要重新适应坐标时点击“自适应”。

如果只想看最近一次成功结果，可以在第 7 步选择“最新成功”。

## 6. 查看旧版输出目录

旧版输出目录可以填写根目录，也可以填写其中一个子目录：

```text
catr_loss_calibrator_output
catr_loss_calibrator_output/metadata
catr_loss_calibrator_output/raw
catr_loss_calibrator_output/loss
```

然后点击“加载历史”。软件会自动识别旧版结构，并切换到“旧版目录”视图。

旧版目录规则：

- 只读展示，不会迁移或改写旧文件。
- 优先按当前校准项过滤相关文件。
- 没有配置绑定时，结果页显示“未绑定配置”。
- 新校准运行仍写入新版 workspace，不再写回旧版目录。

## 7. 常见问题

| 现象 | 优先检查 |
|---|---|
| 历史Session 下拉框为空 | workspace 路径是否选到 `{workspace_id}` 目录；旧数据是否有 `session_manifest.json`。 |
| 最新成功为空 | 当前项目和校准项是否有成功完成的 session；失败或取消不会更新 latest。 |
| 曲线没有显示 | 文件表中是否选中了可预览的 CSV；CSV 是否包含频率和数值列。 |
| 旧版目录显示未绑定配置 | 这是预期行为，旧版输出没有 workspace/session 元数据。 |
| 找不到某次校准 | 到 `projects/{project_code}/sessions/` 按时间查看目录，并检查 `session_manifest.json` 的 `state`。 |

## 8. 现场归档建议

- 每个项目开始前确认项目代号，后续复测保持一致。
- 每次改变接线、馈源、喇叭、放大器或频段配置后，使用新的校准阶段或轮次。
- 对外交付或阶段冻结时，整体备份对应的 `workspace` 或 `projects/{project_code}` 目录。
- 不建议手工改名 `session_id` 目录；如需备注现场条件，优先体现在批次/轮次字段中。
