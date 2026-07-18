# CATR 路损自动校准软件设计方案

更新时间：2026-07-18

## 1. 目标

重新开发一套独立的 CATR 暗室路损自动校准软件，用于执行 `LINK-CAL-001` 至 `LINK-CAL-005` 的路损校准、保存原始网分 S21 数据、计算最终带符号路损文件，并为后续测试项提供可追溯的校准参数。

该软件不作为当前静区测试软件的插件，也不依赖当前静区测试软件运行时。

## 2. 去耦合原则

新软件必须避免与现有 `quiet-zone-tester` 耦合：

- 不 import `quiet_zone_tester.*`。
- 不调用当前 `InstrumentService`。
- 不依赖当前 `MainWindow`、扫描设置、步进扫描、扫描数据模型。
- 不共享当前软件的可变配置文件。
- 不要求当前静区测试软件启动后才能运行。
- 新软件独占 VNA、链路箱、SG、SA 等硬件连接。
- 不复用当前项目的扫描架、运动控制、步进扫描和通道测试执行链。

允许参考或迁移的内容：

- VNA SCPI/VISA 控制经验。
- LCD74000F 链路箱指令表。
- Trace CSV、metadata、index 保存思路。
- 单元测试组织方式。

但迁移后的代码必须属于新软件包，并由新软件自己的测试覆盖。

## 3. 推荐工程结构

新项目目录：

```text
catr_loss_calibrator/
  pyproject.toml
  README.md
  src/catr_loss_calibrator/
    presentation/
    app/
    application/
    calibration/
    instrument_management/
    link_management/
    hardware/
    storage/
    project/
    diagnostics/

    __init__.py
    __main__.py
  tests/
```

模块职责：

| 模块 | 职责 |
|---|---|
| `app` | 应用入口、CLI/UI 装配 |
| `presentation` | 面向操作人员的交互层、页面与入口呈现 |
| `application` | 任务编排、用例流转、错误处理 |
| `hardware` | VNA、链路箱、SG、SA 等硬件接口与适配器 |
| `calibration` | 校准项定义、校准执行器、路损公式 |
| `project` | 项目配置、馈源/喇叭/频段配置 |
| `storage` | 原始 S21、最终 L 参数、metadata、文件命名 |
| `tests` | 校准定义、公式、命名、命令生成的测试 |

其中校准域至少应覆盖 5 个校准项：

- `LINK-CAL-001` 暗室内部链路校准
- `LINK-CAL-002` VNA 链路损耗校准
- `LINK-CAL-003` DUT 到 SA 校准
- `LINK-CAL-004` SA-H/V 校准
- `LINK-CAL-005` SG 校准

## 4. 可借鉴的架构原则

参考 `docs/architecture_migration_plan.md`，新软件应吸收其中“边界治理”的原则，但不继承静区测试软件的迁移包袱。

### 4.1 业务域优先

目录结构优先按业务域划分，而不是按 `ui/services/models` 技术层平铺。对路损校准软件而言，核心业务域应包括：

| 业务域 | 责任 |
|---|---|
| `calibration` | 校准项定义、校准步骤、执行器、公式计算 |
| `instrument_management` | 仪表连接、断开、资源占用检查、连接状态 |
| `link_management` | 链路箱命令模板、H/V 极化、DUT 目标、当前链路状态 |
| `hardware` | VNA、链路箱、SG、SA 的接口、Mock 和真实适配器 |
| `storage` | 原始 S21、最终 L 文件、metadata、hash、文件索引 |
| `project` | 馈源、喇叭、频段、项目配置 |
| `diagnostics` | 日志、错误事件、执行记录 |

### 4.2 依赖方向

推荐依赖方向：

```text
presentation / app
  -> calibration
  -> instrument_management / link_management
  -> hardware
  -> storage / project models
```

约束：

- UI 不直接调用 VNA 或链路箱 controller。
- presentation 层面向操作人员，优先承载交互、状态显示与操作入口。
- `calibration runner` 不依赖具体 UI 控件。
- `hardware` 不关心文件保存和页面显示。
- `storage` 不决定流程跳转。
- `project` 配置只保存事实，不执行硬件动作。

### 4.3 状态机管理流程

校准流程应由状态机或显式状态类管理，而不是由多个布尔变量拼接。

建议状态：

```text
IDLE
WAIT_MANUAL_CONFIRM
CONFIGURE_LINK
CONFIGURE_VNA
TRIGGER_SWEEP
READ_TRACE
SAVE_RAW
COMPUTE_OUTPUT
SAVE_OUTPUT
DONE
FAILED
CANCELLED
```

状态机原则：

- 状态机管理流程，不保存大体量测量数据。
- 原始 S21、最终 L 参数、操作日志等事实写入 session/storage。
- 每个状态转换由明确事件触发。
- 非法状态下拒绝执行硬件命令。
- UI 按状态派生按钮可用性。

### 4.4 数据管理保存事实

数据管理不是“保存 CSV”这么简单，而是保存校准事实。一次校准 session 至少应记录：

- 项目配置快照。
- 仪表连接配置快照。
- 馈源、标准喇叭、频段。
- 校准项 ID 和步骤 ID。
- 人工接线确认记录。
- 下发过的链路箱命令。
- VNA sweep 配置。
- 原始 `S21_*` 曲线。
- 输入依赖文件及 hash。
- 最终 `L_*` 文件及 hash。
- 公式版本。
- 错误和重试记录。

建议后续补充：

```text
storage/
  raw_trace_storage.py
  loss_file_storage.py
  calibration_session_repository.py
  metadata_writer.py
  loss_file_policy.py
```

### 4.5 仪表管理与链路管理分离

仪表管理只负责“连接和资源”，链路管理只负责“链路语义和命令”。

仪表管理：

- 创建 VNA、链路箱、SG、SA controller。
- 连接、断开、状态查询。
- 资源占用检查。
- 保存连接配置快照。

链路管理：

- 根据校准步骤生成 `CONFigure:LINK ...` 命令。
- 保存当前链路状态。
- 校验禁止命令和互斥工况。
- 维护 LCD74000F profile。

### 4.6 资源互锁显式化

新软件应显式管理硬件资源互锁：

- 校准中禁止外部手动切链路。
- 校准中禁止重复连接/断开仪表。
- VNA 采样中禁止修改 sweep 配置。
- 一个软件实例应独占 VNA、链路箱、SG/SA。
- 检测到端口或 VISA 资源被占用时，应给出明确错误。
- 禁止与静区测试软件同时控制同一台网分或链路箱。

### 4.7 文档治理

设计、操作、待办和实施记录应分离：

```text
docs/
  CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md
  CALIBRATION_DOMAIN_DESIGN.md
  HARDWARE_ADAPTER_DESIGN.md
  STORAGE_DESIGN.md
  DEVELOPMENT_TODO.md
  TASK_PROGRESS.md
```

### 4.8 实现约束

以下约束直接作为本软件的实现要求：

- 仪表管理必须先于校准执行，负责连接、断开、状态查询和资源占用判断。
- 硬件适配层必须统一抽象 VNA、链路箱、SG、SA；Mock 与真实实现必须共享同一协议。
- 校准编排层只消费硬件接口，不直接操作具体设备实现类。
- 校准流程必须显式管理状态，不允许用多个布尔变量拼接流程判断。
- 资源互锁必须可见、可检查、可失败返回，禁止靠人工经验维持并发安全。
- 真实硬件验证必须在单独的验证清单中覆盖连接、链路切换、采样、保存和故障恢复。
- 可靠性问题按优先级分层跟踪，先保证可运行、可追溯，再逐步完善恢复和长期稳定性。

## 5. 建议演进目录

当前一期骨架保持轻量。随着功能展开，建议演进为：

```text
src/catr_loss_calibrator/
  presentation/
    # 一期先保留入口与交互层骨架

  app/
    main.py
    app_context.py

  application/
    task_runner.py
    errors.py

  calibration/
    models.py
    definitions.py
    calibration_runner.py
    calibration_service.py
    formulas.py
    state_machine.py

  instrument_management/
    models.py
    instrument_manager.py
    connection_service.py
    resource_lock.py

  link_management/
    models.py
    link_service.py
    lcd74000f_profile.py
    link_templates.py

  hardware/
    interfaces.py
    mock.py
    vna/
    link_box/

  storage/
    raw_trace_storage.py
    loss_file_storage.py
    calibration_session_repository.py
    metadata_writer.py
    loss_file_policy.py

  project/
    config.py
    feed_horn_catalog.py

  diagnostics/
    log_record.py
    error_report.py
```

不建议引入：

- 当前静区测试软件的 `InstrumentService facade`。
- 当前静区测试软件的 `MainWindow`。
- 扫描架、运动控制、步进扫描、ScanPlanner 等与路损校准无关的流程。
- 兼容旧扫描业务的 API。

## 6. 一期功能范围

一期先实现“非 UI 核心闭环”，保证校准流程可被 CLI/测试驱动：

- 定义校准项 `LINK-CAL-001` 至 `LINK-CAL-005`。
- 定义链路箱命令序列。
- 定义人工接线确认点。
- 定义原始测量量 `S21_*` 与最终输出参数 `L_*`。
- 实现带符号 dB 公式计算。
- 实现路损文件命名规则。
- 实现 CSV 保存。
- 提供 mock VNA / mock 链路箱用于流程测试。
- 为每个校准项提供独立的参数生成、文件输出与单元测试入口。

二期再做 PySide6 UI：

- 校准项列表。
- 人工接线确认。
- 当前步骤进度。
- VNA 参数配置。
- 原始曲线预览。
- 最终输出文件列表。

## 7. 路损计算口径

最终路损文件保存带符号 dB 值：

- 无源链路通常为负值。
- 含放大器链路可能为正值。
- 标准增益喇叭为正增益，去嵌时使用减号。
- `L_AUX_*` 直接来自辅助线原始 S21 文件，通常为负数，公式中直接相加。

关键公式示例：

```text
L_CH_INT_H = S21_CH_INT_H_RAW + L_AUX_A + L_AUX_C - G_STD_HORN_H
L_CH_INT_V = S21_CH_INT_V_RAW + L_AUX_B + L_AUX_C - G_STD_HORN_V
L_CH_INT_DUT = S21_CH_INT_DUT_RAW + L_AUX_A + L_AUX_C
L_CH_INT_FEED_H/V = L_CH_INT_H/V - L_CH_INT_DUT
```

注意：不引入 `AUX_CORR`，也不把 `L_AUX_*` 转成正损耗。

## 8. 文件命名规则

```text
{PARAM}_{BAND}_{FEED}_{HORN}.csv
```

当 `HORN != NOHORN` 时，`BAND` 必须取馈源与喇叭的有效频段交集：

| 馈源 | 标准喇叭 | BAND | 实际频段 |
|---|---|---|---|
| `F10_17G` | `H10_15G` | `10_15G` | 10–15 GHz |
| `F10_17G` | `H14P5_22G` | `14P5_17G` | 14.5–17 GHz |
| `F17_31G` | `H14P5_22G` | `17_22G` | 17–22 GHz |
| `F17_31G` | `H21P7_33G` | `21P7_31G` | 21.7–31 GHz |

CSV 字段建议：

| 字段 | 含义 |
|---|---|
| `freq_hz` | 频点 |
| `value_db` | 最终带符号路损 / 传输值 |
| `param` | 参数名 |
| `band` | 频段短码 |
| `feed` | 馈源短码 |
| `horn` | 喇叭短码或 `NOHORN` |
| `source_cal` | 来源校准项 |

## 9. 校准执行器状态机

建议状态：

```text
IDLE -> WAIT_MANUAL_CONFIRM -> CONFIGURE_LINK -> CONFIGURE_VNA
     -> TRIGGER_SWEEP -> READ_TRACE -> SAVE_RAW
     -> COMPUTE_OUTPUT -> SAVE_OUTPUT -> DONE
```

异常状态：

```text
FAILED
CANCELLED
```

要求：

- 每一步都写入执行日志。
- 人工接线步骤必须可暂停。
- 失败后保留已采集数据。
- 支持只重新计算，不重新采样。

## 10. 与当前项目的参考映射

| 当前项目能力 | 新软件处理方式 |
|---|---|
| `hardware/vna/scpi.py` | 可迁移为新软件自己的 VNA adapter |
| `hardware/transport/visa_scpi.py` | 可迁移为新软件自己的 VISA transport |
| `domains/link_management/link_service.py` | 参考原始命令下发与连接检查，重新实现 |
| `resource/LCD74000F.md` | 作为链路箱命令权威参考 |
| `domains/data_management/trace_storage.py` | 参考 CSV/metadata/index 设计，重新实现校准专用 storage |

## 11. 验收标准

- 新软件包可独立运行：`python -m catr_loss_calibrator`。
- 不依赖 `quiet_zone_tester` import。
- mock 模式下可列出 `LINK-CAL-001` 至 `LINK-CAL-005`。
- 每个校准项都能生成对应的原始量、正式输出和文件名。
- 路损文件命名规则有单元测试。
- 带符号公式有单元测试。
- 链路箱命令序列有单元测试。
