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

项目按应用装配、业务域、硬件适配、展示模型和旧 UI 兼容层拆分。

- APP 层：`src/quiet_zone_tester/application`
  负责应用级依赖装配、后台任务运行器和扫描工作流状态。

- 业务域：`src/quiet_zone_tester/domains`
  负责仪表连接、链路路由、运动控制、采样、扫描运行、数据保存和报告导出。业务域不依赖 Qt Widget。

- 硬件适配层：`src/quiet_zone_tester/hardware`
  负责统一硬件接口、Mock 实现、真实 VNA/扫描架/开关箱实现和 transport helper。

- 展示模型层：`src/quiet_zone_tester/presentation`
  负责 ViewModel、Qt model 和面向 UI 的状态派生。

- UI 兼容层：`src/quiet_zone_tester/ui`
  负责现有 Qt Widget、主窗口装配和旧控件入口。UI 层不得直接访问真实硬件 controller，不得执行阻塞硬件 I/O。

- 旧兼容路径：`src/quiet_zone_tester/drivers`、`src/quiet_zone_tester/instruments`
  仅保留 deprecated re-export，新代码应从 `quiet_zone_tester.hardware` 导入。

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
  app.py                    # QApplication 创建和全局样式
  main.py                   # 程序入口，规范入口函数为 Main()
  application/              # AppContext、TaskRunner、扫描工作流状态
  domains/                  # acquisition/data/instrument/link/motion/scan 等业务域
  hardware/                 # interfaces、mock、vna、positioner、switch_box、transport
  presentation/             # ViewModel 和 Qt model
  drivers/                  # deprecated 兼容 re-export
  instruments/              # deprecated 兼容 re-export
  models/
    rf_data.py              # S 参数数据模型
    scan_config.py          # X/Y 二维扫描区间模型
  services/
    instrument_service.py   # facade，委托到 domain service
  ui/
    async_task.py           # deprecated 兼容 re-export
    main_window.py          # 主窗口
    widgets/                # 连接、参数、绘图、日志面板
```

## 运行方式

推荐使用 uv 管理虚拟环境和依赖：

```powershell
python -m pip install --user uv
$env:UV_CACHE_DIR='.uv-cache'
python -m uv sync
python -m uv run python -m quiet_zone_tester
```

如果本机 `uv` 命令已经在 PATH 中，也可以直接使用：

```powershell
$env:UV_CACHE_DIR='.uv-cache'
uv sync
uv run python -m quiet_zone_tester
```

传统 venv/pip 方式仍可作为备用：

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

开关箱可在 TC500 与 LCD74000F 间手动切换，TC500 保留原文本指令，LCD74000F 参考 `resource/LCD74000F.md` 使用 `CONFigure:LINK ...` 链路指令。测试采样前会按 S 参数发送对应开关箱切换命令。Mock 类位于 `hardware/mock`，用于测试和离线联调。

## 测试与验证

标准测试使用 `unittest`：

```powershell
$env:UV_CACHE_DIR='.uv-cache'
$env:QT_QPA_PLATFORM='offscreen'
python -m uv run python -m unittest discover -s tests
```

主窗口 offscreen 初始化检查：

```powershell
$env:UV_CACHE_DIR='.uv-cache'
$env:QT_QPA_PLATFORM='offscreen'
python -m uv run python -c "from PySide6.QtWidgets import QApplication; from quiet_zone_tester.application import create_app_context; app=QApplication([]); w=create_app_context().create_main_window(); w.resize(1200, 800); w.show(); app.processEvents(); print('ok')"
```

真实硬件验证按 [docs/HARDWARE_VALIDATION_CHECKLIST.md](docs/HARDWARE_VALIDATION_CHECKLIST.md) 执行。硬件集成测试默认跳过；只有显式设置环境变量时才会启用：

```powershell
$env:RUN_HARDWARE_INTEGRATION='1'
$env:HARDWARE_VNA_RESOURCE='TCPIP0::192.168.1.10::5025::SOCKET'
$env:HARDWARE_POSITIONER_PORT='COM3'
$env:HARDWARE_SWITCH_BOX_MODEL='LCD74000F'
python -m uv run python -m unittest tests.test_hardware_integration_smoke
```

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
