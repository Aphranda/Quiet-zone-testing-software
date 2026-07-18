# CATR 路损校准软件 UI 设计方案

Status: Draft  
Domain: CATR_LOSS_CALIBRATOR  
Canonical: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_DESIGN.md`  
Related: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md`, `catr_loss_calibrator/docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`  
Last updated: 2026-07-18

本文档定义 `catr_loss_calibrator` 的操作员 UI 方案。目标不是做“能跑的窗口”，而是做一套真正面向普通操作人员的校准操作台：能选校准项、能看步骤、能按步骤接线、能一步一步推进、能看到状态和结果。

## 1. 设计目标

- 面向普通操作人员，减少工程术语暴露。
- 每个校准项都能按步骤执行，而不是一键黑盒完成。
- 每一步都展示接线路径、链路箱命令、输入输出端口和当前状态。
- UI 只负责展示、输入和状态派生，不直接拼接业务命令。
- UI 必须基于 MVVM，便于测试、替换和后续扩展。

## 2. 设计约束

- UI 框架使用 PySide6。
- UI 不直接访问真实 VNA / 链路箱 controller。
- UI 不负责公式计算，不负责文件命名，不负责存储细节。
- 校准步骤的接线说明必须来自 `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` 对应条目。
- UI 状态必须由 `calibration state machine` 派生，不允许多个布尔变量拼流程。
- 设计应吸收开源工业软件的通用成熟做法：分区清晰、步骤明确、状态可见、错误可追、命令可试。

## 3. MVVM 分层

### 3.1 View

View 只负责页面渲染和控件交互。

建议页面：

- 主窗口 `MainWindow`
- 校准项列表区 `CalibrationListPanel`
- 当前步骤区 `StepDetailPanel`
- 执行控制区 `ActionPanel`
- 日志区 `LogPanel`
- 状态栏 `StatusBarPanel`

### 3.2 ViewModel

ViewModel 保存 UI 所需的派生状态：

- 当前校准项
- 当前步骤
- 当前状态
- 当前步骤说明
- 当前接线路径摘要
- 当前链路箱指令
- 当前输出文件路径
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

### 3.4 Controller / Runner

UI 不直接执行校准逻辑，而是通过 runner 触发：

- `MockCalibrationRunner`
- 后续真实 calibration runner

runner 负责：

- 状态迁移
- 接线确认
- 链路命令下发
- 原始 trace 保存
- metadata 保存
- 最终结果保存

## 3.5 需要内化的开源软件设计原则

这里不记录“参考了哪些项目”，而是直接沉淀成本项目的界面原则：

- 向导式推进：复杂校准不要让用户自由跳来跳去，默认按步骤线性推进。
- 主流程与验证流程分离：完整校准和指令测试必须是两个独立入口。
- 高密度状态反馈：任何时候都要看见当前步、连接态、设备响应和下一步是否可操作。
- 任务区 / 内容区 / 结果区分离：左侧选任务，中间做动作，右侧看结果，符合工业操作习惯。
- 可折叠辅助信息：日志、历史命令、调试信息应可收起，避免干扰主操作区。
- 表单优先：复杂参数用字段和只读卡片承载，不让操作员在长文本里找重点。
- 容错优先：失败时保留上下文，允许重试、暂停、取消和查看历史。
- 指令可复用：预设命令、历史命令和当前命令应能复用，方便现场排障。

## 4. 主窗口布局

建议使用多页签 + 统一状态栏布局，至少包含“校准执行页”和“指令测试页”。

从常见开源 Qt / 仪表控制类项目里可以借鉴的，不是某个具体界面样式，而是这几类稳定做法：

- 主流程用向导式步骤推进，减少操作员“自己判断下一步做什么”的负担。
- 左侧放任务树或项目列表，中间放当前动作，右侧放日志 / 结果 / 属性，这种三栏结构最适合工业操作台。
- 独立保留“指令测试页”，用于脱离完整流程验证设备联通性和命令正确性。
- 状态反馈要很强：连接状态、当前步、已完成步数、失败原因、可继续与否，都要一眼能看到。
- 日志和结果区最好可停靠或可折叠，避免主操作区被挤窄。
- 复杂参数用表单和只读卡片展示，避免让操作员直接面对一长串文本。

### 4.1 页签结构

- 校准执行页：一步一步执行 `LINK-CAL` / `LINK-TXR` / `LINK-GT` / `LINK-SYS`。
- 指令测试页：单独验证链路箱命令、route_id 和原始 `CONFigure:LINK ...` 指令。
- 日志页：查看执行日志、错误、连接信息。
- 结果页：查看 raw / metadata / final 文件。

每个页签都应承担单一职责：

- 校准执行页只负责操作流转。
- 指令测试页只负责设备命令联调。
- 日志页只负责追踪。
- 结果页只负责查看和导出。

这种拆分方式来自成熟桌面工业软件的通用架构，能显著降低认知负担。

### 4.2 校准执行页布局

#### 左栏：校准项导航

显示：

- 校准项 ID
- 校准项名称
- 步骤数量
- 当前选中项高亮

作用：

- 让操作人员快速切换不同校准项
- 显示当前方案总览

#### 中栏：步骤执行区

显示：

- 当前步骤名称
- 当前步骤状态
- 步骤进度条
- 当前步骤卡片摘要
- 接线路径
- 接线说明
- 链路箱命令
- 输入端口 / 输出端口
- 原始输出 / 最终输出

按钮：

- 开始
- 下一步
- 跳过
- 重试
- 取消
- 完成当前步骤

#### 右栏：日志与结果区

显示：

- 操作日志
- 当前连接健康状态
- 当前设备响应摘要
- raw 文件路径
- metadata 文件路径
- final 文件路径
- 错误信息

#### 底部：状态栏

显示：

- 当前状态
- 连接状态
- 当前校准项
- 当前步骤编号

### 4.3 指令测试页布局

指令测试页用于独立验证链路箱指令，不进入完整校准流程。

建议字段：

- 指令输入框
- route_id 下拉框
- 预设命令按钮
- 当前响应
- 错误信息
- 历史命令列表
- 响应时间
- 最近一次成功时间
- 命令来源说明

可测试对象：

- `CONFigure:LINK H, VNA1`
- `CONFigure:LINK V, VNA1`
- `CONFigure:LINK DUT, VNA2`
- `CONFigure:LINK DUT, AMP1, VNA2`
- `CONFigure:LINK DUT, SA`
- `CONFigure:LINK H/V, AMP2, SA`
- 以及 `lcd74000f_profile` 中定义的 route_id

推荐把指令测试页做成“命令台”风格：

- 左边选 route_id / 预设项
- 中间编辑或查看命令
- 右边显示返回值、错误与历史
- 下方显示设备连接状态和发送记录

这类结构更接近工业测试软件，操作员不需要理解内部对象，只需要确认“命令发出去了、设备回了什么、当前是否可用”。

同时建议保留以下能力：

- 预设命令一键填充
- 历史命令回放
- 连接状态即时刷新
- 响应错误高亮
- 支持复制命令与响应，便于工单和日志留存

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

步骤区必须优先显示“人能看懂的路径”，例如：

- `PORT1 -> AUX-D -> 转台DUT接口 -> VNA2`
- `H/V -> AMP2 -> SA`
- `DUT_REF -> SA`

## 6. 交互流程

### 6.1 标准流程

1. 选择校准项。
2. 查看步骤列表。
3. 点击“开始”。
4. UI 显示当前步骤和接线说明。
5. 操作员完成接线。
6. 点击“下一步”。
7. runner 执行链路切换、采样、保存。
8. UI 更新当前状态和日志。
9. 重复直到结束。

### 6.2 异常流程

- 接线错误：允许“重试”。
- 操作员临时离开：允许“暂停”。
- 发现配置不对：允许“取消”。
- 当前步骤可跳过时：允许“跳过”。

## 7. 按钮可用性规则

按钮状态由当前校准状态决定：

- `IDLE`：允许选择校准项、开始
- `WAIT_MANUAL_CONFIRM`：允许下一步、跳过、取消
- `CONFIGURE_LINK` / `CONFIGURE_VNA` / `TRIGGER_SWEEP` / `READ_TRACE` / `SAVE_RAW` / `COMPUTE_OUTPUT` / `SAVE_OUTPUT`：只读，禁止改配置
- `DONE`：允许查看结果、导出、重新开始
- `FAILED` / `CANCELLED`：允许查看日志、清理、重来

## 8. 数据绑定来源

| UI 数据 | 来源 |
|---|---|
| 校准项列表 | `default_calibration_catalog()` |
| 步骤说明 | `CalibrationStep` |
| 当前状态 | `CalibrationStateMachine` |
| 日志 | runner events / diagnostics |
| 输出文件 | storage / session 记录 |

## 9. 与 HTML 方案的关系

UI 不重新定义接线规则，只展示 HTML 方案已有内容：

- HTML 方案是接线与校准口径的权威来源。
- UI 只负责把每个步骤的说明、路径和命令做成操作员可执行的界面。
- 若 HTML 方案更新，UI 文本和字段也要同步更新。

## 10. 实现顺序建议

1. 先做 `MainWindow` 骨架。
2. 再做校准项列表。
3. 再做步骤详情区。
4. 再做指令测试页和日志页。
5. 再做按钮动作、状态联动和进度反馈。
6. 最后接 runner、设备状态和结果导出。

优先级上，先把“看得见流程”的部分做出来，再去补“看得见数据”的部分，这样更符合操作员软件的使用习惯。

## 11. 验收标准

- 操作员能选校准项。
- 操作员能看到当前步骤、接线路径和命令。
- UI 能按状态机一步一步执行。
- 非法操作会被禁用或拦截。
- 操作员能看到日志和文件输出结果。
