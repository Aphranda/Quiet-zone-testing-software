# CATR 暗室校准测试方案待办与历史操作

更新时间：2026-07-18

适用范围：

- 主报告：`docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`
- Markdown 源文档：`docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.md`
- 用户备份 HTML：`docs/CATR暗室校准测试方案BACKUP USER.html`

本文只记录围绕当前 CATR 暗室校准测试方案文档的历史操作和后续待办，不包含软件代码、网分控制、扫描架控制等其他开发事项。

## 1. 当前状态

- 报告名称已定为：`CATR暗室校准测试方案`。
- HTML 报告当前为 25 页。
- 已删除原“整机发射/接收与 SA/SG 校准”重复总结页。
- 已将“实际路损文件命名规则”拆成两页：
  - P23：实际路损文件命名规则、馈源/喇叭短码、有效频段交集。
  - P24：路损文件示例与 CSV 字段定义。
- 主 HTML 已同步到用户备份 HTML。
- 已临时生成截图检查辅助文件：
  - `docs/temp/CATR_PAGE_PREVIEW.png`
  - `docs/temp/CATR_PAGE_CHECK_P23_P25.html`
  - `docs/temp/CATR_page_23.png` / `CATR_page_24.png` / `CATR_page_25.png`
  - `docs/temp/CATR_p23_rough.png` / `CATR_p24_rough.png` / `CATR_p25_rough.png`

## 2. 历史操作汇总

### 2.1 文件命名与报告结构

- 将报告英文文件名整理为：
  - `docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`
  - `docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.md`
- 报告内部标题使用中文：`CATR暗室校准测试方案`。
- 将“LCD”表述统一改为“链路箱”，避免和链路箱实际物理对象混淆。
- 将暗室整体链路图放在链路箱实际链路图上方。
- 将“原始链路图”表述改为“链路箱实际链路图”。
- 增加 `resource/暗室整体链路.png` 和 `resource/原始链路图.png` 对应的报告页面。

### 2.2 校准项目结构调整

- 将校准操作拆分为：
  - `LINK-CAL-001`：暗室内部链路校准。
  - `LINK-CAL-002`：VNA 链路损耗校准。
  - `LINK-CAL-003`：SA 校准。
  - `LINK-CAL-004`：SG 校准。
- 将 `LINK-CAL-002` 与 `LINK-CAL-003` 按类似格式拆成“端口连接图”和“参数计算与输出归类”页面。
- 将 SA 校准与 SG 校准分开：
  - `LINK-CAL-003` 为 SA 校准。
  - `LINK-CAL-004` 为 SG 校准。
- 删除 `LINK-CAL-002` 中不再需要的“主链路外部接线规则”选项卡。
- 删除 `LINK-CAL-003` 中“接到暗室接口板”的临时校准部分，改为 AUX-E 接转台 DUT 接口。
- 将 `LINK-CAL-004` 按 `LINK-CAL-003` 格式拆成两页。
- `LINK-CAL-004` 使用 AUX-F 重复测回传段，便于自动化流程与上游校准保持一致。

### 2.3 LINK-CAL-001 暗室内部链路校准

- 增加“暗室内部链路校准”作为第一个校准项。
- 使用三根 3M 辅助线：
  - AUX-A
  - AUX-B
  - AUX-C
- 三根辅助线先独立测试。
- 步骤中明确辅助线 A/B/C 的使用关系：
  - DUT-H：AUX-A + AUX-C。
  - DUT-V：AUX-B + AUX-C。
  - DUT 内部段：AUX-A + AUX-C。
- 将“暗室内部 DUT 端口”改为更明确的“转台DUT接口”。
- 细化 `LINK-CAL-001`：H/V 闭合测量包含：
  - 馈源
  - 反射面
  - 标准增益喇叭
- 对应公式已改为：
  - `L_CH_INT_H = S21_CH_INT_H_RAW + L_AUX_A + L_AUX_C - G_STD_HORN_H`
  - `L_CH_INT_V = S21_CH_INT_V_RAW + L_AUX_B + L_AUX_C - G_STD_HORN_V`
  - `L_CH_INT_DUT = S21_CH_INT_DUT_RAW + L_AUX_A + L_AUX_C`
  - `L_CH_INT_FEED_H/V = L_CH_INT_H/V - L_CH_INT_DUT`

### 2.4 LINK-CAL-002 VNA 链路损耗校准

- 明确 VNA 主链路覆盖三种情况：
  1. 两边都是直通。
  2. AMP1 开启，馈源侧直通。
  3. AMP2 开启，DUT 侧直通。
- AUX-D 用于校准转台 DUT 到 VNA2 回传段。
- `L_DUT_VNA`、`L_DUT_VNA_AMP1` 被定义为关键参数。
- 最终输出参数顺序调整为：先 DUT 侧，再 FEED 侧。
- `LINK-CAL-002` 的选项卡顺序调整为与 `LINK-CAL-003` 一致。

### 2.5 LINK-CAL-003 SA 校准

- 增加指令 `CONFigure:LINK DUT,SA` 后，SA 校准支持 DUT 到 SA 直通。
- `VNA1 -> SA` 校准按三种情况定义：
  1. 两边直通。
  2. AMP1 开启，馈源侧直通。
  3. AMP2 开启，DUT 侧直通。
- H/V 合并在同一页描述。
- `LINK-CAL-003` 改为参考 `LINK-CAL-002` 方式：
  - AUX-E 接网分 PORT1 和转台 DUT 接口。
  - 接收侧切到 DUT->SA 或 DUT->AMP1->SA。
- 明确 `L_DUT_SA`、`L_DUT_SA_AMP1` 为主输出。
- VNA1 到 SA 三种工况仅作为一致性校验，不再作为主计算来源。

### 2.6 LINK-CAL-005 SG 校准

- SG 校准分三种情况：
  1. 两边直通。
  2. AMP1 开启，发射侧直通。
  3. AMP2 开启，DUT 侧直通。
- 回传路径使用 AUX-F 重复测一遍：
  - `L_DUT_VNA_F`
  - `L_DUT_VNA_F_AMP1`
- 最终输出：
  - `L_SG_DUT_H/V`
  - `L_SG_DUT_H/V_AMP1`
  - `L_SG_DUT_H/V_AMP2`

### 2.7 测试项操作页

- 增加并细化测试项：
  - `LINK-TXR-001`：DUT 通道校准。
  - `LINK-TXR-002`：方向图测试。
  - `LINK-TXR-003`：有源增益测试。
  - `LINK-TXR-004`：天线板 EIRP 测试。
  - `LINK-GT-001`：G/T 测试。
  - `LINK-SYS-001`：整机发射测试。
  - `LINK-SYS-002`：整机接收测试。
- `LINK-TXR-*` 均使用 VNA1 到 VNA2 直通链路：
  - `CONFigure:LINK DUT, VNA2`
  - `CONFigure:LINK H/V, VNA1`
- `LINK-GT-001`：
  - SG 直通发射。
  - SA 经 AMP1 放大接收。
  - 不允许 AMP2。
- `LINK-SYS-001`：
  - DUT 直接发射给到馈源。
  - SA-H/V 接收链路。
  - SA 接收默认直通，可选 AMP2。
- `LINK-SYS-002`：
  - SG 通过馈源直通路径发射。
  - DUT 终端接收。
  - SA 不开通。

### 2.8 带符号路损和标准喇叭去嵌

- 明确最终路损文件保存带符号值。
- 无源链路通常为负值。
- 含放大器链路可能为正值。
- 标准喇叭增益为正数，去嵌使用减号：
  - 例：`S21_RAW=-80 dB`，`G_STD_HORN=+20 dBi`，最终链路损耗为 `-80 - 20 = -100 dB`。
- 删除不应存在的 `AUX_CORR` 概念。
- 辅助线原始实测量记为 `S21_AUX_*`，通常为负值；`L_AUX_*` 直接按带符号原始文件保存，即 `L_AUX_* = S21_AUX_*`，公式中直接使用 `+ L_AUX_*`。

### 2.9 参数命名和文件命名规则

- 参数命名强调输入输出端口，避免 H/V、DUT、SA/SG 端口含义混淆。
- 增加实际路损文件命名规则：

```text
{PARAM}_{BAND}_{FEED}_{HORN}.csv
```

- 当前馈源：
  - `F10_17G`：10–17 GHz。
  - `F17_31G`：17–31 GHz。
- 当前标准喇叭：
  - `H10_15G`：10–15 GHz。
  - `H14P5_22G`：14.5–22 GHz。
  - `H21P7_33G`：21.7–33 GHz。
- 明确 `BAND` 必须取馈源与喇叭的有效频段交集：
  - `F10_17G + H10_15G -> 10_15G`
  - `F10_17G + H14P5_22G -> 14P5_17G`
  - `F17_31G + H14P5_22G -> 17_22G`
  - `F17_31G + H21P7_33G -> 21P7_31G`

### 2.10 HTML 逻辑评审修复

- 记录并修复 HTML 评审中发现的链路/参数冲突：
  - `LINK-TXR-001` 至 `LINK-TXR-004` 不再直接引用 `L_VNA_H/V` 闭合临时量，改为使用 `L_VNA_FEED_H/V` 与 `L_DUT_VNA` 的组合。
  - `LINK-CAL-003` 增加整机发射 SA 接收侧修正参数 `L_SYS_TX_SA_H/V` 与 `L_SYS_TX_SA_H/V_AMP2`，避免 `LINK-SYS-001` 误用 `L_DUT_SA`。
  - `LINK-SYS-001` 链路箱指令只开通 `H/V, SA` 或 `H/V, AMP2, SA`，不再同时下发 `DUT, SA`。
  - 实际路损文件命名规则限定 `PARAM` 使用最终输出参数；原始 `S21_*`、临时 `T_*` 和闭合临时量只作为追溯数据保存。
  - 统一 P7 关键链路箱指令速览中的 `CONFigure:LINK ...` 表述。

## 3. 当前待办事项

### P0：内容正确性

- [ ] 复核 `LINK-CAL-001` 中“暗室接口板 H/V -> 馈源 -> 反射面 -> 标准增益喇叭 -> 暗室接口板 DUT”的物理描述是否与实际暗室接线完全一致。
- [ ] 确认 `L_CH_INT_FEED_H/V = L_CH_INT_H/V - L_CH_INT_DUT` 是否作为最终“馈源/反射面到 DUT 参考面”参数使用。
- [ ] 确认 `LINK-CAL-003` 中 `L_DUT_SA` / `L_DUT_SA_AMP1` 仅用于 DUT 到 SA 类链路；整机发射 SA 接收侧已改用 `L_SYS_TX_SA_H/V` / `L_SYS_TX_SA_H/V_AMP2`。
- [x] 修复 `LINK-TXR-*` 页面误用 `L_VNA_H/V` 闭合临时量的问题，改为引用最终输出参数组合。
- [x] 修复 `LINK-SYS-001` 页面误用 `L_DUT_SA` 作为 H/V 到 SA 接收链路修正量的问题。
- [x] 修复 `LINK-SYS-001` 中 `DUT,SA` 与 `H/V,SA` 同时下发导致的链路含义冲突。
- [ ] 确认 `LINK-CAL-004` 中 AUX-F 重复测回传段是否作为强制步骤。
- [ ] 确认所有经过标准增益喇叭的闭合测量均已在 LINK-CAL 内完成 `- G_STD_HORN_H/V`，测试项页面不再二次扣除。

### P1：版面与分页

- [ ] 按模板要求继续做 Edge headless 截图检查，确认页眉、页脚、表格和长文件名未压到页脚。
- [ ] 截图检查操作参考 `REPORT_SCREENSHOT_CHECK_PLAYBOOK.md`。
- [ ] 检查 P23/P24 拆页后的最终视觉效果。
- [ ] 删除或归档临时截图检查文件：
  - `docs/temp/CATR_PAGE_PREVIEW.png`
  - `docs/temp/CATR_PAGE_CHECK_P23_P25.html`
  - `docs/temp/CATR_page_23.png`
  - `docs/temp/CATR_page_24.png`
  - `docs/temp/CATR_page_25.png`
  - `docs/temp/CATR_p23_rough.png`
  - `docs/temp/CATR_p24_rough.png`
  - `docs/temp/CATR_p25_rough.png`
- [ ] 检查所有页码与页面注释是否一致。
- [ ] 如后续继续删页或加页，需要同步 HTML 页脚页码、注释和备份文件。

### P2：命名与数据结构

- [ ] 决定跨喇叭重叠频段的默认优先级：
  - 14.5–15 GHz。
  - 21.7–22 GHz。
- [ ] 决定实际路损文件是否按“频段交集”拆分成多个文件，还是保存宽频文件并在软件中筛选频段。
- [ ] 确认 `NOHORN` 参数的 `BAND` 是否允许使用完整馈源频段，例如 `10_17G` / `17_31G`。
- [ ] 定义 CSV 文件是否必须包含：
  - `freq_hz`
  - `value_db`
  - `param`
  - `band`
  - `feed`
  - `horn`
  - `source_cal`
- [ ] 明确是否需要保存原始 `S21_*` 文件与最终 `L_*` 文件之间的追溯关系。

### P3：自动化落地

- [ ] 将报告中的 `LINK-CAL-*`、`LINK-TXR-*`、`LINK-GT-*`、`LINK-SYS-*` 转为结构化测试项定义。
- [ ] 每个测试项定义应至少包含：
  - `id`
  - `name`
  - `template`
  - `commands[]`
  - `required_loss_params[]`
  - `forbidden_commands[]`
  - `manual_checks[]`
- [ ] UI 中建议显示“当前测试项需要读取的路损文件/参数”。
- [ ] 校准 UI 中建议显示“本次校准将生成的最终参数”和“临时/追溯参数”。
- [ ] 自动化流程中决定 VNA1 到 SA 三工况一致性校验是否强制执行。

### P4：独立自动化校准软件开发

目标不是在当前静区测试软件中简单新增一个模块，而是重新开发一套面向 CATR 暗室校准的独立软件。当前项目代码可作为参考资产：仪表连接、VNA 控制、链路箱命令、采集流程、文件保存和测试覆盖方式均可借鉴，但新软件应拥有独立的工程结构、配置体系、校准业务模型和 UI 流程。

核心约束：新软件必须避免与当前静区测试软件耦合。不得依赖静区测试软件的主窗口、扫描流程、全局服务对象、运行时状态或配置文件格式；如需复用代码，只能复用经过隔离的底层硬件通信适配器、协议定义、公式/文件命名工具或测试样例，并应在新软件仓库内建立独立测试。

#### P4-01 当前项目可参考资产

- [ ] 参考当前项目的仪表连接与 controller 创建能力：
  - `src/quiet_zone_tester/domains/instrument_management/`
  - `src/quiet_zone_tester/domains/instrument_management/controller_factory.py`
  - `src/quiet_zone_tester/domains/instrument_management/connection_service.py`
  - `src/quiet_zone_tester/shared/instrument_defaults.py`
- [ ] 参考当前项目的 VNA 控制与采集能力：
  - `src/quiet_zone_tester/hardware/vna/scpi.py`
  - `src/quiet_zone_tester/hardware/transport/visa_scpi.py`
  - `src/quiet_zone_tester/domains/acquisition/acquisition_service.py`
  - `src/quiet_zone_tester/ui/widgets/vna_control_panel.py`
- [ ] 参考当前项目的链路箱控制能力：
  - `src/quiet_zone_tester/domains/link_management/link_service.py`
  - `src/quiet_zone_tester/domains/link_management/link_router.py`
  - `src/quiet_zone_tester/domains/link_management/switch_box_profiles.py`
  - `src/quiet_zone_tester/ui/widgets/switch_box_control_panel.py`
  - `resource/LCD74000F.md`
- [ ] 参考当前项目的数据保存基础：
  - `src/quiet_zone_tester/domains/data_management/trace_storage.py`
  - 现有 trace CSV、metadata、index 保存能力。
- [ ] 明确哪些代码可直接迁移、哪些只参考设计：
  - 可直接迁移候选：SCPI/VISA transport、VNA 控制基础类、链路箱协议封装、文件命名工具、部分单元测试样例。
  - 建议重新设计：校准业务流程、校准 UI、参数计算模型、项目配置、校准结果数据库/文件索引。

#### P4-02 新软件工程规划

- [ ] 确定新软件名称、仓库位置和交付形式。
- [ ] 确定技术栈：
  - Python + PySide6 桌面软件。
  - 或 Web UI + 本地硬件服务。
  - 或命令行批处理 + 简单配置界面。
- [ ] 建立独立工程骨架，建议包含：
  - `app/`：应用入口和 UI 装配。
  - `hardware/`：VNA、链路箱、SG、SA、辅助设备通信。
  - `calibration/`：校准项定义、执行器、公式计算。
  - `project/`：项目配置、馈源/喇叭/频段配置。
  - `storage/`：原始 S21、最终 L 参数、metadata、报告输出。
  - `tests/`：单元测试和流程模拟测试。
- [ ] 新软件不应依赖当前静区测试软件的 UI 主窗口或扫描流程。
- [ ] 新软件可以导入或复制经确认稳定的底层硬件适配器，但需要独立测试保护。
- [ ] 建立去耦合边界：
  - 不调用 `quiet_zone_tester.services.instrument_service.InstrumentService` 作为新软件业务入口。
  - 不依赖当前 `MainWindow`、扫描设置页、步进扫描流程或扫描数据模型。
  - 不使用当前静区测试软件的运行时全局状态。
  - 不把校准业务流程写入当前扫描流程中。
  - 不要求用户先启动静区测试软件才能运行校准软件。
  - 不共享可变配置文件；如复用配置字段，需要定义独立 schema 和迁移规则。
- [ ] 建立允许复用边界：
  - 可复用 VNA SCPI/VISA transport 的稳定底层实现。
  - 可复用链路箱 LCD74000F 协议封装或指令表。
  - 可复用文件命名、CSV 存储、metadata 思路。
  - 可复用现有单元测试思路，但测试应复制/迁移到新软件工程内。
- [ ] 建立硬件资源隔离策略：
  - 新软件启动时独占 VNA、链路箱、SG/SA 等硬件连接。
  - 检测端口/资源被其他程序占用时给出明确提示。
  - 禁止两个软件同时控制同一台链路箱或网分。

#### P4-03 新增校准业务模型

- [ ] 新增校准项定义模型，例如：
  - `CalibrationItem`
  - `CalibrationStep`
  - `CalibrationCommand`
  - `CalibrationOutputParam`
  - `CalibrationTraceParam`
- [ ] 支持以下校准项 ID：
  - `LINK-CAL-001`
  - `LINK-CAL-002`
  - `LINK-CAL-003`
  - `LINK-CAL-004`
- [ ] 每个校准项至少描述：
  - 校准目的。
  - 人工接线提示。
  - 链路箱指令序列。
  - VNA 采样参数。
  - 原始测量量 `S21_*`。
  - 最终输出参数 `L_*`。
  - 依赖文件，例如 `L_AUX_*`、`G_STD_HORN_H/V`。
  - 禁止指令和互斥工况。

#### P4-04 新增校准执行器

- [ ] 新增 CATR 校准执行服务，例如：
  - `calibration/calibration_runner.py`
  - `calibration/calibration_service.py`
- [ ] 执行器应支持：
  - 按校准项逐步骤执行。
  - 人工接线确认暂停点。
  - 链路箱指令下发。
  - VNA 配置、触发、采样。
  - 读取 sweep time / 等待 VNA 完成。
  - SCPI 错误检查。
  - 原始 `S21_*` 曲线保存。
  - 最终 `L_*` 参数计算。
  - 中断、失败恢复和日志记录。
- [ ] 执行顺序需要符合报告：
  - `LINK-CAL-001`：AUX-A/B/C 独立测试 -> DUT-H -> DUT-V -> DUT 内部段。
  - `LINK-CAL-002`：AUX-D 独立测试 -> DUT 到 VNA2 回传段 -> VNA 主链路三工况。
  - `LINK-CAL-003`：AUX-E 独立测试 -> DUT 到 SA 主输出 -> VNA1 到 SA 一致性校验。
  - `LINK-CAL-004`：AUX-F 独立测试 -> DUT 到 VNA2 回传段 -> SG 三工况。

#### P4-05 新增校准参数计算与文件管理

- [ ] 新增路损参数计算模块，例如：
  - `calibration/loss_formula.py`
  - `storage/loss_file_policy.py`
- [ ] 公式必须按带符号 dB 逐频点计算。
- [ ] 辅助线原始实测 `S21_AUX_*` 直接保存为带符号 `L_AUX_* = S21_AUX_*`，通常为负值，并直接参与 `+ L_AUX_*` 计算。
- [ ] 标准喇叭去嵌统一使用 `- G_STD_HORN_H/V`。
- [ ] 支持从标准喇叭增益文件读取 `G_STD_HORN_H/V`。
- [ ] 支持频点对齐策略：
  - 完全匹配。
  - 插值。
  - 最近频点回退是否允许需明确。
- [ ] 输出文件命名必须遵守：

```text
{PARAM}_{BAND}_{FEED}_{HORN}.csv
```

- [ ] 当 `HORN != NOHORN` 时，`BAND` 必须取馈源和喇叭频段交集。
- [ ] 输出 CSV 至少包含：
  - `freq_hz`
  - `value_db`
  - `param`
  - `band`
  - `feed`
  - `horn`
  - `source_cal`

#### P4-06 新增校准 UI

- [ ] 在新软件中设计独立“CATR 校准”主界面。
- [ ] UI 应显示：
  - 校准项列表。
  - 当前校准项说明。
  - 人工接线图/文字确认。
  - 即将下发的链路箱指令。
  - VNA 参数配置。
  - 当前步骤进度。
  - 原始曲线采样状态。
  - 最终输出参数列表。
  - 输出文件路径。
- [ ] UI 应支持：
  - 单步执行。
  - 整项执行。
  - 暂停/继续。
  - 失败重试。
  - 只重新计算文件，不重新采样。

#### P4-07 与测试项执行联动

- [ ] 测试项运行前检查所需路损文件是否存在。
- [ ] 测试项页面显示当前将使用的路损文件：
  - `LINK-TXR-*` 使用 `L_VNA_FEED_H/V` 与 `L_DUT_VNA`。
  - `LINK-GT-001` 使用 `L_SG_DUT_H/V` 和 `L_DUT_SA_AMP1`。
  - `LINK-SYS-001` 使用 `L_SYS_TX_SA_H/V` 或 `L_SYS_TX_SA_H/V_AMP2`。
  - `LINK-SYS-002` 使用 `L_SG_DUT_H/V`。
- [ ] 测试结果 metadata 中记录：
  - 路损文件名。
  - 路损文件 hash。
  - 生成该路损文件的校准项 ID。
  - 馈源、喇叭、频段。

#### P4-08 最小测试覆盖

- [ ] 为校准项定义增加单元测试：
  - 校准项 ID 完整性。
  - 每个步骤命令序列正确。
  - 禁止指令不被生成。
- [ ] 为路损公式增加单元测试：
  - `S21_AUX_*` 到 `L_AUX_* = S21_AUX_*` 的带符号保存与 `+ L_AUX_*` 计算。
  - `G_STD_HORN` 正值减法。
  - AMP 链路结果可为正值。
  - 频段交集命名。
- [ ] 为链路箱命令生成增加测试：
  - `LINK-CAL-002` 三工况。
  - `LINK-CAL-003` AUX-E 与一致性校验。
  - `LINK-CAL-004` AUX-F 与 SG 三工况。
- [ ] 为文件命名增加测试：
  - `F10_17G + H10_15G -> 10_15G`。
  - `F10_17G + H14P5_22G -> 14P5_17G`。
  - `F17_31G + H14P5_22G -> 17_22G`。
  - `F17_31G + H21P7_33G -> 21P7_31G`。

## 4. 相关文档

- `docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`
- `docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.md`
- `docs/CATR暗室校准测试方案BACKUP USER.html`
- `CATR_CHAMBER_OPERATION_PLAYBOOK.md`
- `REPORT_SCREENSHOT_CHECK_PLAYBOOK.md`
- `resource/LCD74000F.md`
