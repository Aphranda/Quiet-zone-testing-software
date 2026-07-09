# 微波暗室静区自动化测试系统

本项目是一套面向微波暗室静区测试的桌面端自动化测试程序，目标是完成仪器连接、扫描架控制、VNA 扫频采样、实时曲线显示、数据处理和静态测试报告生成。

## 核心技术栈

- 语言：Python 3.10+
- UI 框架：PySide6
- 仪器通信：PyVISA，SCPI/VISA 协议；PySerial，Modbus RTU 协议
- 数据处理：NumPy
- 实时绘图：PyQtGraph
- 静态报告：Matplotlib
- 日志：Python `logging`

## 分层架构

项目必须严格遵循 UI 层、业务逻辑层、硬件驱动层分离。

- UI 层：`src/quiet_zone_tester/ui`
  负责窗口、控件、用户交互、实时曲线显示和状态提示。UI 层不得直接访问仪器，不得执行阻塞硬件 I/O。

- 业务逻辑层：`src/quiet_zone_tester/services`
  负责编排测试流程，例如仪器连接、扫频配置、预览采样、扫描架扫描、数据保存和报告生成。业务层通过驱动接口访问硬件。

- 驱动接口层：`src/quiet_zone_tester/drivers`
  负责 VNA、扫描架、开关箱等设备的统一接口定义和 Mock 后端。

- 真实仪器层：`src/quiet_zone_tester/instruments`
  负责真实 VNA、扫描架、开关箱等设备的通信封装。真实设备控制代码必须基于统一接口实现，不得放入 UI 层。

- 数据模型层：`src/quiet_zone_tester/models`
  负责 S 参数、位置、扫描结果等跨层共享的数据结构。

## 线程与 UI 响应规范

UI 线程绝不能被硬件 I/O 阻塞。

- 仪器连接、SCPI 查询、扫频采样、扫描架运动等耗时操作必须放入 `QThread` 或等价异步机制。
- UI 层只负责发起任务和接收结果信号。
- 后台任务返回后，由主线程更新控件、曲线和状态栏。
- 禁止在按钮回调中直接执行 VISA 读写、长时间循环或文件报告生成。

## Mock 与真实测试模式

任何硬件控制类都必须提供对应 Mock 类。

- VNA Controller 必须有 Mock VNA，可生成合理的 S 参数幅度、相位和频率轴数据。
- 扫描架 Controller 必须有 Mock Positioner，可模拟当前位置、运动完成和基本限位行为。
- 开关箱 Controller 必须有 Mock Switch Box，可模拟 S 参数到开关通道的切换。
- Mock 后端用于自动化测试、离线开发和 UI 联调，不作为当前软件默认连接模式。
- 当前软件主流程为真实测试模式，必须连接网分仪、扫描架和开关箱后才能开始测试。连接面板只暴露真实 VNA VISA 资源、真实扫描架串口参数，以及 TC500/LCD74000F 开关箱 TCP/IP 或串口参数。

## VISA/SCPI 异常处理规范

硬件通信代码必须把超时、断开、非法响应作为常态处理。

- 所有 VISA 读写必须使用 `try-except` 包裹。
- 必须记录关键通信日志，包括资源名、命令、失败原因和重试次数。
- 必须提供超时和有限重试机制。
- 驱动层异常不得直接泄漏到 UI 层，业务层应转换为可展示的错误信息。
- 断开连接时应尽量释放资源，即使部分设备已经异常离线。

## 性能规范

射频数据处理和绘图必须优先使用 NumPy 向量化。

- 大点数 S 参数幅相转换不得使用逐点 Python `for` 循环。
- 实时曲线使用 PyQtGraph 更新，避免 Matplotlib 参与实时刷新。
- Matplotlib 仅用于测试报告、离线图表和静态导出。
- 多维扫描数据应使用结构化数组或明确的数据模型保存，避免散乱字典在多层之间传递。

## 当前项目结构

```text
src/quiet_zone_tester/
  app.py                    # QApplication 入口
  main.py                   # 命令行入口
  logging_config.py         # 日志初始化
  drivers/
    base.py                 # VNA/扫描架/开关箱驱动接口
    mock_vna.py             # Mock VNA
    mock_positioner.py      # Mock 扫描架
    mock_switch_box.py      # Mock 开关箱
  instruments/
    visa_scpi.py            # VISA/SCPI 会话封装
    vna_scpi.py             # 真实 VNA 控制器
    switch_box_tc500.py     # TC500 开关箱控制器
    switch_box_lcd74000f.py # LCD74000F 开关箱控制器
    modbus_rtu.py           # Modbus RTU 串口会话封装
    positioner_icl.py       # iCL-RS 扫描架控制器，X/Y 对应厂家 Axis03/Axis04，实际 Modbus ID 为 2/3
  models/
    rf_data.py              # S 参数数据模型
    scan_config.py          # X/Y 二维扫描区间模型
  services/
    instrument_service.py   # 仪器业务流程
  ui/
    async_task.py           # QThread 后台任务封装
    main_window.py          # 主窗口
    widgets/                # 连接、参数、绘图、日志面板
```

## 运行方式

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m quiet_zone_tester
```

开发阶段也可以在项目根目录直接运行：

```powershell
python run.py
```

当前默认使用真实测试模式。VNA 通过 VISA 资源连接；扫描架参考 `resource/iCL-RS` 控制代码，使用串口 Modbus RTU 连接，只有 X/Y 两轴。厂家 RZDemo 使用 `Dimension.Axis03` 与 `Dimension.Axis04` 控制 X/Y，但该枚举实际值分别为 2 和 3，软件界面中的 X/Y 轴 ID 默认也使用 2/3；串口参数默认匹配 RZDemo 的 115200、8N1。扫描架配置中，X/Y 轴 ID 后提供“运动”和“停止”按钮，用于按默认速度点动对应轴并立即停止。

测试参数提供两种扫描模式：

- 步进测试：配置 X/Y 扫描区间、步进间隔、步进速度和到点延时。扫描架运动到每个步进点后等待延时，随后触发 VNA 读取数据，再进入下一个点。
- 匀速测试：配置运行轴、运行速度和运行时间。扫描架按指定速度连续运行，VNA 在运行期间持续读取数据；速度可为负值，用于反向点动。

开关箱可在 TC500 与 LCD74000F 间手动切换，TC500 保留原文本指令，LCD74000F 参考 `resource/LCD74000F.md` 使用 `CONFigure:LINK ...` 链路指令。测试采样前会按 S 参数发送对应开关箱切换命令。Mock 类保留在 `drivers` 下，仅用于测试和离线联调。

## 开发工作流

每次开发新模块前，先给出概要设计，包括核心类、职责边界和调用流程。

代码输出或说明必须明确文件路径，例如：

```text
// filepath: src/quiet_zone_tester/instruments/vna_scpi.py
```

新增模块必须遵守：

- UI 层不直接访问硬件。
- 真实驱动和 Mock 驱动同步设计。
- VISA 通信必须有日志、异常处理和重试。
- 数据处理使用 NumPy 向量化。
- 可运行、可测试优先于一次性堆叠功能。
