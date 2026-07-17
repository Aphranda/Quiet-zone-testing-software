# 软件架构评审

Status: Active
Domain: ARCH
Canonical: `docs/ARCHITECTURE_REVIEW.md`
Related: `docs/architecture_migration_plan.md`, `docs/ARCH_MIGRATION_TODO.md`, `docs/ARCH_TASK_PROGRESS.md`
Last updated: 2026-07-15

本文档记录当前静区测试软件及独立 `LCD_LINK` 程序的架构评审结果。评审重点是识别当前真实运行架构、标注旧架构与迁移架构、检查依赖方向，以及确认 LCD74000F 独立拆分后的维护边界。

## 1. 评审结论

当前软件处于渐进式迁移阶段，不应描述为已经完成新架构切换。

- 旧架构仍承载应用运行主链：`ui/main_window.py` 和 `services/instrument_service.py` 仍是主要编排入口。
- 迁移架构已经建立并承担大量业务职责：`application/`、`domains/`、`hardware/` 和 `presentation/` 均已有实际实现。
- 硬件目录迁移基本完成，`drivers/` 和 `instruments/` 主要作为 deprecated 兼容入口。
- 展示层和应用编排迁移尚未完成，旧 UI 不是单纯兼容层。
- `LCD_LINK` 已具备独立安装和运行能力，但 LCD74000F 协议、路由和默认值目前与主项目重复维护。

整体迁移方向合理，现有自动化测试可以支撑继续重构。当前最重要的工作不是继续增加目录，而是统一权威实现、纠正迁移状态，并让依赖装配和业务编排真正落入目标层。

## 2. 当前架构标注

### 2.1 旧架构：当前运行主链

以下模块属于旧架构，但仍是生产运行路径，不应直接标记为可删除兼容层：

```text
src/quiet_zone_tester/main.py
  -> src/quiet_zone_tester/app.py
  -> src/quiet_zone_tester/application/app_context.py
  -> src/quiet_zone_tester/ui/main_window.py
  -> src/quiet_zone_tester/services/instrument_service.py
```

| 模块 | 当前实际职责 | 评审标注 |
| --- | --- | --- |
| `ui/main_window.py` | Widget 装配、信号路由、后台任务发起、扫描流程、暂停/停止、位置轮询、状态反馈 | 旧架构主链，迁移中 |
| `ui/widgets/` | 当前真实 Qt View，并通过部分 ViewModel 派生状态 | 旧视图层，迁移中 |
| `services/instrument_service.py` | UI facade，同时保留连接、采样、扫描、数据写入和兼容转换 | 旧服务总入口，迁移中 |
| `models/` | 扫描范围和射频数据等跨流程基础模型 | 保留模块，需逐步明确归属 |

### 2.2 旧兼容入口：实现已经迁出

以下路径主要用于兼容历史导入，新代码不应继续依赖：

```text
drivers/          -> hardware/ 中的接口、Mock 和 VNA 实现
instruments/      -> hardware/ 中的真实硬件实现
ui/async_task.py  -> application/task_runner.py
```

这部分可以明确标注为 deprecated，但删除前仍需确认外部脚本、发布包和设备联调工具是否使用旧导入路径。

### 2.3 迁移架构：已经落地但完成度不同

```text
application/      应用装配、任务运行器、扫描工作流状态
domains/          连接、链路、运动、采样、扫描和数据管理
hardware/         硬件 Protocol、Mock、真实适配器和通信 transport
presentation/     ViewModel、Qt Model 和 UI 状态派生
shared/           仪器默认值等跨模块稳定配置
```

| 层 | 当前状态 | 完成度判断 |
| --- | --- | --- |
| `application/` | 已有 AppContext、TaskRunner 和扫描状态，但 AppContext 只装配顶层 facade | 部分完成 |
| `domains/` | 业务服务已覆盖主要业务域，且没有直接依赖 Qt Widget | 主体已落地 |
| `hardware/` | 新旧实现已迁入，旧目录通过 re-export 兼容 | 基本完成 |
| `presentation/` | ViewModel 和 Qt Model 已建立，但真实 View 仍在 `ui/` | 部分完成 |
| `services/` | 仍是 UI 使用的统一 facade，内部委托 domain service | 迁移过渡层 |
| `ui/` | 仍是运行时主视图和顶层流程路由 | 尚未完成迁移 |

### 2.4 新独立子项目：LCD_LINK

`LCD_LINK` 是一个可独立安装和运行的 Python 包：

```text
LCD_LINK/src/lcd_link/app.py
  -> window.py
  -> controller.py
  -> routing.py

LCD_LINK/src/lcd_link/service.py
  当前未被独立窗口调用
```

它不依赖 `quiet_zone_tester`，满足独立交付要求。但主项目也保留了自己的 LCD74000F Controller、路由规则和默认值，因此目前属于“独立复制实现”，不是“共享核心实现”。

## 3. 当前依赖关系

当前主程序的真实依赖流如下：

```text
QApplication
  -> AppContext
  -> MainWindow
       -> InstrumentService facade
            -> domain services
                 -> hardware Protocol / controller

Qt Widgets
  -> presentation ViewModel / Qt Model
  -> MainWindow 顶层路由

deprecated imports
  -> hardware canonical implementations
```

目标方向基本正确，但仍存在两个未闭合环节：

1. AppContext 没有装配各业务服务和硬件适配器，实际对象创建仍分散在 `InstrumentService` 和 domain 内的 Controller Factory。
2. MainWindow 仍直接组织后台任务参数、扫描状态和多个业务动作，presentation shell 尚未形成。

## 4. 主要发现

### ARCH-01 - 迁移状态与代码事实不一致

Severity: High

`ARCH_MIGRATION_TODO.md` 已将多个 P2、P3 和 P5 项目标记完成，但对应验收条件尚未完全满足：

- `MainWindow` 仍接近 900 行，并持有 Service、TaskRunner、扫描工作流和 PositionTracker。
- 扫描启动、暂停、恢复、停止和任务回调仍由 `MainWindow` 编排。
- `InstrumentService` 仍接近 900 行，并包含文件输出、旧 `dict` 转换、Controller 创建委托和扫描流程兼容方法。
- `ui/` 仍是真实运行视图，不只是 README 所称的“旧 UI 兼容层”。

影响：新功能的代码归属会出现歧义，维护者可能基于“迁移已完成”的错误假设继续向过渡层增加职责。

建议：将不满足验收条件的任务重新标记为“迁移中”，完成代码收口后再勾选；README 应把 `ui/` 描述为“当前 View 层及迁移兼容层”。

### ARCH-02 - LCD74000F 存在两套权威实现

Severity: High

以下逻辑在主项目和 `LCD_LINK` 中分别实现：

- LCD74000F TCP/IP 和串口通信。
- SCPI 查询、重试、`*OPC?` 和错误队列处理。
- S 参数兼容路由和链路命令列表。
- IP、端口、串口、波特率和超时默认值。

两份实现已经出现行为差异：独立版增加了 `query_command()`、`selected_command` 和可选串口依赖处理，主项目版本则继续使用主项目的共享默认值和硬件接口。

影响：协议修复、安全处理和设备兼容改动可能只落到一个项目，形成设备行为漂移。

建议：把 `lcd_link` 定义为 LCD74000F 唯一核心包，主项目硬件层使用轻量适配器包装它。若业务要求必须复制交付，则应明确版本号、上游来源和同步验证机制，并增加两份实现的一致性测试。

### ARCH-03 - 依赖装配没有集中到 Composition Root

Severity: Medium

`AppContext` 当前只创建 `InstrumentService` 和 `MainWindow`。具体硬件 Controller 仍由 `domains/instrument_management/controller_factory.py` 直接创建。

这使 domain 同时承担业务规则和基础设施选择，依赖方向表现为：

```text
domain controller factory -> concrete hardware controller
```

建议目标：

```text
domain -> controller Protocol
application composition root -> concrete hardware controller
hardware -> domain/application 定义的端口契约
```

Controller Factory 可以迁入 `application/` 或 `hardware/`，AppContext 根据连接配置完成具体实现装配。

### ARCH-04 - MainWindow 和 InstrumentService 仍是双重集中点

Severity: Medium

当前形成了两个较大的协调中心：

- `MainWindow` 集中 UI 状态、任务调度和流程回调。
- `InstrumentService` 集中设备生命周期、多个 domain service、兼容 API 和数据写入。

虽然 facade 模式适合作为迁移阶段的稳定边界，但目前 facade 仍包含较多实现细节。继续向其中加入功能会延长迁移周期。

建议：新增业务能力优先进入 domain 或 application controller；`InstrumentService` 只保留稳定外部 API 和异常转换；`MainWindow` 只保留 Widget 装配、信号连接和显示委托。

### ARCH-05 - LCD_LINK 的 Service/ViewModel 分层没有贯通

Severity: Medium

独立窗口直接创建并调用 `Lcd74000fSwitchBoxController`，`LinkService` 没有进入窗口调用链。`LinkControlViewModel` 定义在 `window.py` 内，链路图的 `set_link_state()` 当前为空实现，计算出的高亮 token 没有产生视图效果。

影响：Service 层成为未使用抽象，窗口继续同时承担连接状态、任务调度、业务调用和显示状态。

建议在独立小程序中明确选择一种结构：

- 简化方案：Window 直接调用 Controller，删除未使用 Service 和无效状态抽象。
- 分层方案：Window 只调用 ViewModel/Application Service，由该层管理 Controller 生命周期和命令状态。

如果链路图高亮是预期功能，应实现绘制逻辑；如果只是静态参考图，应删除高亮状态模型，避免产生错误架构信号。

### ARCH-06 - LCD_LINK 缺少后台任务生命周期管理

Severity: Medium

独立窗口使用全局 `QThreadPool` 执行硬件操作，关闭窗口时会直接断开 Controller。若窗口关闭时仍有连接、查询或发送操作运行，后台任务可能与 socket/serial 关闭并发发生。

建议：

- 由窗口或 application service 持有正在执行的 Worker。
- 关闭期间禁止启动新任务。
- 在释放 Controller 前等待任务结束，或实现可控取消和超时退出。
- 明确同一 Controller 是否允许并发命令；若不允许，应使用单工作队列串行执行。

### ARCH-07 - LCD_LINK 缺少独立自动化测试

Severity: Low

主项目测试覆盖了主项目硬件迁移、链路 Service 和 ViewModel，但没有测试直接导入 `lcd_link`。独立包的路由、Controller 重试、响应读取、窗口状态和关闭行为未被自动化保护。

建议在 `LCD_LINK/tests/` 建立独立测试集，并至少覆盖：

- TCP socket 和 serial transport 的成功、超时及断开。
- `*OPC?`、错误队列和有限重试。
- 路由命令规范化和非法输入。
- 连接、忙碌、断开和关闭状态。
- 包安装后的 `python -m lcd_link` 和 console script 导入检查。

### ARCH-08 - 源码直跑兼容逻辑进入了包入口

Severity: Low

`LCD_LINK/src/lcd_link/app.py` 和 `__main__.py` 都包含运行时 `sys.path` 注入，用于支持直接执行包内源文件。这解决了当前开发环境的启动问题，但会掩盖包没有安装或 `PYTHONPATH` 错误等部署问题。

建议长期保留标准入口：

```text
python -m lcd_link
lcd-link-control
```

如确实需要源码双击或直接执行，可在 `LCD_LINK/run.py` 或 Windows 启动脚本中集中处理路径，不让包内模块承担环境修复职责。

## 5. 建议目标架构

```text
quiet_zone_tester.app
  -> ApplicationContext / Composition Root
       -> MainShellController
       -> domain services
       -> hardware adapters
       -> TaskRunner

presentation views
  -> ViewModel / Qt Model
  -> MainShellController

domain services
  -> Protocol / domain models
  -X-> Qt Widget
  -X-> concrete hardware classes

hardware adapters
  -> transport
  -> shared lcd_link core

LCD_LINK standalone app
  -> LCD application service
  -> shared lcd_link core
```

LCD74000F 的推荐共享关系：

```text
lcd_link.core
  <- quiet_zone_tester.hardware LCD adapter
  <- LCD_LINK independent window
  <- LCD_LINK tests
```

## 6. 建议整改顺序

### P0 - 修正架构事实

1. 更新 README、迁移 TODO 和进度记录，区分“目录已建立”“职责已委托”“迁移已完成”。
2. 把 `ui/` 标注为当前 View 层及迁移兼容层。
3. 明确 `InstrumentService` 是临时 facade 还是长期公共 API。

### P1 - 统一 LCD 核心

1. 确定 LCD74000F 的唯一权威实现。
2. 让主项目和独立窗口消费同一 Controller、路由和默认配置。
3. 建立 `LCD_LINK/tests/`，覆盖协议和窗口状态。
4. 补齐后台任务关闭和 Controller 串行访问策略。

### P2 - 收口应用装配

1. 将具体 Controller 创建移出 domain。
2. 由 AppContext 装配 domain service、hardware adapter 和任务运行器。
3. 为扫描、手动运动和链路控制建立 application controller/use case。

### P3 - 瘦身旧主链

1. 将 MainWindow 中的任务参数拼装和流程回调迁入 application/presentation controller。
2. 删除 InstrumentService 中已经没有外部调用的兼容私有方法。
3. 完成 View 迁移后，再将旧 `ui/` 入口降级为兼容导出或删除。

### P4 - 清理兼容路径

1. 统计外部脚本对 `drivers/`、`instruments/` 和旧入口的使用。
2. 设置弃用版本和删除条件。
3. 删除兼容层前执行安装包、主窗口和真实硬件回归。

## 7. 验证记录

评审日期：2026-07-15

- 使用 UTF-8 读取项目文档和源文件。
- 主项目执行 `python -m unittest discover -s tests`。
- 共运行 184 个测试，全部通过，1 个测试跳过。
- `LCD_LINK/src` 执行源码编译检查并通过。
- 本次评审未连接真实 VNA、扫描架或 LCD74000F，因此不包含真实硬件协议和关闭竞态验证。

测试通过说明当前行为具备较好的回归保护，但不消除本文件列出的职责重复、依赖方向和长期维护风险。

## 8. 评审决策摘要

| 决策项 | 当前判断 |
| --- | --- |
| 当前架构阶段 | 渐进迁移中 |
| 旧 UI 是否只是兼容层 | 否，仍是运行主视图 |
| InstrumentService 是否已经完全瘦身 | 否，仍是大型 facade 和兼容协调器 |
| hardware 迁移是否基本完成 | 是 |
| presentation 迁移是否完成 | 否，Model/ViewModel 已落地，View 尚未迁完 |
| LCD_LINK 是否可独立运行 | 是 |
| LCD 实现是否已经单一来源 | 否 |
| 当前首要架构动作 | 统一 LCD 核心并纠正迁移状态 |
