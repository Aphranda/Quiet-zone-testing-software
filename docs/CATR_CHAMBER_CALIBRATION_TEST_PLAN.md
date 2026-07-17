# 链路管理设计

Status: Active
Domain: LINK
Canonical: `docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.md`
Related: `docs/architecture_migration_plan.md`, `docs/INSTRUMENT_MANAGEMENT_DESIGN.md`
Last updated: 2026-07-17

本文档定义开关箱链路操作、历史 S 参数兼容路由、开关箱 profile 和链路控制 UI/ViewModel 的边界。

## 职责

- 按极化切换源端链路：`H,VNA1`、`V,VNA1`。
- 按 DUT 目标切换仪表链路：`DUT,AMP1,VNA2`、`DUT,AMP1,SA`。
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
- `CONFigure:LINK H,...` / `CONFigure:LINK V,...` 切换的是链路箱到暗室接口板的 H/V 极化端口；后续物理路径为“链路箱 H/V -> 暗室接口板 H/V -> 馈源 -> 反射面 -> 标准增益喇叭或 DUT”。DUT/标准喇叭接收侧再经“暗室接口板 DUT -> AMP1”回到链路箱。
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
| `S21_*` | 网分原始 S21 测量值 | 单位 dB，用于追溯和复算，不直接替代 `L_*`。 |
| `value_db` | 参与计算的校准后损耗值 | 按频点保存。 |
| `raw_s21_db` | 原始 S21 记录 | 用于校准结果追溯。 |
| `freq_hz[]` | 频点数组 | 所有损耗参数应按频点保存。 |

核心校准参数简称：

| 参数 | 含义 | 来源 |
|---|---|---|
| `L_AUX_A` / `L_AUX_B` / `L_AUX_C` | 三根 3M 辅助线自身损耗 | `LINK-CAL-001` 辅助线独立测试 |
| `L_CH_INT_H` / `L_CH_INT_V` / `L_CH_INT_DUT` | 暗室内部 H、V、DUT 段链路损耗，扣除对应 3M 辅助线 | `LINK-CAL-001` 暗室内部链路校准 |
| `L_CH_INT_FEED_H` / `L_CH_INT_FEED_V` | 馈源发射到转台DUT接口/DUT 端面的派生损耗 | `L_CH_INT_H/V - L_CH_INT_DUT` |
| `L_VNA_H` / `L_VNA_V` / `L_VNA_H_AMP2` / `L_VNA_V_AMP2` | VNA 测试链路等效损耗 | `LINK-CAL-002` VNA 链路损耗校准 |
| `L_DUT_VNA` | 转台DUT到VNA的损耗 | `LINK-CAL-002` AUX-D 回传段校准 |
| `L_SA_H` / `L_SA_V` / `L_SA_H_AMP2` / `L_SA_V_AMP2` | 频谱仪接收链路等效损耗 | `LINK-CAL-003` SA 校准 |
| `L_SG_H` / `L_SG_V` | 信号源发射链路等效损耗 | `LINK-CAL-004` SG 校准 |

端口命名约定：

- `网分 PORT1 / PORT2`：外部网分真实端口，校准时可按项目临时改接。
- `VNA1 / VNA2 / SG / SA / H / V / DUT`：链路箱或暗室接口板物理端口名，需按上下文区分。

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
| `LINK-CAL-002` | VNA 链路损耗校准 | VNA 发射 + VNA 接收 | 转台DUT接口换标准增益喇叭；另用 AUX-D 校准转台DUT到 VNA2 回传段 | 极化 H/V；TX 是否经过 AMP2；AUX-D 阶段不需要极化且不经过 AMP2 | 校准 VNA 链路 + AUX-D 回传段 |
| `LINK-CAL-003` | SA 校准 | VNA S21 闭环 | 网分 PORT1 接链路箱 VNA1，网分 PORT2 接链路箱 SA | 极化 H/V；PORT1 侧经 VNA1->H/V 发射，PORT2 侧经 DUT->SA 接收 | SA 校准链路 |
| `LINK-CAL-004` | SG 校准 | VNA S21 闭环 | 网分 PORT1 接链路箱 SG，网分 PORT2 接链路箱 VNA2 | 极化 H/V；PORT1 侧经 SG->H/V 发射，PORT2 侧经 DUT->VNA2 接收 | SG 校准链路 |
| `LINK-TXR-001` | DUT 通道校准 | VNA | 接上 DUT；不使用 `DUT -> VNA2` | 极化 H/V；馈源接收方向是否经过 AMP2 | DUT VNA：通道校准链路 |
| `LINK-TXR-002` | 方向图测试 | VNA | 接上 DUT；不使用 `DUT -> VNA2` | 极化 H/V；馈源接收方向是否经过 AMP2 | DUT VNA：方向图链路 |
| `LINK-TXR-003` | 有源增益测试 | VNA | 接上 DUT；不使用 `DUT -> VNA2` | 极化 H/V；馈源接收方向是否经过 AMP2 | DUT VNA：有源增益链路 |
| `LINK-TXR-004` | 天线板 EIRP 测试 | VNA | 接上 DUT；不使用 `DUT -> VNA2` | 极化 H/V；馈源接收方向是否经过 AMP2 | DUT VNA：天线板 EIRP 链路 |
| `LINK-GT-001` | G/T 测试 | SG 发射 + SA 接收 | DUT 接收侧切到 SA | 极化 H/V；不允许 AMP2 | SG/SA 链路 |
| `LINK-SYS-001` | 整机发射测试 | SA 接收；SG 不输出功率 | DUT 发射功率，SA 接收 | 极化 H/V；不允许 AMP2 | SG/SA 链路 |
| `LINK-SYS-002` | 整机接收测试 | SG 输出测试信号 | DUT 自身接收；SA 不参与 | 极化 H/V；不允许 AMP2 | SG-only 链路 |

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

### 模板 A：链路损耗校准 VNA 链路

用途：用网分执行链路损耗校准。校准时将 转台DUT接口替换为标准增益喇叭。即使正式测试链路使用 SA 或 SG，其损耗也由网分进行等效校准。

操作步骤：

1. 切换标准增益喇叭接收侧到 VNA2。
2. 根据极化切换 TX 侧到 VNA1；VNA1 经链路箱 H/V、暗室接口板 H/V、馈源、反射面到标准增益喇叭。
3. 如果校准包含 TX 放大器路径，则 TX 侧经过 AMP2；否则直连 VNA1。

指令组合：

| 极化 | TX 放大器 | 链路箱指令 |
|---|---|---|
| H | 不经过 AMP2 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK H, VNA1` |
| V | 不经过 AMP2 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK V, VNA1` |
| H | 经过 AMP2 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK H, AMP2, VNA1` |
| V | 经过 AMP2 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK V, AMP2, VNA1` |

SA 校准对应关系：

| 校准对象 | 校准时使用的网分闭合环路 | 校准指令 |
|---|---|---|
| H 发射，经 DUT 到 SA | 网分 PORT1 -> 链路箱 VNA1 -> 链路箱 H -> 暗室接口板 H -> 馈源 -> 反射面 -> 标准增益喇叭/转台DUT接口 -> 暗室接口板 DUT -> AMP1 -> 链路箱 SA -> 网分 PORT2 | `CONFigure:LINK H, VNA1` + `CONFigure:LINK DUT, AMP1, SA` |
| V 发射，经 DUT 到 SA | 网分 PORT1 -> 链路箱 VNA1 -> 链路箱 V -> 暗室接口板 V -> 馈源 -> 反射面 -> 标准增益喇叭/转台DUT接口 -> 暗室接口板 DUT -> AMP1 -> 链路箱 SA -> 网分 PORT2 | `CONFigure:LINK V, VNA1` + `CONFigure:LINK DUT, AMP1, SA` |
| SA-H 馈源侧端口 | 网分 PORT1 临时接暗室接口板 H 参考端 -> 链路箱 H -> 链路箱 SA -> 网分 PORT2 | `CONFigure:LINK H, SA` |
| SA-V 馈源侧端口 | 网分 PORT1 临时接暗室接口板 V 参考端 -> 链路箱 V -> 链路箱 SA -> 网分 PORT2 | `CONFigure:LINK V, SA` |
| SA-H 馈源侧端口，经过 AMP2 | 网分 PORT1 临时接暗室接口板 H 参考端 -> 链路箱 H -> AMP2 -> 链路箱 SA -> 网分 PORT2 | `CONFigure:LINK H, AMP2, SA` |
| SA-V 馈源侧端口，经过 AMP2 | 网分 PORT1 临时接暗室接口板 V 参考端 -> 链路箱 V -> AMP2 -> 链路箱 SA -> 网分 PORT2 | `CONFigure:LINK V, AMP2, SA` |

SG 校准对应关系：

| 校准对象 | 校准时使用的网分闭合环路 | 校准指令 |
|---|---|---|
| SG-H 端口 | 网分 PORT1 -> 链路箱 SG -> 链路箱 H -> 暗室接口板 H -> 馈源 -> 反射面 -> 标准增益喇叭/转台DUT接口 -> 暗室接口板 DUT -> AMP1 -> 链路箱 VNA2 -> 网分 PORT2 | `CONFigure:LINK H, SG` + `CONFigure:LINK DUT, AMP1, VNA2` |
| SG-V 端口 | 网分 PORT1 -> 链路箱 SG -> 链路箱 V -> 暗室接口板 V -> 馈源 -> 反射面 -> 标准增益喇叭/转台DUT接口 -> 暗室接口板 DUT -> AMP1 -> 链路箱 VNA2 -> 网分 PORT2 | `CONFigure:LINK V, SG` + `CONFigure:LINK DUT, AMP1, VNA2` |

上述对应关系拆分为 `LINK-CAL-003` SA 校准和 `LINK-CAL-004` SG 校准；校准逻辑与 `LINK-CAL-002` VNA 链路损耗校准一致，仍使用网分和标准增益喇叭。因为 SA/SG 校准同样由网分测 S21 完成，所以必须形成 PORT1 到 PORT2 的闭合环路：例如 DUT 到 PORT2 的 SA 校准场景，PORT1 侧需要先切 `VNA1 -> H/V`。

禁止/注意：

- `LINK-CAL-003` 的 DUT 到 SA 校准必须同时配置 VNA1 到 H/V 的发射半链路和 DUT 到 SA 的接收半链路。
- `LINK-CAL-004` 的 SG 校准必须同时配置 SG 到 H/V 的发射半链路和 DUT 到 VNA2 的接收半链路。
- 链路损耗校准使用标准增益喇叭，不是接上 DUT 的测试链路。

### 模板 B：LINK-CAL-002 AUX-D 回传段校准链路

用途：作为 `LINK-CAL-002` 的子步骤，执行转台DUT到VNA的损耗校准。校准时使用第四根辅助线 AUX-D，先直连 VNA1 和 VNA2 进行 AUX-D 单独测试；随后将 AUX-D 接到转台DUT接口作为转台DUT侧参考，同时接收侧仍需要通过链路箱切到 `DUT -> AMP1 -> VNA2`。

操作步骤：

1. AUX-D 单独测试：人工接入 AUX-D，直连 VNA1 和 VNA2。
2. 用网分测量 AUX-D 本身响应，作为辅助线修正参考。
3. 转台DUT到VNA的损耗校准发射侧：将 AUX-D 从 VNA2 侧改接到转台DUT接口。
4. 转台DUT到VNA的损耗校准接收侧：切换 DUT 接收侧到 VNA2。
5. 不切换 H/V 极化链路。
6. 不经过 AMP2。

指令组合：

| 操作 | 链路箱指令 |
|---|---|
| AUX-D 单独测试：VNA1 直连 VNA2 | 不下发 |
| 转台DUT到VNA的损耗校准发射侧：VNA1 通过 AUX-D 接到转台DUT接口 | 不下发 |
| 转台DUT到VNA的损耗校准接收侧：DUT 接收侧切到 VNA2 | `CONFigure:LINK DUT, AMP1, VNA2` |

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

- 接上 DUT 时，DUT TX&RX 通用测试链路不使用 `CONFigure:LINK DUT, AMP1, VNA2`。

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

输出参数：

| 参数 | 含义/计算 |
|---|---|
| `L_AUX_A` / `L_AUX_B` / `L_AUX_C` | 三根 3M 辅助线自身损耗，`L_AUX_* = -S21_AUX_*`。 |
| `L_CH_INT_H` | 暗室接口板 H 到暗室接口板 DUT 的净损耗，`L_CH_INT_H = -S21_CH_INT_H_RAW - L_AUX_A - L_AUX_C`。 |
| `L_CH_INT_V` | 暗室接口板 V 到暗室接口板 DUT 的净损耗，`L_CH_INT_V = -S21_CH_INT_V_RAW - L_AUX_B - L_AUX_C`。 |
| `L_CH_INT_DUT` | 转台DUT接口到暗室接口板 DUT 的净损耗，`L_CH_INT_DUT = -S21_CH_INT_DUT_RAW - L_AUX_A - L_AUX_C`。 |
| `L_CH_INT_FEED_H` | 馈源 H 发射到转台DUT接口/DUT 端面的派生损耗，`L_CH_INT_FEED_H = L_CH_INT_H - L_CH_INT_DUT`。 |
| `L_CH_INT_FEED_V` | 馈源 V 发射到转台DUT接口/DUT 端面的派生损耗，`L_CH_INT_FEED_V = L_CH_INT_V - L_CH_INT_DUT`。 |

### LINK-CAL-002：VNA 链路损耗校准

- 仪表角色：VNA 发射 + VNA 接收。
- DUT/校准件状态：主链路校准时转台DUT接口换标准增益喇叭；回传段校准时使用 AUX-D 接转台DUT接口。
- 可选参数：主链路校准支持极化 H/V、TX 是否经过 AMP2；AUX-D 回传段不需要极化、不经过 AMP2。
- 链路模板：模板 A + 模板 B。
- 目的：校准 VNA 主测试链路损耗，并在同一校准项内用 AUX-D 得到转台DUT接口到 VNA2 的回传链路损耗。
- 具体指令：

| 阶段/条件 | 链路箱指令 |
|---|---|
| 主链路 H，不经过 AMP2 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK H, VNA1` |
| 主链路 V，不经过 AMP2 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK V, VNA1` |
| 主链路 H，经过 AMP2 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK H, AMP2, VNA1` |
| 主链路 V，经过 AMP2 | `CONFigure:LINK DUT, AMP1, VNA2` + `CONFigure:LINK V, AMP2, VNA1` |
| AUX-D 单独测试：VNA1 直连 VNA2 | 不下发 |
| AUX-D 接转台DUT接口：VNA1 通过 AUX-D 接到转台DUT接口 | 不下发 |
| AUX-D 接转台DUT接口：DUT 接收侧切到 VNA2 | `CONFigure:LINK DUT, AMP1, VNA2` |

输出参数：

| 参数 | 含义/用途 |
|---|---|
| `L_VNA_H` / `L_VNA_V` | VNA1 经 H/V、暗室空间、标准喇叭、DUT 回 VNA2 的等效链路损耗。 |
| `L_VNA_H_AMP2` / `L_VNA_V_AMP2` | 经过 AMP2 的 VNA 等效链路损耗。 |
| `L_AUX_D` | AUX-D 辅助线自身损耗，`L_AUX_D = -S21_AUX_D`。 |
| `L_DUT_VNA` | 转台DUT接口到 VNA2 的回传链路损耗，由 AUX-D 参考和转台DUT接口测量结果计算得到。 |

### LINK-CAL-003：SA 校准

- 仪表角色：VNA S21 闭环。
- DUT/校准件状态：DUT 到 SA 校准时，转台DUT接口换标准增益喇叭，网分 PORT1 接链路箱 VNA1，网分 PORT2 接链路箱 SA；H/V 馈源侧到 SA 校准时，网分 PORT1 临时接链路箱 H/V 馈源侧参考端，网分 PORT2 接链路箱 SA。
- 可选参数：极化 H/V；DUT 到 SA；H/V 馈源侧到 SA；是否经过 AMP2。
- 链路模板：SA 校准链路。
- 目的：校准链路箱 SA 物理端口相关损耗；DUT 到 SA 校准时必须由 VNA1->H/V 提供 PORT1 侧发射路径。
- 具体指令：

| 等效校准对象 | 链路箱指令 |
|---|---|
| H 发射，经 DUT 到 SA | `CONFigure:LINK H, VNA1` + `CONFigure:LINK DUT, AMP1, SA` |
| V 发射，经 DUT 到 SA | `CONFigure:LINK V, VNA1` + `CONFigure:LINK DUT, AMP1, SA` |
| H 馈源侧到 SA | `CONFigure:LINK H, SA` |
| V 馈源侧到 SA | `CONFigure:LINK V, SA` |
| H 馈源侧经 AMP2 到 SA | `CONFigure:LINK H, AMP2, SA` |
| V 馈源侧经 AMP2 到 SA | `CONFigure:LINK V, AMP2, SA` |

输出参数：

| 参数 | 含义/用途 |
|---|---|
| `L_SA_H` / `L_SA_V` | DUT/馈源侧到频谱仪 SA 端口的等效接收链路损耗。 |
| `L_SA_H_AMP2` / `L_SA_V_AMP2` | 经过 AMP2 的 SA 接收路径损耗。 |

### LINK-CAL-004：SG 校准

- 仪表角色：VNA S21 闭环。
- DUT/校准件状态：转台DUT接口换标准增益喇叭；网分 PORT1 接链路箱 SG，网分 PORT2 接链路箱 VNA2。
- 可选参数：极化 H/V。
- 链路模板：SG 校准链路。
- 目的：校准链路箱 SG 物理端口到 H/V 馈源侧的链路损耗。
- 具体指令：

| 条件 | 链路箱指令 |
|---|---|
| H 极化 | `CONFigure:LINK H, SG` + `CONFigure:LINK DUT, AMP1, VNA2` |
| V 极化 | `CONFigure:LINK V, SG` + `CONFigure:LINK DUT, AMP1, VNA2` |

输出参数：

| 参数 | 含义/用途 |
|---|---|
| `L_SG_H` / `L_SG_V` | SG 端口经 H/V 发射到标准喇叭/转台DUT接口，再回 VNA2 的等效发射链路损耗。 |

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








