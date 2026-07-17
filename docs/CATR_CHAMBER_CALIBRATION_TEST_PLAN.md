# 链路管理设计

Status: Active
Domain: LINK
Canonical: `docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.md`
Related: `docs/architecture_migration_plan.md`, `docs/INSTRUMENT_MANAGEMENT_DESIGN.md`
Last updated: 2026-07-17

本文档定义开关箱链路操作、历史 S 参数兼容路由、开关箱 profile 和链路控制 UI/ViewModel 的边界。

## 职责

- 按极化切换源端链路：`H,VNA1`、`V,VNA1`。
- 按 DUT 目标切换仪表链路：`DUT,VNA2`、`DUT,AMP1,VNA2`、`DUT,SA`、`DUT,AMP1,SA`。
- 保留 `S11/S21/S12/S22` 到开关箱命令的历史兼容路由，但 S 参数不再作为主链路事实。
- 支持 LCD74000F、TC500 和 Mock profile。
- 执行开关箱链路切换和原始命令发送。

## 当前实现

- 路由规则：`domains/link_management/link_router.py`
- profile：`domains/link_management/switch_box_profiles.py`
- 执行服务：`domains/link_management/link_service.py`
- UI 状态和链路图派生状态：`presentation/modules/link_control/link_control_view_model.py`
- Widget 兼容入口：`ui/widgets/switch_box_control_panel.py`

## 边界

链路管理不负责底层串口/TCP 通信；真实通信在 `hardware/switch_box/` 中实现。

链路管理不负责 VNA 采样；采样由 `AcquisitionService` 管理。

## 关键规则

- Widget 不直接拼接业务命令。
- S 参数只属于 VNA 测量；开关箱主链路操作使用极化、DUT 目标或原始命令。
- `CONFigure:LINK H,...` / `CONFigure:LINK V,...` 切换的是链路箱到暗室接口板的 H/V 极化端口；后续物理路径为“链路箱 H/V -> 暗室接口板 H/V -> 馈源 -> 反射面 -> 标准增益喇叭或 DUT”。DUT/标准喇叭接收侧可按测试对象回到链路箱：VNA2 回传可选 `DUT,VNA2` 直通或 `DUT,AMP1,VNA2` 经 AMP1，SA 接收可选 `DUT,SA` 直通或 `DUT,AMP1,SA` 经 AMP1。
- 暗室整体物理链路参考 `resource/暗室整体链路.png`；链路箱实际链路图参考 `resource/原始链路图.png`。
- AMP2 为单向放大器；只有从馈源接收信号的链路才允许选择是否经过 AMP2。信号源发射、转台DUT到VNA的损耗辅助线和整机接收链路不使用 AMP2。
- 测试时外部仪表接线固定：网分、SA、SG 必须接到链路箱对应物理端口。只有校准时才允许按校准对象临时改接网分 PORT 到链路箱 VNA1/VNA2/SG/SA 等端口。
- `LinkRouter` 可独立测试，不依赖真实开关箱。
- `LinkService` 只依赖开关箱 controller 协议。
- 链路图高亮 token 由 `LinkControlViewModel.diagram_state()` 派生，Widget 只负责绘制。

## 参数与符号约定

本方案中校准结果最终进入路损数学计算。为避免符号方向混淆，统一采用以下命名：

| 符号/字段 | 含义 | 说明 |
|---|---|---|
| `L_*` | Loss，校准后损耗量 | 单位 dB，作为正的损耗量参与计算。 |
| `L_AUX_*` | Auxiliary Loss，辅助链路临时损耗量 | 单位 dB，作为正的损耗量保存；不作为最终测试项路损直接使用，但会参与后续扣除计算。 |
| `T_*` | Temporary，临时中间损耗量 | 单位 dB，通常表示带辅助链路的闭合环路测量结果；必须保存，用于计算最终 `L_*`。 |
| `S21_*` | 网分原始 S21 测量值 | 单位 dB，用于追溯和复算，不直接替代 `L_*`。 |
| `value_db` | 参与计算的校准后损耗值 | 按频点保存。 |
| `raw_s21_db` | 原始 S21 记录 | 用于校准结果追溯。 |
| `freq_hz[]` | 频点数组 | 所有损耗参数应按频点保存。 |

核心校准参数简称：

| 参数 | 含义 | 来源 |
|---|---|---|
| `L_AUX_A` / `L_AUX_B` / `L_AUX_C` | 三根 3M 辅助线自身损耗，临时变量 | `LINK-CAL-001` 辅助线独立测试 |
| `L_CH_INT_H` / `L_CH_INT_V` / `L_CH_INT_DUT` | 暗室内部链路损耗：`CP-H/V` 或 `TD` 至 `CP-DUT` | `LINK-CAL-001` 暗室内部链路校准 |
| `L_CH_INT_FEED_H` / `L_CH_INT_FEED_V` | 馈源发射到转台DUT接口/DUT 端面的派生损耗 | `L_CH_INT_H/V - L_CH_INT_DUT` |
| `L_VNA_H/V` / `L_VNA_H/V_AMP1` / `L_VNA_H/V_AMP2` | VNA 测试链路等效损耗，分别对应两边直通、AMP1 回传、AMP2 发射侧三种工况 | `LINK-CAL-002` VNA 链路损耗校准 |
| `L_AUX_D` | AUX-D 辅助线自身损耗，临时变量 | `LINK-CAL-002` AUX-D 单独测试 |
| `L_DUT_VNA` / `L_DUT_VNA_AMP1` | `TD` 至 `LB-VNA2` 的直通/AMP1 回传损耗 | `LINK-CAL-002` AUX-D 回传段校准 |
| `L_VNA_FEED_H` / `L_VNA_FEED_V` / `L_VNA_FEED_H_AMP2` / `L_VNA_FEED_V_AMP2` | `LB-VNA1` 至 `DUT_REF` / `FH/FV` 的派生等效损耗 | `L_VNA_* - L_DUT_VNA` |
| `L_AUX_E` | AUX-E 辅助线自身损耗，临时变量 | `LINK-CAL-003` AUX-E 单独测试 |
| `T_VNA1_SA_*` | VNA1 到 SA 的完整闭合环路临时损耗，覆盖两边直通、AMP1、AMP2 三种工况 | `LINK-CAL-003` VNA1 到 SA 校准原始闭合环路 |
| `T_AUXE_DUT_SA` / `T_AUXE_DUT_SA_AMP1` | AUX-E 接转台DUT接口后的 SA 接收闭合环路临时损耗 | `LINK-CAL-003` AUX-E 接转台DUT接口校准 |
| `L_DUT_SA` / `L_DUT_SA_AMP1` | `DUT_REF` 至 `LB-SA` 的直通/AMP1 等效接收链路损耗 | `T_AUXE_DUT_SA* - L_AUX_E` |
| `L_AUX_F` | AUX-F 辅助线自身损耗，临时变量 | `LINK-CAL-004` AUX-F 单独测试 |
| `L_DUT_VNA_F` / `L_DUT_VNA_F_AMP1` | `LINK-CAL-004` 中重复测得的直通/AMP1 回传损耗 | `LINK-CAL-004` AUX-F 回传段校准 |
| `T_SG_*` | SG 到 VNA2 的完整闭合环路临时损耗，覆盖两边直通、AMP1、AMP2 三种工况 | `LINK-CAL-004` SG 校准原始闭合环路 |
| `L_SG_DUT_*` | `LB-SG` 至 `DUT_REF` 的等效发射链路损耗，覆盖三种工况 | `T_SG_* - L_DUT_VNA_F*` |

端口/参考面英文简称：

| 简称 | 英文全称 | 含义 |
|---|---|---|
| `P1` / `P2` | VNA Port 1 / 2 | 外部网分真实端口。 |
| `LB` | Link Box | 链路箱端口前缀，例如 `LB-H`、`LB-V`、`LB-VNA1`、`LB-VNA2`、`LB-SA`、`LB-SG`。 |
| `CP` | Chamber Panel | 暗室接口板端口前缀，例如 `CP-H`、`CP-V`、`CP-DUT`。 |
| `TD` | Turntable DUT Port | 转台 DUT 接口。 |
| `DUT_REF` | DUT Reference Plane | DUT 测试参考面；校准时可由标准增益喇叭替代。 |
| `FH` / `FV` | Feed H / Feed V | 馈源 H/V 极化参考面。 |
| `POL-H` / `POL-V` | Polarization H / V | 仅表示 H/V 极化选择，不代表具体物理端口。 |

命名规则：

- 参数名保持短，例如 `L_DUT_SA`、`L_DUT_SA_AMP1`；不要把 `LB/CP/TD/DUT_REF` 全部塞进参数名。
- 物理端口与参考面的区别写在参数定义、链路图和公式说明中。
- 链路箱 SCPI 指令中的 `H`、`V`、`DUT` 保留设备命令写法；在公式含义中应使用 `LB-*`、`CP-*`、`TD`、`DUT_REF`、`FH/FV` 避免混淆。

## 测试项操作文件架构

链路测试项按“操作定义”组织，后续可直接迁移为测试项配置或用例模型。每个测试项建议保持以下字段：

| 字段 | 说明 |
|---|---|
| 测试项 ID | 稳定编号，便于代码、UI 和记录文件引用。 |
| 名称 | 面向用户显示的测试项名称。 |
| 仪表角色 | 本测试项涉及 VNA、SG、SA 的角色。 |
| DUT 状态 | DUT 是否接入、是否发射、是否接收，或是否替换为标准增益喇叭。 |
| 可选参数 | 极化、TX 是否经过 AMP2 等。 |
| 链路操作步骤 | 实际下发到链路箱的顺序。 |
| 禁止/注意 | 明确不能下发的链路，避免误切。 |

## 测试项操作清单

| 测试项 ID | 名称 | 仪表角色 | DUT/校准件状态 | 可选参数 | 链路模板 |
|---|---|---|---|---|---|
| `LINK-CAL-001` | 暗室内部链路校准 | VNA S21 闭环 | 三根 3M 辅助线直接接网分和暗室接口板 H/V/DUT | 先测 DUT-H，再测 DUT-V；不经过链路箱 | 暗室内部辅助线链路 |
| `LINK-CAL-002` | VNA 链路损耗校准 | VNA 发射 + VNA 接收 | 转台DUT接口换标准增益喇叭；另用 AUX-D 校准转台DUT到 VNA2 回传段 | 极化 H/V；三种工况：两边直通、AMP1 开启且馈源侧直通、AMP2 开启且 DUT 侧直通 | 校准 VNA 链路 + AUX-D 回传段 |
| `LINK-CAL-003` | SA 校准 | VNA S21 闭环 | 网分 PORT1 接链路箱 VNA1，网分 PORT2 接链路箱 SA | 极化 H/V；PORT1 侧经 VNA1->H/V 发射，PORT2 侧经 DUT->SA 接收 | SA 校准链路 |
| `LINK-CAL-004` | SG 校准 | VNA S21 闭环 | 网分 PORT1 接链路箱 SG，网分 PORT2 接链路箱 VNA2 | 极化 H/V；PORT1 侧经 SG->H/V 发射，PORT2 侧经 DUT->VNA2 接收 | SG 校准链路 |
| `LINK-TXR-001` | DUT 通道校准 | VNA | 接上 DUT；不使用 `DUT -> VNA2` | 极化 H/V；馈源接收方向是否经过 AMP2 | DUT VNA：通道校准链路 |
| `LINK-TXR-002` | 方向图测试 | VNA | 接上 DUT；不使用 `DUT -> VNA2` | 极化 H/V；馈源接收方向是否经过 AMP2 | DUT VNA：方向图链路 |
| `LINK-TXR-003` | 有源增益测试 | VNA | 接上 DUT；不使用 `DUT -> VNA2` | 极化 H/V；馈源接收方向是否经过 AMP2 | DUT VNA：有源增益链路 |
| `LINK-TXR-004` | 天线板 EIRP 测试 | VNA | 接上 DUT；不使用 `DUT -> VNA2` | 极化 H/V；馈源接收方向是否经过 AMP2 | DUT VNA：天线板 EIRP 链路 |
| `LINK-GT-001` | G/T 测试 | SG 发射 + SA 接收 | DUT 接收侧切到 SA | 极化 H/V；不允许 AMP2 | SG/SA 链路 |
| `LINK-SYS-001` | 整机发射测试 | SA 接收；SG 不输出功率 | DUT 发射功率，SA 接收 | 极化 H/V；不允许 AMP2 | SG/SA 链路 |
| `LINK-SYS-002` | 整机接收测试 | SG 输出测试信号 | DUT 自身接收；SA 不参与 | 极化 H/V；不允许 AMP2 | SG-only 链路 |

## 校准模板总览

校准模板不只定义链路箱指令，还需要定义“闭合环路测量量、临时/追溯量、最终输出量”的关系。后续测试项引用校准结果时，应优先使用最终输出参数；带 AUX 或带回传段的闭合环路结果只能作为临时量保存。

| 校准项 | 主要测量/临时量 | 最终输出参数 | 核心扣除关系 |
|---|---|---|---|
| `LINK-CAL-001` 暗室内部链路 | `S21_CH_INT_*`，`L_AUX_A/B/C` | `L_CH_INT_H/V/DUT`，`L_CH_INT_FEED_H/V` | 先扣除 AUX-A/B/C；再由 `L_CH_INT_H/V - L_CH_INT_DUT` 得到馈源到 DUT 参考面损耗。 |
| `LINK-CAL-002` VNA 链路损耗 | `L_VNA_*`，`L_AUX_D`，`L_DUT_VNA` / `L_DUT_VNA_AMP1` | `L_VNA_FEED_*` | VNA 主闭合环路扣除对应的 `L_DUT_VNA` / `L_DUT_VNA_AMP1`，得到 VNA 发射侧到 DUT/馈源参考面的等效损耗。 |
| `LINK-CAL-003` SA 校准 | `L_AUX_E`，`T_AUXE_DUT_SA*`，`T_VNA1_SA_*` | `L_DUT_SA`，`L_DUT_SA_AMP1` | AUX-E 接转台DUT接口直接得到 DUT 到 SA 的关键接收损耗；VNA1 到 SA 三工况仅作为一致性校验。 |
| `LINK-CAL-004` SG 校准 | `L_AUX_F`，`L_DUT_VNA_F` / `L_DUT_VNA_F_AMP1`，`T_SG_H/V`，`T_SG_H/V_AMP1`，`T_SG_H/V_AMP2` | `L_SG_DUT_H/V`，`L_SG_DUT_H/V_AMP1`，`L_SG_DUT_H/V_AMP2` | SG 校准内先用 AUX-F 重复测回传段，再用 SG 到 VNA2 闭合环路扣除对应回传段，得到三工况等效发射链路损耗。 |

关键扣除公式：

| 公式 | 说明 |
|---|---|
| `L_CH_INT_FEED_H/V = L_CH_INT_H/V - L_CH_INT_DUT` | 由暗室内部 H/V 链路扣除 DUT 内部段，得到馈源到 DUT 参考面的暗室内部损耗。 |
| `L_VNA_FEED_* = L_VNA_* - L_DUT_VNA` | VNA 主链路闭合损耗扣除对应的 DUT 到 VNA2 回传段（直通或 AMP1）。 |
| `L_DUT_SA = T_AUXE_DUT_SA - L_AUX_E` | AUX-E 接转台DUT接口，扣除 AUX-E 自身损耗后得到 DUT 参考面至 SA 端口的直通接收链路损耗。 |
| `L_DUT_SA_AMP1 = T_AUXE_DUT_SA_AMP1 - L_AUX_E` | AUX-E 接转台DUT接口，扣除 AUX-E 自身损耗后得到 DUT 参考面至 SA 端口的 AMP1 接收链路损耗。 |
| `L_DUT_VNA_F = -S21_DUT_VNA_F_RAW - L_AUX_F` | LINK-CAL-004 内用 AUX-F 重复测得 DUT 到 VNA2 直通回传段。 |
| `L_DUT_VNA_F_AMP1 = -S21_DUT_VNA_F_AMP1_RAW - L_AUX_F` | LINK-CAL-004 内用 AUX-F 重复测得 DUT 到 VNA2 经 AMP1 回传段。 |
| `L_SG_DUT_H/V = T_SG_H/V - L_DUT_VNA_F` | SG 两边直通闭合环路扣除 LINK-CAL-004 内重复测得的 DUT 到 VNA2 直通回传段。 |
| `L_SG_DUT_H/V_AMP1 = T_SG_H/V_AMP1 - L_DUT_VNA_F_AMP1` | SG 发射侧直通、DUT 回传侧经 AMP1 的闭合环路，扣除 LINK-CAL-004 内重复测得的 AMP1 回传段。 |
| `L_SG_DUT_H/V_AMP2 = T_SG_H/V_AMP2 - L_DUT_VNA_F` | SG 发射侧经 AMP2、DUT 回传侧直通的闭合环路，扣除 LINK-CAL-004 内重复测得的直通回传段。 |

关键链路箱指令速览：

| 校准场景 | 链路箱指令 | 备注 |
|---|---|---|
| `LINK-CAL-001` 暗室内部链路 | 不下发 | AUX-A/B/C 直接接网分和暗室接口板/转台DUT接口。 |
| `LINK-CAL-002` VNA 主链路 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H/V[, AMP2], VNA1` | 主链路使用标准增益喇叭；AUX-D 回传段按选择下发 DUT→VNA2 直通或 DUT→AMP1→VNA2。 |
| `LINK-CAL-003` VNA1 到 SA | `CONFigure:LINK H/V[,AMP2], VNA1` + `CONFigure:LINK DUT,SA` 或 `CONFigure:LINK DUT,AMP1,SA` | 三种工况：两边直通、AMP1 开启且馈源侧直通、AMP2 开启且 DUT 侧直通。 |
| `LINK-CAL-004` SG 到 VNA2 | `CONFigure:LINK H/V, SG` + `CONFigure:LINK DUT,VNA2`；`CONFigure:LINK H/V, SG` + `CONFigure:LINK DUT,AMP1,VNA2`；`CONFigure:LINK H/V,AMP2,SG` + `CONFigure:LINK DUT,VNA2` | 三种工况：两边直通、AMP1 开启且发射侧直通、AMP2 开启且 DUT 侧直通。 |

## 通用链路模板

### 模板 A0：暗室内部辅助线链路

用途：校准暗室接口板 H/V 到 DUT 的内部链路，以及转台DUT接口到暗室接口板 DUT 的 DUT 内部段链路。该校准使用三根 3M 辅助线；三根辅助线需先分别独立测试，随后直接接到网分、转台DUT接口和暗室接口板，不经过链路箱，不下发链路箱指令。

操作步骤：

1. 准备三根 3M 辅助线作为外部参考线，分别标记为 AUX-A、AUX-B、AUX-C。
2. 辅助线独立测试：三根 3M 辅助线分别直连网分 PORT1 与 PORT2，测得 `L_AUX_A`、`L_AUX_B`、`L_AUX_C`。
3. 辅助线分配规则：AUX-A 用于 PORT1 到 H/转台DUT接口；AUX-B 用于 PORT1 到 V；AUX-C 固定用于暗室接口板 DUT 到 PORT2。
4. DUT-H 测量：网分 PORT1 经 AUX-A 接暗室接口板 H，暗室接口板 DUT 经 AUX-C 接网分 PORT2。
5. DUT-V 测量：网分 PORT1 经 AUX-B 接暗室接口板 V，暗室接口板 DUT 经 AUX-C 接网分 PORT2。
6. DUT 内部段测量：网分 PORT1 经 AUX-A 接转台DUT接口，暗室接口板 DUT 经 AUX-C 接网分 PORT2。
7. 上述测量均不经过链路箱，不下发 `CONFigure:LINK` 指令；暗室内部链路损耗计算时需扣除对应 3M 辅助线自身损耗。

指令组合：

| 测量顺序 | 外部接线 | 链路箱指令 |
|---|---|---|
| 0：辅助线独立测试 | 三根 3M 辅助线分别直连网分 PORT1 与 PORT2，测得 `L_AUX_A`、`L_AUX_B`、`L_AUX_C` | 不下发 |
| 1：DUT-H | 网分 PORT1 -> AUX-A -> 暗室接口板 H；暗室接口板 DUT -> AUX-C -> 网分 PORT2 | 不下发 |
| 2：DUT-V | 网分 PORT1 -> AUX-B -> 暗室接口板 V；暗室接口板 DUT -> AUX-C -> 网分 PORT2 | 不下发 |
| 3：DUT 内部段 | 网分 PORT1 -> AUX-A -> 转台DUT接口；暗室接口板 DUT -> AUX-C -> 网分 PORT2 | 不下发 |

可得路损段与数学计算：

| 最终参数 | 对应物理段 | 原始测量量 | 计算公式 |
|---|---|---|---|
| `L_AUX_A` | AUX-A 3M 辅助线自身损耗 | `S21_AUX_A` | `L_AUX_A = -S21_AUX_A` |
| `L_AUX_B` | AUX-B 3M 辅助线自身损耗 | `S21_AUX_B` | `L_AUX_B = -S21_AUX_B` |
| `L_AUX_C` | AUX-C 3M 辅助线自身损耗 | `S21_AUX_C` | `L_AUX_C = -S21_AUX_C` |
| `L_CH_INT_H` | 暗室接口板 H -> 暗室内部 H 链路 -> 暗室接口板 DUT | `S21_CH_INT_H_RAW` | `L_CH_INT_H = -S21_CH_INT_H_RAW - L_AUX_A - L_AUX_C` |
| `L_CH_INT_V` | 暗室接口板 V -> 暗室内部 V 链路 -> 暗室接口板 DUT | `S21_CH_INT_V_RAW` | `L_CH_INT_V = -S21_CH_INT_V_RAW - L_AUX_B - L_AUX_C` |
| `L_CH_INT_DUT` | 转台DUT接口 -> DUT 内部段 -> 暗室接口板 DUT | `S21_CH_INT_DUT_RAW` | `L_CH_INT_DUT = -S21_CH_INT_DUT_RAW - L_AUX_A - L_AUX_C` |

说明：以上公式按 dB 量逐频点计算；若仪表或数据处理已将原始 S21 转成正损耗，则公式中的 `-S21_*` 应替换为对应的正损耗原始量。

禁止/注意：

- 暗室内部链路校准不经过链路箱。
- 暗室内部链路校准不使用 `CONFigure:LINK H,...`、`CONFigure:LINK V,...` 或 `CONFigure:LINK DUT,...`。
- 三根 3M 辅助线必须先独立测试。
- 辅助线使用固定分配：DUT-H 使用 AUX-A + AUX-C；DUT-V 使用 AUX-B + AUX-C；DUT 内部段使用 AUX-A + AUX-C。
- 测量顺序固定为辅助线独立测试、DUT-H、DUT-V、DUT 内部段。

### 模板 A：VNA 链路损耗校准主链路

用途：用网分执行 VNA 主链路损耗校准。校准时将转台DUT接口替换为标准增益喇叭。即使正式测试链路使用 SA 或 SG，其损耗也由网分进行等效校准。

操作步骤：

1. 切换标准增益喇叭接收侧到 VNA2。
2. 根据极化切换 TX 侧到 VNA1；VNA1 经链路箱 H/V、暗室接口板 H/V、馈源、反射面到标准增益喇叭。
3. 如果校准包含 TX 放大器路径，则 TX 侧经过 AMP2；否则直连 VNA1。

指令组合：

| 极化 | TX 放大器 | 链路箱指令 |
|---|---|---|
| H | 不经过 AMP2 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H, VNA1` |
| V | 不经过 AMP2 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK V, VNA1` |
| H | 经过 AMP2 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H, AMP2, VNA1` |
| V | 经过 AMP2 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK V, AMP2, VNA1` |

SA 校准对应关系：

| 校准对象 | 校准时使用的网分闭合环路 | 校准指令 |
|---|---|---|
| VNA1 到 SA，H/V 环路，两边直通 | 网分 PORT1 -> 链路箱 VNA1 -> 链路箱 H/V -> 暗室接口板 H/V -> 馈源 -> 反射面 -> 标准增益喇叭/转台DUT接口 -> 暗室接口板 DUT -> 链路箱 SA -> 网分 PORT2 | `CONFigure:LINK H/V, VNA1` + `CONFigure:LINK DUT,SA` |
| VNA1 到 SA，H/V 环路，AMP1 开启且馈源侧直通 | 网分 PORT1 -> 链路箱 VNA1 -> 链路箱 H/V -> 暗室接口板 H/V -> 馈源 -> 反射面 -> 标准增益喇叭/转台DUT接口 -> 暗室接口板 DUT -> AMP1 -> 链路箱 SA -> 网分 PORT2 | `CONFigure:LINK H/V, VNA1` + `CONFigure:LINK DUT,AMP1,SA` |
| VNA1 到 SA，H/V 环路，AMP2 开启且 DUT 侧直通 | 网分 PORT1 -> 链路箱 VNA1 -> AMP2 -> 链路箱 H/V -> 暗室接口板 H/V -> 馈源 -> 反射面 -> 标准增益喇叭/转台DUT接口 -> 暗室接口板 DUT -> 链路箱 SA -> 网分 PORT2 | `CONFigure:LINK H/V, AMP2, VNA1` + `CONFigure:LINK DUT,SA` |
| SA-H 馈源侧端口 | 网分 PORT1 -> AUX-E -> 暗室接口板 DUT -> 标准喇叭 -> 反射面 -> 馈源 -> 暗室接口板 H -> 链路箱 H -> 链路箱 SA -> 网分 PORT2，形成不经过 AMP2 的等效回路 | `CONFigure:LINK H, SA` |
| SA-V 馈源侧端口 | 网分 PORT1 -> AUX-E -> 暗室接口板 DUT -> 标准喇叭 -> 反射面 -> 馈源 -> 暗室接口板 V -> 链路箱 V -> 链路箱 SA -> 网分 PORT2，形成不经过 AMP2 的等效回路 | `CONFigure:LINK V, SA` |
| SA-H 馈源侧端口，经过 AMP2 | 网分 PORT1 -> AUX-E -> 暗室接口板 DUT -> 标准喇叭 -> 反射面 -> 馈源 -> 暗室接口板 H -> 链路箱 H -> AMP2 -> 链路箱 SA -> 网分 PORT2，形成经过 AMP2 的等效回路 | `CONFigure:LINK H, AMP2, SA` |
| SA-V 馈源侧端口，经过 AMP2 | 网分 PORT1 -> AUX-E -> 暗室接口板 DUT -> 标准喇叭 -> 反射面 -> 馈源 -> 暗室接口板 V -> 链路箱 V -> AMP2 -> 链路箱 SA -> 网分 PORT2，形成经过 AMP2 的等效回路 | `CONFigure:LINK V, AMP2, SA` |

SG 校准对应关系：

| 校准对象 | 校准时使用的网分闭合环路 | 校准指令 |
|---|---|---|
| SG-H/V，两边直通 | 网分 PORT1 -> 链路箱 SG -> 链路箱 H/V -> 暗室接口板 H/V -> 馈源 -> 反射面 -> 标准增益喇叭/转台DUT接口 -> 暗室接口板 DUT -> 链路箱 VNA2 -> 网分 PORT2 | `CONFigure:LINK H/V, SG` + `CONFigure:LINK DUT, VNA2` |
| SG-H/V，AMP1 开启，发射侧直通 | 网分 PORT1 -> 链路箱 SG -> 链路箱 H/V -> 暗室接口板 H/V -> 馈源 -> 反射面 -> 标准增益喇叭/转台DUT接口 -> 暗室接口板 DUT -> AMP1 -> 链路箱 VNA2 -> 网分 PORT2 | `CONFigure:LINK H/V, SG` + `CONFigure:LINK DUT, AMP1, VNA2` |
| SG-H/V，AMP2 开启，DUT 侧直通 | 网分 PORT1 -> 链路箱 SG -> AMP2 -> 链路箱 H/V -> 暗室接口板 H/V -> 馈源 -> 反射面 -> 标准增益喇叭/转台DUT接口 -> 暗室接口板 DUT -> 链路箱 VNA2 -> 网分 PORT2 | `CONFigure:LINK H/V, AMP2, SG` + `CONFigure:LINK DUT, VNA2` |

上述对应关系拆分为 `LINK-CAL-003` SA 校准和 `LINK-CAL-004` SG 校准；校准逻辑与 `LINK-CAL-002` VNA 链路损耗校准一致，仍使用网分和标准增益喇叭。因为 SA/SG 校准同样由网分测 S21 完成，所以必须形成 PORT1 到 PORT2 的闭合环路：例如 DUT 到 PORT2 的 SA 校准场景，PORT1 侧需要先切 `VNA1 -> H/V`。

禁止/注意：

- `LINK-CAL-003` 的 VNA1 到 SA 校准必须同时配置 VNA1 到 H/V 的发射半链路和 DUT 到 SA 的接收半链路；该闭合环路扣除 VNA FEED 后得到 DUT 参考面至 SA 端口的等效接收链路损耗。
- `LINK-CAL-003` 的 SA 主输出校准使用 AUX-E 辅助线：AUX-E 连接网分 PORT1 和转台DUT接口，接收侧按 DUT 直通或 DUT->AMP1 切到链路箱 SA，最后回到网分 PORT2。
- `LINK-CAL-004` 的 SG 校准必须同时配置 SG 到 H/V 的发射半链路和 DUT 到 VNA2 的接收半链路；三种工况分别为两边直通、AMP1 开启且发射侧直通、AMP2 开启且 DUT 侧直通。
- VNA 链路损耗校准主链路使用标准增益喇叭，不是接上 DUT 的测试链路。

### 模板 B：LINK-CAL-002 AUX-D 回传段校准链路

用途：作为 `LINK-CAL-002` 的子步骤，执行转台DUT到VNA的损耗校准。校准时使用第四根辅助线 AUX-D，先直连 VNA1 和 VNA2 进行 AUX-D 单独测试；随后将 AUX-D 接到转台DUT接口作为转台DUT侧参考，同时接收侧仍需要通过链路箱切到 `DUT -> VNA2`。

操作步骤：

1. AUX-D 单独测试：人工接入 AUX-D，直连 VNA1 和 VNA2。
2. 用网分测量 AUX-D 本身响应，作为辅助线修正参考。
3. 转台DUT到VNA的损耗校准发射侧：将 AUX-D 从 VNA2 侧改接到转台DUT接口。
4. 转台DUT到VNA的损耗校准接收侧：切换 DUT 直通到 VNA2。
5. 不切换 H/V 极化链路。
6. 不经过 AMP2。

指令组合：

| 操作 | 链路箱指令 |
|---|---|
| AUX-D 单独测试：VNA1 直连 VNA2 | 不下发 |
| 转台DUT到VNA的损耗校准发射侧：VNA1 通过 AUX-D 接到转台DUT接口 | 不下发 |
| 转台DUT到VNA的损耗校准接收侧：DUT 直通到 VNA2 | `CONFigure:LINK DUT, VNA2` |

禁止/注意：

- 转台DUT到VNA的损耗校准不使用 `CONFigure:LINK H, VNA1` 或 `CONFigure:LINK V, VNA1`。
- 转台DUT到VNA的损耗校准不使用 `CONFigure:LINK H, AMP2, VNA1` 或 `CONFigure:LINK V, AMP2, VNA1`。
- 执行 AUX-D 单独测试前，需要确认 AUX-D 已直连 VNA1 和 VNA2。
- 执行转台DUT到VNA的损耗校准前，需要确认 AUX-D 已从 VNA2 侧改接到转台DUT接口。

### 模板 C：DUT VNA 测试细分链路

用途：接上 DUT 后执行 VNA 相关 TX&RX 测试。接上 DUT 时，不下发网分 `DUT -> VNA2` 接收链路，只配置 H/V 馈源端口到 VNA1。由于 AMP2 为单向放大器，只有从馈源接收信号的场景才选择是否经过 AMP2；H/V 后续物理路径为链路箱 H/V、暗室接口板 H/V、馈源、反射面到 DUT。该模板按测试项语义细分，命令组合相同，但记录和 UI 展示应保留测试项名称。

适用测试项：

- `LINK-TXR-001` DUT 通道校准
- `LINK-TXR-002` 方向图测试
- `LINK-TXR-003` 有源增益测试
- `LINK-TXR-004` 天线板 EIRP 测试

细分测试项：

| 测试项 ID | 测试项 | 馈源接收直通用途 | 馈源接收经过 AMP2 用途 |
|---|---|---|---|
| `LINK-TXR-001` | DUT 通道校准 | DUT 通道校准直通链路 | DUT 通道校准含 TX 放大器链路 |
| `LINK-TXR-002` | 方向图测试 | 方向图直通链路 | 方向图含 TX 放大器链路 |
| `LINK-TXR-003` | 有源增益测试 | 有源增益直通链路 | 有源增益含 TX 放大器链路 |
| `LINK-TXR-004` | 天线板 EIRP 测试 | 天线板 EIRP 直通链路 | 天线板 EIRP 含 TX 放大器链路 |

操作步骤：

1. 不切换 `DUT -> VNA2`。
2. 根据测试极化选择 H 或 V。
3. 根据测试配置选择 TX 是否经过 AMP2。

细分指令组合：

| 馈源接收路径 | H 极化指令 | V 极化指令 |
|---|---|---|
| 直通 | `CONFigure:LINK H, VNA1` | `CONFigure:LINK V, VNA1` |
| 经过 AMP2 | `CONFigure:LINK H, AMP2, VNA1` | `CONFigure:LINK V, AMP2, VNA1` |

禁止/注意：

- 接上 DUT 时，DUT TX&RX 通用测试链路不使用 `CONFigure:LINK DUT, VNA2`。

### 模板 D：SG/SA 链路

用途：使用信号源和频谱仪的测试链路。DUT 侧切到 SA，TX 侧按 H/V 极化切到 SG；SG 经链路箱 H/V、暗室接口板 H/V、馈源、反射面到 DUT，DUT 接收侧经暗室接口板 DUT、AMP1 回到 SA。

适用测试项：

- `LINK-GT-001` G/T 测试
- `LINK-SYS-001` 整机发射测试

操作步骤：

1. 切换 DUT 侧到 SA。
2. 根据测试极化切换 H 或 V 到 SG。
3. 不经过 AMP2。

指令组合：

| 极化 | 链路箱指令 |
|---|---|
| H | `CONFigure:LINK DUT, AMP1, SA` + `CONFigure:LINK H, SG` |
| V | `CONFigure:LINK DUT, AMP1, SA` + `CONFigure:LINK V, SG` |

禁止/注意：

- G/T 测试中信号源发射、频谱仪接收。由于放大器为单向器件，G/T 不提供 TX 加放大器选项。
- 整机发射测试中信号源不输出发射功率，发射功率由 DUT 产生，频谱仪负责接收。
- 本模板不使用 `CONFigure:LINK H, AMP2, SG` 或 `CONFigure:LINK V, AMP2, SG`。

### 模板 E：SG-only 链路

用途：整机接收测试。信号源经链路箱 H/V、暗室接口板 H/V、馈源、反射面发射测试信号，DUT 负责接收，频谱仪不参与。

适用测试项：

- `LINK-SYS-002` 整机接收测试

操作步骤：

1. 不切换 DUT 到 SA。
2. 根据测试极化切换 H 或 V 到 SG。

指令组合：

| 极化 | 链路箱指令 |
|---|---|
| H | `CONFigure:LINK H, SG` |
| V | `CONFigure:LINK V, SG` |

禁止/注意：

- 整机接收测试不使用 `CONFigure:LINK DUT, AMP1, SA`。
- 整机接收测试不使用频谱仪。

## 测试项操作定义

### LINK-CAL-001：暗室内部链路校准

- 仪表角色：VNA S21 闭环。
- DUT/校准件状态：使用三根 3M 辅助线直接连接网分、转台DUT接口与暗室接口板 H/V/DUT；三根辅助线需先独立测试。
- 可选参数：无；测量顺序固定为辅助线独立测试、DUT-H、DUT-V、DUT 内部段。
- 链路模板：模板 A0。
- 目的：校准暗室接口板 H/V 到 DUT 端口之间的暗室内部链路损耗，以及转台DUT接口到暗室接口板 DUT 的 DUT 内部段损耗。
- 具体指令：

| 测量顺序 | 外部接线 | 链路箱指令 |
|---|---|---|
| 0：辅助线独立测试 | 三根 3M 辅助线分别直连网分 PORT1 与 PORT2，测得 `L_AUX_A`、`L_AUX_B`、`L_AUX_C` | 不下发 |
| 1：DUT-H | 网分 PORT1 -> AUX-A -> 暗室接口板 H；暗室接口板 DUT -> AUX-C -> 网分 PORT2 | 不下发 |
| 2：DUT-V | 网分 PORT1 -> AUX-B -> 暗室接口板 V；暗室接口板 DUT -> AUX-C -> 网分 PORT2 | 不下发 |
| 3：DUT 内部段 | 网分 PORT1 -> AUX-A -> 转台DUT接口；暗室接口板 DUT -> AUX-C -> 网分 PORT2 | 不下发 |

最终输出参数（重点）：

| 参数 | 输入端口/参考面 | 输出端口/参考面 | 路径 | 计算公式 |
|---|---|---|---|---|
| `L_CH_INT_H` | `CP-H` | `CP-DUT` | 暗室内部 H 链路 | `L_CH_INT_H = -S21_CH_INT_H_RAW - L_AUX_A - L_AUX_C` |
| `L_CH_INT_V` | `CP-V` | `CP-DUT` | 暗室内部 V 链路 | `L_CH_INT_V = -S21_CH_INT_V_RAW - L_AUX_B - L_AUX_C` |
| `L_CH_INT_DUT` | `TD` | `CP-DUT` | DUT 内部段 | `L_CH_INT_DUT = -S21_CH_INT_DUT_RAW - L_AUX_A - L_AUX_C` |
| `L_CH_INT_FEED_H` | `FH` | `TD` / `DUT_REF` | H 馈源到 DUT 参考面 | `L_CH_INT_FEED_H = L_CH_INT_H - L_CH_INT_DUT` |
| `L_CH_INT_FEED_V` | `FV` | `TD` / `DUT_REF` | V 馈源到 DUT 参考面 | `L_CH_INT_FEED_V = L_CH_INT_V - L_CH_INT_DUT` |

临时/追溯参数：

| 参数 | 输入端口/参考面 | 输出端口/参考面 | 含义 |
|---|---|---|---|
| `L_AUX_A` | `P1` | `P2` | AUX-A 自身损耗，`L_AUX_A = -S21_AUX_A`。 |
| `L_AUX_B` | `P1` | `P2` | AUX-B 自身损耗，`L_AUX_B = -S21_AUX_B`。 |
| `L_AUX_C` | `P1` | `P2` | AUX-C 自身损耗，`L_AUX_C = -S21_AUX_C`。 |
| `S21_CH_INT_H_RAW` | `P1/AUX-A/CP-H` | `CP-DUT/AUX-C/P2` | DUT-H 原始闭合测量。 |
| `S21_CH_INT_V_RAW` | `P1/AUX-B/CP-V` | `CP-DUT/AUX-C/P2` | DUT-V 原始闭合测量。 |
| `S21_CH_INT_DUT_RAW` | `P1/AUX-A/TD` | `CP-DUT/AUX-C/P2` | DUT 内部段原始闭合测量。 |

说明：`L_CH_INT_FEED_H/V` 由 `L_CH_INT_H/V` 扣除 `L_CH_INT_DUT` 得到；三者均已扣除对应 AUX 辅助线损耗。

### LINK-CAL-002：VNA 链路损耗校准

- 仪表角色：VNA 发射 + VNA 接收。
- DUT/校准件状态：主链路校准时转台DUT接口换标准增益喇叭；回传段校准时使用 AUX-D 接转台DUT接口。
- 可选参数：主链路校准支持极化 H/V，并按三种 VNA2 回传/馈源路径组合执行：两边直通、AMP1 开启且馈源侧直通、AMP2 开启且 DUT 侧直通。
- 链路模板：模板 A + 模板 B。
- 目的：校准 VNA 主测试链路损耗，并在同一校准项内用 AUX-D 得到转台DUT接口到 VNA2 的回传链路损耗。
- 具体指令：

| 阶段/条件 | 链路箱指令 |
|---|---|
| AUX-D 单独测试：VNA1 直连 VNA2 | 不下发 |
| AUX-D 接转台DUT接口：VNA1 通过 AUX-D 接到转台DUT接口 | 不下发 |
| AUX-D 接转台DUT接口：DUT 直通到 VNA2 | `CONFigure:LINK DUT, VNA2` |
| AUX-D 接转台DUT接口：DUT 经 AMP1 到 VNA2 | `CONFigure:LINK DUT, AMP1, VNA2` |
| 主链路 H，两边直通 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H, VNA1` |
| 主链路 V，两边直通 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK V, VNA1` |
| 主链路 H，AMP1 开启，馈源侧直通 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK H, VNA1` |
| 主链路 V，AMP1 开启，馈源侧直通 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK V, VNA1` |
| 主链路 H，AMP2 开启，DUT 侧直通 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK H, AMP2, VNA1` |
| 主链路 V，AMP2 开启，DUT 侧直通 | `CONFigure:LINK DUT, VNA2` + `CONFigure:LINK V, AMP2, VNA1` |

最终输出参数（重点）：

| 参数 | 输入端口/参考面 | 输出端口/参考面 | 极化/路径 | 计算公式 |
|---|---|---|---|---|
| `L_VNA_FEED_H` / `L_VNA_FEED_V` | `LB-VNA1` | `DUT_REF` / `FH/FV` | `POL-H/V`，两边直通 | `L_VNA_FEED_H/V = L_VNA_H/V - L_DUT_VNA` |
| `L_VNA_FEED_H_AMP1` / `L_VNA_FEED_V_AMP1` | `LB-VNA1` | `DUT_REF` / `FH/FV` | `POL-H/V`，AMP1 开启，馈源侧直通 | `L_VNA_FEED_H/V_AMP1 = L_VNA_H/V_AMP1 - L_DUT_VNA_AMP1` |
| `L_VNA_FEED_H_AMP2` / `L_VNA_FEED_V_AMP2` | `LB-VNA1` | `DUT_REF` / `FH/FV` | `POL-H/V`，AMP2 开启，DUT 侧直通 | `L_VNA_FEED_H/V_AMP2 = L_VNA_H/V_AMP2 - L_DUT_VNA` |
| `L_DUT_VNA` | `TD` | `LB-VNA2` | 回传段，DUT 侧直通 | `L_DUT_VNA = -S21_DUT_VNA_RAW - L_AUX_D` |
| `L_DUT_VNA_AMP1` | `TD` | `LB-VNA2` | 回传段，经 `AMP1` | `L_DUT_VNA_AMP1 = -S21_DUT_VNA_AMP1_RAW - L_AUX_D` |

临时/追溯参数：

| 参数 | 输入端口/参考面 | 输出端口/参考面 | 极化/路径 | 含义/公式 |
|---|---|---|---|---|
| `L_AUX_D` | `P1` | `P2` | AUX-D | AUX-D 自身损耗，`L_AUX_D = -S21_AUX_D`。 |
| `L_VNA_H` / `L_VNA_V` | `LB-VNA1` | `LB-VNA2` | `POL-H/V`，两边直通，含回传段 | VNA 主链路闭合损耗。 |
| `L_VNA_H_AMP1` / `L_VNA_V_AMP1` | `LB-VNA1` | `LB-VNA2` | `POL-H/V`，AMP1 开启，馈源侧直通，含 AMP1 回传段 | VNA 主链路闭合损耗，用于校验/计算 AMP1 回传工况。 |
| `L_VNA_H_AMP2` / `L_VNA_V_AMP2` | `LB-VNA1` | `LB-VNA2` | `POL-H/V`，AMP2 开启，DUT 侧直通，含直通回传段 | 经过 AMP2 的 VNA 主链路闭合损耗。 |

说明：三种工况分别对应“两边直通”“AMP1 开启、馈源侧直通”“AMP2 开启、DUT 侧直通”。`L_VNA_FEED_*` 必须扣除同一工况下的 DUT 到 VNA2 回传段；不默认组合 AMP1 与 AMP2 同时开启。

### LINK-CAL-003：SA 校准

- 仪表角色：VNA S21 闭环。
- DUT/校准件状态：主输出校准时使用 AUX-E 接转台DUT接口，网分 PORT2 接链路箱 SA；VNA1 到 SA 一致性校验时，转台DUT接口换标准增益喇叭，网分 PORT1 接链路箱 VNA1，网分 PORT2 接链路箱 SA。
- 可选参数：AUX-E 接转台DUT接口时可选 DUT 侧直通或经过 AMP1；VNA1 到 SA 一致性校验支持极化 H/V，并覆盖三种工况（两边直通、AMP1 开启且馈源侧直通、AMP2 开启且 DUT 侧直通）。
- 链路模板：SA 校准链路。
- 目的：校准 DUT 参考面至链路箱 SA 端口的等效接收链路损耗；AUX-E 接转台DUT接口的结果作为主输出，VNA1 到 SA 三种工况只作为一致性校验。
- 具体指令：

| 等效校准对象 | 链路箱指令 |
|---|---|
| AUX-E 单独测试：网分 PORT1 直连 AUX-E 到网分 PORT2 | 不下发 |
| AUX-E 接转台DUT接口：DUT 直通到 SA | `CONFigure:LINK DUT,SA` |
| AUX-E 接转台DUT接口：DUT 经 AMP1 到 SA | `CONFigure:LINK DUT,AMP1,SA` |
| VNA1 到 SA，H/V 环路，两边直通 | `CONFigure:LINK H/V, VNA1` + `CONFigure:LINK DUT,SA` |
| VNA1 到 SA，H/V 环路，AMP1 开启且馈源侧直通 | `CONFigure:LINK H/V, VNA1` + `CONFigure:LINK DUT,AMP1,SA` |
| VNA1 到 SA，H/V 环路，AMP2 开启且 DUT 侧直通 | `CONFigure:LINK H/V, AMP2, VNA1` + `CONFigure:LINK DUT,SA` |

最终输出参数（重点）：

| 参数 | 输入端口/参考面 | 输出端口 | 极化/路径 | 计算公式 |
|---|---|---|---|---|
| `L_DUT_SA` | `DUT_REF` | `LB-SA` | DUT 侧直通 | `L_DUT_SA = T_AUXE_DUT_SA - L_AUX_E` |
| `L_DUT_SA_AMP1` | `DUT_REF` | `LB-SA` | DUT 侧经过 `AMP1` | `L_DUT_SA_AMP1 = T_AUXE_DUT_SA_AMP1 - L_AUX_E` |

临时/追溯参数：

| 参数 | 输入端口/参考面 | 输出端口 | 极化/路径 | 含义/公式 |
|---|---|---|---|---|
| `L_AUX_E` | `P1` | `CP-DUT` | AUX-E | 辅助线损耗，`L_AUX_E = -S21_AUX_E`。 |
| `T_AUXE_DUT_SA` | `P1/AUX-E/DUT_REF` | `LB-SA/P2` | DUT 侧直通 | AUX-E 接转台DUT接口的直通接收闭合环路，`T_AUXE_DUT_SA = -S21_AUXE_DUT_SA_RAW`。 |
| `T_AUXE_DUT_SA_AMP1` | `P1/AUX-E/DUT_REF` | `LB-SA/P2` | DUT 侧经过 `AMP1` | AUX-E 接转台DUT接口的 AMP1 接收闭合环路，`T_AUXE_DUT_SA_AMP1 = -S21_AUXE_DUT_SA_AMP1_RAW`。 |
| `T_VNA1_SA_H` / `T_VNA1_SA_V` | `LB-VNA1` | `LB-SA` | `POL-H/V`，两边直通 | 一致性校验量，`T_VNA1_SA_H/V ≈ L_VNA_FEED_H/V + L_DUT_SA`。 |
| `T_VNA1_SA_H_AMP1` / `T_VNA1_SA_V_AMP1` | `LB-VNA1` | `LB-SA` | `POL-H/V`，AMP1 开启且馈源侧直通 | 一致性校验量，`T_VNA1_SA_H/V_AMP1 ≈ L_VNA_FEED_H/V + L_DUT_SA_AMP1`。 |
| `T_VNA1_SA_H_AMP2` / `T_VNA1_SA_V_AMP2` | `LB-VNA1` | `LB-SA` | `POL-H/V`，AMP2 开启且 DUT 侧直通 | 一致性校验量，`T_VNA1_SA_H/V_AMP2 ≈ L_VNA_FEED_H/V_AMP2 + L_DUT_SA`。 |

说明：`L_DUT_SA` / `L_DUT_SA_AMP1` 由 AUX-E 接转台DUT接口直接得到，是 LINK-CAL-003 的主输出；VNA1 到 SA 三种工况分别为“两边直通”“AMP1 开启、馈源侧直通”“AMP2 开启、DUT 侧直通”，只作为一致性校验，不再作为主计算来源。

### LINK-CAL-004：SG 校准

- 仪表角色：VNA S21 闭环。
- DUT/校准件状态：转台DUT接口换标准增益喇叭；网分 PORT1 接链路箱 SG，网分 PORT2 接链路箱 VNA2。
- 可选参数：极化 H/V；三种工况：两边直通、AMP1 开启且发射侧直通、AMP2 开启且 DUT 侧直通。
- 链路模板：SG 校准链路。
- 目的：校准链路箱 SG 物理端口到 DUT 参考面的等效发射链路损耗；为便于自动化，本校准项内使用 AUX-F 重复测回传段，不跨项引用 LINK-CAL-002 的 AUX-D 结果。
- 具体指令：

| 条件 | 链路箱指令 |
|---|---|
| AUX-F 单独测试 | 不下发；网分 PORT1 → AUX-F → 网分 PORT2 |
| AUX-F 接转台DUT接口，VNA2 直通接收 | `CONFigure:LINK DUT, VNA2` |
| AUX-F 接转台DUT接口，VNA2 经 AMP1 接收 | `CONFigure:LINK DUT, AMP1, VNA2` |
| H/V，两边直通 | `CONFigure:LINK H/V, SG` + `CONFigure:LINK DUT, VNA2` |
| H/V，AMP1 开启，发射侧直通 | `CONFigure:LINK H/V, SG` + `CONFigure:LINK DUT, AMP1, VNA2` |
| H/V，AMP2 开启，DUT 侧直通 | `CONFigure:LINK H/V, AMP2, SG` + `CONFigure:LINK DUT, VNA2` |

最终输出参数（重点）：

| 参数 | 输入端口/参考面 | 输出端口/参考面 | 极化/路径 | 计算公式 |
|---|---|---|---|---|
| `L_DUT_VNA_F` | `TD` | `LB-VNA2` | LINK-CAL-004 回传段，DUT 侧直通 | `L_DUT_VNA_F = -S21_DUT_VNA_F_RAW - L_AUX_F` |
| `L_DUT_VNA_F_AMP1` | `TD` | `LB-VNA2` | LINK-CAL-004 回传段，经 `AMP1` | `L_DUT_VNA_F_AMP1 = -S21_DUT_VNA_F_AMP1_RAW - L_AUX_F` |
| `L_SG_DUT_H` / `L_SG_DUT_V` | `LB-SG` | `DUT_REF` | `POL-H/V`，两边直通 | `L_SG_DUT_H/V = T_SG_H/V - L_DUT_VNA_F` |
| `L_SG_DUT_H_AMP1` / `L_SG_DUT_V_AMP1` | `LB-SG` | `DUT_REF` | `POL-H/V`，AMP1 开启，发射侧直通 | `L_SG_DUT_H/V_AMP1 = T_SG_H/V_AMP1 - L_DUT_VNA_F_AMP1` |
| `L_SG_DUT_H_AMP2` / `L_SG_DUT_V_AMP2` | `LB-SG` | `DUT_REF` | `POL-H/V`，AMP2 开启，DUT 侧直通 | `L_SG_DUT_H/V_AMP2 = T_SG_H/V_AMP2 - L_DUT_VNA_F` |

临时/追溯参数：

| 参数 | 输入端口/参考面 | 输出端口/参考面 | 极化/路径 | 含义/公式 |
|---|---|---|---|---|
| `L_AUX_F` | `P1` | `P2` | AUX-F | AUX-F 自身损耗，`L_AUX_F = -S21_AUX_F`。 |
| `T_SG_H` / `T_SG_V` | `LB-SG` | `LB-VNA2` | `POL-H/V`，两边直通，含直通回传段 | SG 校准完整闭合环路临时损耗，`T_SG_H/V = -S21_SG_H/V_RAW`。 |
| `T_SG_H_AMP1` / `T_SG_V_AMP1` | `LB-SG` | `LB-VNA2` | `POL-H/V`，AMP1 开启，含 AMP1 回传段 | SG 校准 AMP1 闭合环路临时损耗，`T_SG_H/V_AMP1 = -S21_SG_H/V_AMP1_RAW`。 |
| `T_SG_H_AMP2` / `T_SG_V_AMP2` | `LB-SG` | `LB-VNA2` | `POL-H/V`，AMP2 开启，含直通回传段 | SG 校准 AMP2 闭合环路临时损耗，`T_SG_H/V_AMP2 = -S21_SG_H/V_AMP2_RAW`。 |

说明：`T_SG_*` 不能直接作为 SG 发射链路最终路损；它包含 LINK-CAL-004 内通过 AUX-F 重复测得的 DUT 到 VNA2 回传段。两边直通和 AMP2 工况扣除 `L_DUT_VNA_F`，AMP1 工况扣除 `L_DUT_VNA_F_AMP1`。

### LINK-TXR-001：DUT 通道校准

- 仪表角色：VNA。
- DUT 状态：接上 DUT。
- 可选参数：极化 H/V；TX 是否经过 AMP2。
- 链路模板：模板 C。
- 具体指令：

| 条件 | 链路箱指令 |
|---|---|
| H，不经过 AMP2 | `CONFigure:LINK H, VNA1` |
| V，不经过 AMP2 | `CONFigure:LINK V, VNA1` |
| H，经过 AMP2 | `CONFigure:LINK H, AMP2, VNA1` |
| V，经过 AMP2 | `CONFigure:LINK V, AMP2, VNA1` |

### LINK-TXR-002：方向图测试

- 仪表角色：VNA。
- DUT 状态：接上 DUT。
- 可选参数：极化 H/V；TX 是否经过 AMP2。
- 链路模板：模板 C。
- 具体指令：

| 条件 | 链路箱指令 |
|---|---|
| H，不经过 AMP2 | `CONFigure:LINK H, VNA1` |
| V，不经过 AMP2 | `CONFigure:LINK V, VNA1` |
| H，经过 AMP2 | `CONFigure:LINK H, AMP2, VNA1` |
| V，经过 AMP2 | `CONFigure:LINK V, AMP2, VNA1` |

### LINK-TXR-003：有源增益测试

- 仪表角色：VNA。
- DUT 状态：接上 DUT。
- 可选参数：极化 H/V；TX 是否经过 AMP2。
- 链路模板：模板 C。
- 具体指令：

| 条件 | 链路箱指令 |
|---|---|
| H，不经过 AMP2 | `CONFigure:LINK H, VNA1` |
| V，不经过 AMP2 | `CONFigure:LINK V, VNA1` |
| H，经过 AMP2 | `CONFigure:LINK H, AMP2, VNA1` |
| V，经过 AMP2 | `CONFigure:LINK V, AMP2, VNA1` |

### LINK-TXR-004：天线板 EIRP 测试

- 仪表角色：VNA。
- DUT 状态：接上 DUT。
- 可选参数：极化 H/V；TX 是否经过 AMP2。
- 链路模板：模板 C。
- 具体指令：

| 条件 | 链路箱指令 |
|---|---|
| H，不经过 AMP2 | `CONFigure:LINK H, VNA1` |
| V，不经过 AMP2 | `CONFigure:LINK V, VNA1` |
| H，经过 AMP2 | `CONFigure:LINK H, AMP2, VNA1` |
| V，经过 AMP2 | `CONFigure:LINK V, AMP2, VNA1` |

### LINK-GT-001：G/T 测试

- 仪表角色：SG 发射 + SA 接收。
- DUT 状态：DUT 接收侧切到 SA。
- 可选参数：极化 H/V。
- 链路模板：模板 D。
- 注意：不允许 TX 经过 AMP2。
- 具体指令：

| 极化 | 链路箱指令 |
|---|---|
| H | `CONFigure:LINK DUT, AMP1, SA` + `CONFigure:LINK H, SG` |
| V | `CONFigure:LINK DUT, AMP1, SA` + `CONFigure:LINK V, SG` |

### LINK-SYS-001：整机发射测试

- 仪表角色：SA 接收；SG 接入但不输出发射功率。
- DUT 状态：DUT 自身产生发射功率。
- 可选参数：极化 H/V。
- 链路模板：模板 D。
- 注意：不允许 TX 经过 AMP2。
- 具体指令：

| 极化 | 链路箱指令 |
|---|---|
| H | `CONFigure:LINK DUT, AMP1, SA` + `CONFigure:LINK H, SG` |
| V | `CONFigure:LINK DUT, AMP1, SA` + `CONFigure:LINK V, SG` |

### LINK-SYS-002：整机接收测试

- 仪表角色：SG 输出测试信号。
- DUT 状态：DUT 自身接收。
- 可选参数：极化 H/V。
- 链路模板：模板 E。
- 注意：SA 不参与，不切换 DUT 到 SA。
- 具体指令：

| 极化 | 链路箱指令 |
|---|---|
| H | `CONFigure:LINK H, SG` |
| V | `CONFigure:LINK V, SG` |

## 后续迁移

- 为当前链路状态建立结构化 model，供日志、UI 和扫描记录复用。
- 为校准结果建立 `cal_params[]` 数据结构，保存 `L_*` 损耗参数、频点数组和原始 `S21_*` 数据。








