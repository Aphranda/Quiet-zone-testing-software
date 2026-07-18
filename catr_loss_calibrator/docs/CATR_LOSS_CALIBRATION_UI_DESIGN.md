# CATR 路损校准软件 UI 设计方案

Status: Active
Domain: CATR_LOSS_CALIBRATOR
Canonical: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_DESIGN.md`
Related: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md`, `catr_loss_calibrator/docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
Last updated: 2026-07-18

本文档定义 `catr_loss_calibrator` 的操作员 UI 方案。当前界面采用 PySide6 + MVVM，实现目标是给普通操作人员提供一套校准操作台：先配置仪表，再按步骤执行校准，最后查看结果，同时始终可见 LOG。

## 1. 设计目标

- 面向普通操作人员，减少工程术语暴露，少用简称，多用完整名称。
- 仪表连接必须可见、可配置、可手动控制，启动界面时不自动连接。
- 每个校准项都能按步骤执行，而不是一键黑盒完成。
- 每一步都展示接线路径、链路箱命令、输入输出端口和当前状态。
- LOG 作为公共资源常驻界面右侧，无论切换哪个页签都能看到。
- UI 只负责展示、输入和状态派生，不负责公式计算和文件命名。
- UI 必须基于 MVVM，便于测试、替换和后续扩展。

## 2. 设计约束

- UI 框架使用 PySide6。
- 主窗口使用 `QTabWidget` 管理功能页签，使用右侧常驻 `LogPanel` 显示运行日志。
- 仪表连接配置在第一页完成，连接动作必须由操作人员手动触发。
- Mock / Real 使用互斥控件表达；Real 模式下可通过 VISA 搜索资源。
- 资源地址和型号保留可编辑下拉框，允许选择常用项，也允许现场手动录入。
- UI 不负责公式计算，不负责文件命名，不负责存储细节。
- 校准步骤的接线说明应与 `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` 对应条目保持一致。
- UI 状态应尽量由 ViewModel / runner 派生，避免在 View 中拼接业务流程。

当前实现中，`CalibrationViewModel` 暂时承担仪表管理门面职责，负责根据连接配置创建 Mock / PyVISA 设备对象。后续如果真实硬件控制逻辑继续变复杂，应把设备创建和连接管理下沉到独立 service / adapter，ViewModel 只保留界面状态派生。

## 3. MVVM 分层

### 3.1 View

View 只负责页面渲染和控件交互。

当前主要组件：

- 主窗口 `MainWindow`
- 仪表配置卡片 `DeviceCommandPanel`
- 校准项列表区
- 步骤详情区
- 执行控制区
- 结果区
- 右侧常驻日志区 `LogPanel`
- 状态栏

### 3.2 ViewModel

ViewModel 保存 UI 所需的派生状态：

- 当前校准项
- 当前步骤
- 当前状态
- 当前步骤说明
- 当前接线路径摘要
- 当前链路箱指令
- 当前输出文件路径
- 设备连接配置
- 设备连接状态
- 最近一次设备响应
- 按钮可用性
- 错误提示
- 操作日志

### 3.3 Model

Model 复用软件现有校准模型：

- `CalibrationItem`
- `CalibrationStep`
- `CalibrationCatalog`
- `CalibrationState`
- `TraceRecord`
- `MetadataRecord`
- `InstrumentConnectionConfig`

### 3.4 Runner / Hardware Adapter

UI 不直接执行校准计算，而是通过 runner 触发：

- `MockCalibrationRunner`
- 后续真实 calibration runner

runner 负责：

- 状态迁移
- 接线确认
- 链路命令下发
- 原始 trace 保存
- metadata 保存
- 最终结果保存

硬件 adapter 负责：

- Mock / Real 设备实例化
- VISA 资源连接
- SCPI / 链路箱命令收发
- VNA 扫频配置、触发和采样

## 4. 主窗口布局

主窗口采用顶部品牌区 + 中部左右分栏 + 底部状态栏。

- 顶部品牌区：显示 LOGO、软件名称、项目、版本和状态提示。
- 左侧主工作区：包含三个页签，依次为 `仪表配置`、`校准执行`、`结果`。
- 右侧 LOG 区：常驻显示操作日志、设备连接日志、命令响应和错误。
- 底部状态栏：显示当前状态和四类设备连接摘要。

这种结构把“正在做什么”和“发生了什么”分开：操作内容在左侧切换，日志在右侧连续保留，现场排障时不需要来回切页。

### 4.1 页签结构

- 仪表配置：配置并连接链路箱、网分、信号源、频谱仪，也承担独立命令验证能力。
- 校准执行：一步一步执行 `LINK-CAL` / `LINK-TXR` / `LINK-GT` / `LINK-SYS`。
- 结果：查看运行摘要、最终输出、文件状态和会话记录。

LOG 不作为独立页签，而是公共右侧面板。

### 4.2 仪表配置页

仪表配置页是第一页，按四列等宽展示设备卡片，顺序为：

1. 链路箱
2. 网分
3. 信号源
4. 频谱仪

每个设备卡片包含：

- 连接模式：`Mock` / `Real` 互斥选择。
- 资源地址：可编辑下拉框。
- 型号：可编辑下拉框。
- 超时：毫秒输入。
- 操作：搜索、连接、断开。
- 状态：已连接 / 未连接。
- 预设命令：常用命令或命令模板。
- 命令输入：可手动输入 SCPI / 控制命令。
- 当前响应：显示最近一次返回。

Real 模式下，搜索按钮通过 VISA 枚举资源；Mock 模式下，搜索按钮只恢复对应设备的 Mock 资源选项。

链路箱卡片需要显示当前预设命令对应的关键节点，便于操作人员确认链路方向。

网分卡片额外包含扫频配置：

- 起频
- 止频
- 步进，默认 `10 MHz`
- 点数，跟随起频、止频、步进自动计算，并显示在步进后方
- 功率
- IFBW
- 扫频模式
- S 参数
- 配置 / 触发 / 采样按钮

历史命令不再作为界面功能保留。实时 LOG 已覆盖现场追踪需求，命令卡片只保留当前命令和当前响应。

### 4.3 校准执行页

#### 左栏：校准项导航

显示：

- 校准项 ID
- 校准项名称
- 步骤数量
- 当前选中项高亮
- 步骤列表
- 校准项摘要

作用：

- 让操作人员快速切换不同校准项。
- 显示当前方案总览。
- 展示当前步骤、已完成步骤和未开始步骤。

#### 中栏：步骤执行区

显示：

- 当前步骤名称
- 当前步骤状态
- 步骤进度条
- 接线路径
- 接线说明
- 链路箱命令
- 输入端口 / 输出端口
- 原始输出 / 最终输出
- required_inputs
- notes

按钮：

- 开始
- 下一步
- 跳过
- 重试
- 取消

#### 底部：状态栏

显示：

- 当前状态
- VNA / SG / LinkBox / SA 连接状态

### 4.4 结果页

结果页显示：

- 运行摘要
- 最终输出与会话结果
- 会话记录
- raw / metadata / final 文件状态

结果页只负责查看和导出相关信息，不承担步骤执行和仪表配置。

### 4.5 右侧 LOG 面板

LOG 面板常驻右侧，显示：

- 操作日志
- 错误日志
- 设备连接变化
- 命令发送记录
- 命令响应记录
- runner 状态事件

LOG 面板支持：

- 级别筛选
- 关键字搜索
- 字体大小调整
- 自动换行开关
- 时间戳显示开关
- 清空筛选

LOG 面板不承担历史命令回放功能。

## 5. 步骤展示规则

每个步骤必须展示以下信息：

| 字段 | 来源 | 用途 |
|---|---|---|
| 步骤 ID | `CalibrationStep.id` | 稳定引用 |
| 步骤名称 | `CalibrationStep.name` | UI 标题 |
| 接线说明 | `CalibrationStep.manual_instruction` | 操作员接线提示 |
| 接线路径摘要 | 由 `manual_instruction` / `route_ids` 派生 | 更直观地提示“怎么接” |
| 链路箱命令 | `CalibrationStep.link_commands` | 供高级确认 |
| 输入端口 | `CalibrationStep.input_port` | 端口方向确认 |
| 输出端口 | `CalibrationStep.output_port` | 端口方向确认 |
| 原始输出 | `CalibrationStep.raw_outputs` | 追溯量 |
| 最终输出 | `CalibrationStep.final_outputs` | 最终结果 |
| 所需输入 | `CalibrationStep.required_inputs` | 依赖提示 |
| 备注 | `CalibrationStep.notes` | 补充说明 |

步骤区必须优先显示“人能看懂的路径”，例如：

- `PORT1 -> AUX-D -> 转台 DUT 接口 -> VNA2`
- `H/V -> AMP2 -> SA`
- `DUT_REF -> SA`

## 6. 交互流程

### 6.1 启动与仪表配置

1. 启动软件。
2. 默认进入 `仪表配置` 页。
3. 操作人员选择 Mock 或 Real。
4. Real 模式下搜索或输入 VISA 资源。
5. 设置型号和超时。
6. 手动连接设备。
7. 通过预设命令或手动命令验证设备响应。
8. LOG 持续记录连接、命令和响应。

### 6.2 校准执行

1. 切换到 `校准执行` 页。
2. 选择校准项。
3. 查看步骤列表。
4. 点击“开始”。
5. UI 显示当前步骤和接线说明。
6. 操作员完成接线。
7. 点击“下一步”。
8. runner 执行链路切换、采样、保存。
9. UI 更新当前状态、结果摘要和 LOG。
10. 重复直到结束。

### 6.3 异常流程

- 接线错误：允许“重试”。
- 操作员临时离开：后续应支持“暂停”。
- 发现配置不对：允许“取消”。
- 当前步骤可跳过时：允许“跳过”。
- 设备连接失败：保留连接配置和错误日志，允许修改后重连。

## 7. 按钮可用性规则

按钮状态由当前校准状态和设备连接状态决定：

- `IDLE`：允许选择校准项、配置设备、开始。
- `WAIT_MANUAL_CONFIRM`：允许下一步、跳过、取消。
- `CONFIGURE_LINK` / `CONFIGURE_VNA` / `TRIGGER_SWEEP` / `READ_TRACE` / `SAVE_RAW` / `COMPUTE_OUTPUT` / `SAVE_OUTPUT`：只读，禁止改关键配置。
- `DONE`：允许查看结果、导出、重新开始。
- `FAILED` / `CANCELLED`：允许查看日志、清理、重来。
- 设备已连接时：禁止修改资源地址、型号、Mock / Real 和超时。
- 设备未连接时：允许修改连接配置，但禁止发送设备命令。

## 8. 数据绑定来源

| UI 数据 | 来源 |
|---|---|
| 校准项列表 | `default_calibration_catalog()` |
| 步骤说明 | `CalibrationStep` |
| 当前状态 | `CalibrationStateMachine` / runner events |
| 仪表配置 | `InstrumentConnectionConfig` |
| VISA 资源 | `pyvisa.ResourceManager().list_resources()` |
| 设备响应 | hardware adapter |
| 日志 | runner events / diagnostics / command events |
| 输出文件 | storage / session 记录 |

## 9. 与 HTML 方案的关系

UI 不重新定义接线规则，只展示 HTML 方案已有内容：

- HTML 方案是接线与校准口径的权威来源。
- UI 只负责把每个步骤的说明、路径和命令做成操作员可执行的界面。
- 若 HTML 方案更新，UI 文本和字段也要同步更新。

## 10. 实现顺序建议

1. 先保持 `MainWindow`、页签、右侧 LOG 和状态栏稳定。
2. 完善 `仪表配置` 页的四设备连接配置和命令验证。
3. 完善 VNA 扫频配置、触发和采样。
4. 完善 `校准执行` 页的按钮状态联动和异常拦截。
5. 完善 `结果` 页的文件路径复制、打开目录和结果导出。
6. 后续把真实硬件连接管理从 ViewModel 下沉到独立 service / adapter。

## 11. 验收标准

- 操作员启动软件后不会自动连接设备。
- 操作员能在第一页完成链路箱、网分、信号源、频谱仪配置。
- Mock / Real 互斥，Real 模式可搜索 VISA 资源。
- 操作员能选校准项。
- 操作员能看到当前步骤、接线路径和命令。
- UI 能按状态机一步一步执行。
- 非法操作会被禁用或拦截。
- 操作员在任意页签都能看到 LOG。
- 操作员能看到文件输出结果。
