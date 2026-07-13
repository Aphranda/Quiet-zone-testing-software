# Keysight N5245B PNA-X 网络分析仪 SCPI 常用指令参考

> **适用型号**：Keysight N5245B，以及使用 N52xxB Programming Help 命令集的 PNA/PNA-X B 系列  
> **N5245B 频率范围**：10 MHz ~ 50 GHz（实际端口、选件和许可能力以仪器配置为准）  
> **接口**：LAN（VXI-11 / HiSLIP / Raw Socket）、USB、GPIB  
> **官方资料**：[PNA Series Programming Help](https://helpfiles.keysight.com/csg/N52xxB/)

本文面向本项目从现有 E5080B 增加 N5245B 后的扫频、S 参数配置和复数数据采集。N5245B
使用 N52xxB PNA 编程命令族；两台仪器对项目所需的基础 SCPI 指令兼容。不要根据前面板显示格式读取测量结果，
程序应读取 `SDATA` 的实部/虚部对。

## 1. 连接与识别

| 用途 | 指令 |
|---|---|
| 查询厂商、型号、序列号、固件 | `*IDN?` |
| 清除状态和错误队列 | `*CLS` |
| 查询最近一条系统错误 | `SYSTem:ERRor?` |
| 等待前序操作完成 | `*OPC?` |
| 中止当前操作 | `ABORt` |
| 系统预设 | `SYSTem:PRESet` |

典型 `*IDN?` 返回值包含 `Keysight Technologies,N5245B,...`。软件选择 N5245B 时应核对
返回值第二段，避免连接到错误型号。

常用 VISA 地址：

```text
TCPIP0::192.168.1.10::inst0::INSTR     # VXI-11
TCPIP0::192.168.1.10::hislip0::INSTR   # HiSLIP
TCPIP0::192.168.1.10::5025::SOCKET     # Raw Socket
```

Raw Socket 通常使用端口 5025，并以换行符结束命令。

## 2. 通道与扫频

以下 `<ch>` 为通道号；省略时通常使用通道 1。

| 用途 | 指令 |
|---|---|
| 起始频率 | `SENSe<ch>:FREQuency:STARt <Hz>` |
| 终止频率 | `SENSe<ch>:FREQuency:STOP <Hz>` |
| 中心频率 | `SENSe<ch>:FREQuency:CENTer <Hz>` |
| 频率跨度 | `SENSe<ch>:FREQuency:SPAN <Hz>` |
| 扫描点数 | `SENSe<ch>:SWEep:POINts <count>` |
| 扫描类型 | `SENSe<ch>:SWEep:TYPE LINear|LOGarithmic|SEGMent|POWer|CW` |
| IF 带宽 | `SENSe<ch>:BWIDth:RESolution <Hz>` |
| 查询频率点数组 | `SENSe<ch>:FREQuency:DATA?` |

建议显式指定通道，避免仪器当前活动通道变化影响程序：

```text
SENS1:FREQ:STAR 10E9
SENS1:FREQ:STOP 17E9
SENS1:SWE:POIN 801
SENS1:SWE:TYPE LIN
SENS1:BAND:RES 1000
```

## 3. 源功率

PNA-X 可以按端口配置功率。推荐使用包含通道和端口的完整命令：

```text
SOUR1:POW1:LEV:IMM:AMPL -10
SOUR1:POW2:LEV:IMM:AMPL -10
```

| 用途 | 指令 |
|---|---|
| 设置端口功率 | `SOURce<ch>:POWer<port>:LEVel:IMMediate:AMPLitude <dBm>` |
| 查询端口功率 | `SOURce<ch>:POWer<port>:LEVel:IMMediate:AMPLitude?` |
| 端口输出开关 | `SOURce<ch>:POWer<port>:MODE ON|OFF` |
| 端口衰减 | `SOURce<ch>:POWer<port>:ATTenuation <dB>` |

简写 `SOUR:POW <dBm>` 依赖当前通道/端口状态。自动化程序优先使用完整写法。

## 4. S 参数测量

创建并选择测量：

```text
CALC1:PAR:DEF:EXT 'QZT_S21','S21'
CALC1:PAR:SEL 'QZT_S21'
DISP:WIND1:TRAC1:FEED 'QZT_S21'
```

| 用途 | 指令 |
|---|---|
| 创建扩展测量 | `CALCulate<ch>:PARameter:DEFine:EXT '<name>','<parameter>'` |
| 创建标准测量 | `CALCulate<ch>:PARameter:DEFine '<name>',<parameter>` |
| 选择测量 | `CALCulate<ch>:PARameter:SELect '<name>'` |
| 查询测量目录 | `CALCulate<ch>:PARameter:CATalog?` |
| 删除测量 | `CALCulate<ch>:PARameter:DELete '<name>'` |
| 将测量送到显示迹线 | `DISPlay:WINDow<w>:TRACe<t>:FEED '<name>'` |

常用参数为 `S11`、`S21`、`S12`、`S22`；多端口机型还可使用对应端口组合。项目当前
控制器接受 `S11` 到 `S44`。

## 5. 触发与单次扫描

自动采集推荐关闭连续扫描，再触发一次并等待完成：

```text
INIT1:CONT OFF
TRIG:SOUR IMM
INIT1:IMM
*OPC?
```

| 用途 | 指令 |
|---|---|
| 连续扫描开关 | `INITiate<ch>:CONTinuous ON|OFF` |
| 立即触发通道 | `INITiate<ch>:IMMediate` |
| 触发源 | `TRIGger:SOURce IMMediate|MANual|EXTernal|BUS` |
| 等待完成 | `*OPC?` |

`*OPC?` 的通信超时必须长于当前扫描时间。点数较多、IFBW 较窄或启用平均时，应增大超时。

## 6. 数据读取

### 6.1 复数 S 参数（推荐）

```text
FORM:DATA REAL,64
FORM:BORD SWAP
CALC1:DATA? SDATA
```

`SDATA` 返回交替排列的复数分量：

```text
real[0], imag[0], real[1], imag[1], ...
```

`REAL,64` 每个数为 8 字节浮点数。`FORM:BORD SWAP` 表示交换字节序，常用于 PC 小端解析；
必须让 VISA 库的端序设置与仪器保持一致。

### 6.2 ASCII 回退

```text
FORM:DATA ASC,0
CALC1:DATA? SDATA
```

ASCII 较慢，但便于诊断二进制块或端序问题。

### 6.3 格式化数据

```text
CALC1:FORM MLOG
CALC1:DATA? FDATA
```

`FDATA` 受当前显示格式影响，只适合明确需要 dB、相位等格式化值的场景。读取原始复数
S 参数时使用 `SDATA`。

## 7. 平均与校准状态

| 用途 | 指令 |
|---|---|
| 开关平均 | `SENSe<ch>:AVERage:STATe ON|OFF` |
| 平均次数 | `SENSe<ch>:AVERage:COUNt <count>` |
| 清除平均结果 | `SENSe<ch>:AVERage:CLEar` |
| 开关误差修正 | `SENSe<ch>:CORRection:STATe ON|OFF` |

自动化程序通常不应隐式复位或关闭校准。连接后保留仪器校准状态，仅修改本次测试明确要求的
频率、点数、IFBW、功率和测量参数。

## 8. 本项目推荐流程

```text
*IDN?
*CLS
SENS1:FREQ:STAR 10E9
SENS1:FREQ:STOP 17E9
SENS1:SWE:POIN 801
SENS1:BAND:RES 1000
SOUR1:POW1:LEV:IMM:AMPL -10
CALC1:PAR:DEF:EXT 'CH1_SPARAM','S21'
CALC1:PAR:SEL 'CH1_SPARAM'
INIT1:CONT OFF
INIT1:IMM
*OPC?
FORM:DATA REAL,64
FORM:BORD SWAP
CALC1:DATA? SDATA
SYST:ERR?
```

采集后应验证：返回数值个数为偶数、复数点数与扫描点数一致、频率轴长度一致，以及
`SYST:ERR?` 返回 `0,"No error"`（文本大小写可能随固件变化）。

## 9. 与现有 E5080B 的兼容性

本项目使用的下列基础命令族在 E5080B 与 N5245B 间一致：

- `SENS:FREQ`、`SENS:SWE:POIN`、`SENS:BAND:RES`
- `CALC:PAR:DEF:EXT`、`CALC:PAR:SEL`
- `INIT:IMM`、`*OPC?`
- `FORM:DATA`、`FORM:BORD`、`CALC:DATA? SDATA`
- `SYST:ERR?`

N5245B 是 PNA-X，具备更多源、接收机、噪声和非线性测量能力；这些能力通常依赖硬件选件，
不在本项目基础 S 参数采集范围内。不要仅凭型号假定某个高级命令可用，应查询仪器选件并参考
对应固件版本的官方 Programming Help。

## 10. 开源实现交叉验证

以下公开驱动源码于 2026-07-13 进行了交叉核对：

| 项目 | 与本文一致的实现 | 结论 |
|---|---|---|
| [scikit-rf Keysight PNA 驱动](https://github.com/scikit-rf/scikit-rf/blob/master/skrf/vi/vna/keysight/pna.py) | 明确将 `N5245B` 列为 PNA-X；使用 `SENS:FREQ:STAR/STOP`、`SENS:SWE:POIN`、`SENS:BWID`、`TRIG:SOUR`、`CALC:PAR:SEL`、`CALC:DATA? SDATA`、`FORM REAL,64` 和 `FORM:BORD SWAP` | 直接验证 N5245B 归属及本项目的核心扫频、触发和复数数据读取路径 |
| [QCoDeS Keysight N52xx 驱动](https://github.com/QCoDeS/Qcodes/blob/main/src/qcodes/instrument_drivers/Keysight/N52xx.py) | 使用 `SOUR:POW`、`SENS:BAND`、`SENS:FREQ:*`、`SENS:SWE:POIN`、`SENS:SWE:MODE`、`TRIG:SOUR`、`CALC:PAR:SEL`、`FORM REAL,32` 和二进制 `CALC:DATA? FDATA` | 验证 PNA 系列的频率、功率、IFBW、扫描模式、触发和二进制数据格式命令 |
| [PyMeasure Keysight PNA 驱动](https://github.com/pymeasure/pymeasure/blob/master/pymeasure/instruments/keysight/keysightPNA.py) | 使用 `INIT<ch>:IMM`、`CALC<ch>:MEAS<tr>:DATA:SDATA?`，并支持 ASCII、REAL32、REAL64 和交换字节序 | 独立验证单次触发、复数 SDATA 数据及端序处理 |

不同开源驱动使用的测量访问形式略有差异：

- scikit-rf 使用活动测量形式 `CALC<ch>:DATA? SDATA`。
- PyMeasure 使用指定测量形式 `CALC<ch>:MEAS<tr>:DATA:SDATA?`。
- scikit-rf 创建测量时使用 `CALC<ch>:PAR:EXT`；本项目还依次尝试
  `CALC:PAR:MOD`、`CALC:PAR:DEF:EXT` 和 `CALC:PAR:DEF`，并通过 `SYST:ERR?`
  判断是否成功，以兼容仪器当前已有迹线及不同命令形式。

交叉验证覆盖的是基础 S 参数测量链路，不代表开源项目验证了 N5245B 的噪声、互调、频偏、
脉冲或其他选件功能。

## 11. 资料来源

- Keysight PNA Series Programming Help（N52xxB 命令族）：<https://helpfiles.keysight.com/csg/N52xxB/>
- 仓库内 N5225B 参考：[N5225B_SCPI_Command_Reference.md](N5225B_SCPI_Command_Reference.md)
- scikit-rf PNA/PNA-X 驱动：<https://github.com/scikit-rf/scikit-rf/blob/master/skrf/vi/vna/keysight/pna.py>
- QCoDeS N52xx 驱动：<https://github.com/QCoDeS/Qcodes/blob/main/src/qcodes/instrument_drivers/Keysight/N52xx.py>
- PyMeasure Keysight PNA 驱动：<https://github.com/pymeasure/pymeasure/blob/master/pymeasure/instruments/keysight/keysightPNA.py>

Keysight 帮助站可能限制目录抓取或调整深层链接。本文只整理基础 PNA SCPI 命令，不替代特定
固件版本的官方命令参数、选件限制和错误说明。
