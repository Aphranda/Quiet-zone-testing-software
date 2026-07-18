# CATR 暗室校准与测试操作汇总

Status: Active  
Domain: CATR  
Canonical: `catr_loss_calibrator/docs/CATR_CHAMBER_OPERATION_PLAYBOOK.md`  
Related: `catr_loss_calibrator/docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`, `catr_loss_calibrator/docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN_TODO.md`  
Last updated: 2026-07-18

本文用于从当前方案文档中抽取“可执行操作口径”，便于后续继续标注测试项、校准项和自动化流程。完整报告见 `CATR_CHAMBER_CALIBRATION_TEST_PLAN.md` / `.html`。

## 1. 总体约定

- 链路箱物理端口：
  - `H` / `V`：链路箱到暗室接口板 H/V 极化端口。
  - `DUT`：链路箱 DUT 回传端口。
  - `VNA1` / `VNA2`：网分发射 / 接收等效端口。
  - `SG` / `SA`：信号源 / 频谱仪端口。
- 暗室侧路径：
  - `链路箱 H/V -> 暗室接口板 H/V -> 馈源 -> 反射面 -> 标准增益喇叭或 DUT`
  - `标准增益喇叭或 DUT -> 暗室接口板 DUT -> 链路箱 DUT`
- 放大器约定：
  - `AMP1`：DUT 接收回传侧，可用于 `DUT -> AMP1 -> VNA2/SA`。
  - `AMP2`：馈源侧单向放大器，只用于从馈源接收方向；不用于 SG 发射、整机接收等发射链路。
- 路损值口径：
  - `L_*` 使用 dB 值保存，符号由参数定义决定，不由名称决定。
  - 无源传输链路通常为负值；含放大器链路可能为正值。
  - 标准增益喇叭增益 `G_STD_HORN_H/V` 为正增益，去嵌时使用减号。
  - 辅助线原始实测量记为 `S21_AUX_*`，通常为负值；参与计算前转换为线缆损耗量 `L_AUX_* = -S21_AUX_*`，通常为正值，去嵌时使用 `+ L_AUX_*`。

## 2. 校准操作汇总

| ID | 名称 | 主要目的 | 链路箱指令 | 关键输出 |
|---|---|---|---|---|
| `LINK-CAL-001` | 暗室内部链路校准 | 校准暗室接口板 H/V 经馈源、反射面、标准增益喇叭到 DUT 口，以及转台 DUT 到接口板 DUT 段 | 不下发链路箱指令 | `L_CH_INT_H/V/DUT`，`L_CH_INT_FEED_H/V` |
| `LINK-CAL-002` | VNA 链路损耗校准 | 校准 VNA1 经 H/V 空间链路到 VNA2 的测试链路；同时用 AUX-D 校准 DUT 到 VNA2 回传段 | `DUT,VNA2` / `DUT,AMP1,VNA2` + `H/V[,AMP2],VNA1` | `L_VNA_H/V`，`L_VNA_H/V_AMP1`，`L_VNA_H/V_AMP2`，`L_DUT_VNA`，`L_DUT_VNA_AMP1`，`L_VNA_FEED_*` |
| `LINK-CAL-003` | SA 校准 | 校准 DUT 参考面到 SA 的直通/AMP1 接收链路；VNA1 到 SA 三工况作为一致性校验 | `DUT,SA` / `DUT,AMP1,SA`；校验时配合 `H/V[,AMP2],VNA1` | `L_DUT_SA`，`L_DUT_SA_AMP1`，`T_VNA1_SA_*` |
| `LINK-CAL-004` | SG 校准 | 校准 SG 到 DUT 参考面的等效发射链路；用 AUX-F 重复测回传段 | `H/V,SG` / `H/V,AMP2,SG` + `DUT,VNA2` / `DUT,AMP1,VNA2` | `L_SG_DUT_H/V`，`L_SG_DUT_H/V_AMP1`，`L_SG_DUT_H/V_AMP2` |

### 2.1 LINK-CAL-001 关键公式

| 参数 | 公式 |
|---|---|
| `L_CH_INT_H` | `S21_CH_INT_H_RAW + L_AUX_A + L_AUX_C - G_STD_HORN_H` |
| `L_CH_INT_V` | `S21_CH_INT_V_RAW + L_AUX_B + L_AUX_C - G_STD_HORN_V` |
| `L_CH_INT_DUT` | `S21_CH_INT_DUT_RAW + L_AUX_A + L_AUX_C` |
| `L_CH_INT_FEED_H/V` | `L_CH_INT_H/V - L_CH_INT_DUT` |

说明：`L_CH_INT_H/V` 的原始闭合测量包含馈源、反射面、标准增益喇叭；`L_CH_INT_DUT` 不经过标准喇叭。

### 2.2 LINK-CAL-002 关键工况

| 工况 | 指令 | 输出关注 |
|---|---|---|
| 两边直通 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H/V, VNA1` | `L_VNA_H/V`，`L_DUT_VNA` |
| AMP1 开启，馈源侧直通 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK H/V, VNA1` | `L_VNA_H/V_AMP1`，`L_DUT_VNA_AMP1` |
| AMP2 开启，DUT 侧直通 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H/V, AMP2, VNA1` | `L_VNA_H/V_AMP2`，`L_DUT_VNA` |

### 2.3 LINK-CAL-003 关键工况

| 工况 | 指令 | 输出关注 |
|---|---|---|
| DUT 到 SA 直通 | `CONFigure:LINK DUT, SA` | `L_DUT_SA` |
| DUT 经 AMP1 到 SA | `CONFigure:LINK DUT, AMP1, SA` | `L_DUT_SA_AMP1` |
| VNA1 到 SA 一致性校验，两边直通 | `CONFigure:LINK H/V, VNA1` + `CONFigure:LINK DUT, SA` | `T_VNA1_SA_H/V` |
| VNA1 到 SA 一致性校验，AMP1 | `CONFigure:LINK H/V, VNA1` + `CONFigure:LINK DUT, AMP1, SA` | `T_VNA1_SA_H/V_AMP1` |
| VNA1 到 SA 一致性校验，AMP2 | `CONFigure:LINK H/V, AMP2, VNA1` + `CONFigure:LINK DUT, SA` | `T_VNA1_SA_H/V_AMP2` |

### 2.4 LINK-CAL-004 关键工况

| 工况 | 指令 | 输出关注 |
|---|---|---|
| AUX-F 回传段，DUT 到 VNA2 直通 | `CONFigure:LINK DUT, VNA2` | `L_DUT_VNA_F` |
| AUX-F 回传段，DUT 经 AMP1 到 VNA2 | `CONFigure:LINK DUT, AMP1, VNA2` | `L_DUT_VNA_F_AMP1` |
| SG 两边直通 | `CONFigure:LINK H/V, SG` + `CONFigure:LINK DUT, VNA2` | `L_SG_DUT_H/V` |
| SG 发射侧直通，DUT 回传侧 AMP1 | `CONFigure:LINK H/V, SG` + `CONFigure:LINK DUT, AMP1, VNA2` | `L_SG_DUT_H/V_AMP1` |
| SG 经 AMP2，DUT 回传侧直通 | `CONFigure:LINK H/V, AMP2, SG` + `CONFigure:LINK DUT, VNA2` | `L_SG_DUT_H/V_AMP2` |

## 3. 测试项操作汇总

| ID | 名称 | 链路口径 | 指令 |
|---|---|---|---|
| `LINK-TXR-001` | DUT 通道校准 | VNA1 到 VNA2 直通，接上 DUT，不经过 AMP1/AMP2 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H/V, VNA1` |
| `LINK-TXR-002` | 方向图测试 | 同 VNA 直通链路 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H/V, VNA1` |
| `LINK-TXR-003` | 有源增益测试 | 同 VNA 直通链路 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H/V, VNA1` |
| `LINK-TXR-004` | 天线板 EIRP 测试 | 同 VNA 直通链路 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H/V, VNA1` |
| `LINK-GT-001` | G/T 测试 | SG 直通发射，SA 经 AMP1 放大接收；不允许 AMP2 | `CONFigure:LINK DUT, AMP1, SA` + `CONFigure:LINK H/V, SG` |
| `LINK-SYS-001` | 整机发射测试 | DUT 自身发射到馈源，SA 接收；默认直通，可选 AMP2 | 直通：`DUT,SA` + `H/V,SA`；AMP1：`DUT,AMP1,SA` + `H/V,SA` |
| `LINK-SYS-002` | 整机接收测试 | SG 经馈源直通路径发射，DUT 终端接收；SA 不开通 | `CONFigure:LINK H/V, SG` |

## 4. 测试项所需路损参数

| 测试项 | 需要的校准参数 |
|---|---|
| `LINK-TXR-001` / `002` / `003` / `004` | `L_VNA_H` / `L_VNA_V` |
| `LINK-GT-001` | `L_SG_DUT_H` / `L_SG_DUT_V`，`L_DUT_SA_AMP1` |
| `LINK-SYS-001` | `L_DUT_SA` 或 `L_DUT_SA_AMP1` |
| `LINK-SYS-002` | `L_SG_DUT_H` / `L_SG_DUT_V` |

## 5. 路损文件命名规则

格式：

```text
{PARAM}_{BAND}_{FEED}_{HORN}.csv
```

字段：

| 字段 | 含义 | 示例 |
|---|---|---|
| `PARAM` | 路损参数名 | `L_VNA_FEED_H`，`L_DUT_SA_AMP1` |
| `BAND` | 实际适用频段，必须落在馈源与喇叭交集内 | `10_15G`，`14P5_17G`，`17_22G`，`21P7_31G` |
| `FEED` | 馈源短码 | `F10_17G`，`F17_31G` |
| `HORN` | 标准喇叭短码；不涉及喇叭时用 `NOHORN` | `H10_15G`，`H14P5_22G`，`H21P7_33G`，`NOHORN` |

当前有效交集：

| 馈源 | 标准喇叭 | BAND | 实际频段 |
|---|---|---|---|
| `F10_17G` | `H10_15G` | `10_15G` | 10–15 GHz |
| `F10_17G` | `H14P5_22G` | `14P5_17G` | 14.5–17 GHz |
| `F17_31G` | `H14P5_22G` | `17_22G` | 17–22 GHz |
| `F17_31G` | `H21P7_33G` | `21P7_31G` | 21.7–31 GHz |

示例：

```text
L_VNA_FEED_H_10_15G_F10_17G_H10_15G.csv
L_VNA_FEED_V_21P7_31G_F17_31G_H21P7_33G.csv
L_DUT_SA_AMP1_10_17G_F10_17G_NOHORN.csv
L_SG_DUT_H_17_22G_F17_31G_H14P5_22G.csv
```

CSV 建议字段：

| 字段 | 含义 |
|---|---|
| `freq_hz` | 频点，单位 Hz |
| `value_db` | 最终带符号链路损耗 / 传输值 |
| `param` | 参数名 |
| `band` | 频段短码 |
| `feed` | 馈源短码 |
| `horn` | 喇叭短码或 `NOHORN` |
| `source_cal` | 来源校准项，如 `LINK-CAL-002` |

## 6. 后续待确认点

- 跨喇叭频段重叠区的默认优先级：14.5–15 GHz、21.7–22 GHz。
- 各 `L_*` 文件是否按测试项/频段拆分存储，还是按参数聚合后由软件按频段选择。
- UI 中是否需要直接展示“本测试项将读取哪些路损文件”。
- 自动化执行时，是否把 `LINK-CAL-003` 的 VNA1 到 SA 三工况一致性校验作为强制步骤，还是作为可选复核。
