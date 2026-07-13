# Keysight N5225B PNA 微波网络分析仪 — SCPI 常用指令参考

> **适用型号**: N522xB 系列（N5221B / N5222B / N5224B / N5225B / N5227B）  
> **频率范围**: 900 Hz / 10 MHz ~ 50 GHz  
> **接口**: GPIB / USB / LAN (VXI-11 / Sockets)  
> **编程手册**: [Keysight PNA Series Programming Help](https://helpfiles.keysight.com/csg/N52xxB/)

---

## 目录

1. [IEEE 488.2 通用指令](#1-ieee-4882-通用指令)
2. [系统配置 — SYSTem](#2-系统配置--system)
3. [显示控制 — DISPlay](#3-显示控制--display)
4. [激励参数 — SENSe](#4-激励参数--sense)
5. [计算与测量 — CALCulate](#5-计算与测量--calculate)
6. [信号源 — SOURce](#6-信号源--source)
7. [触发 — TRIGger](#7-触发--trigger)
8. [扫描控制 — INITiate](#8-扫描控制--initiate)
9. [数据格式与读取](#9-数据格式与读取)
10. [校准 — SENSe:CORRection](#10-校准--sensecorrection)
11. [状态报告 — STATus](#11-状态报告--status)
12. [典型测量流程](#12-典型测量流程)

---

## 1. IEEE 488.2 通用指令

| 指令 | 说明 |
|---|---|
| `*IDN?` | 查询仪器标识（厂商、型号、序列号、固件版本） |
| `*RST` | 复位到默认状态 |
| `*CLS` | 清除状态寄存器和错误队列 |
| `*ESE <mask>` | 设置事件状态使能寄存器 |
| `*ESR?` | 查询事件状态寄存器 |
| `*OPC` | 设置"操作完成"标志位 |
| `*OPC?` | 查询"操作完成"标志位（阻塞直到完成，返回 `+1`） |
| `*WAI` | 等待所有待处理操作完成再执行下一条指令 |
| `*STB?` | 查询状态字节 |
| `*SRE <mask>` | 设置服务请求使能寄存器 |
| `*TST?` | 自检 |
| `*SAV <n>` | 保存仪器状态到寄存器 n（0-9） |
| `*RCL <n>` | 从寄存器 n 调出仪器状态 |

---

## 2. 系统配置 — SYSTem

| 指令 | 说明 |
|---|---|
| `SYSTem:PRESet` | 系统预设（等同于前面板 Preset） |
| `SYSTem:FPReset` | 出厂复位（更彻底的复位） |
| `SYSTem:ERRor?` | 查询错误队列（返回 `code,"description"`） |
| `SYSTem:VERSion?` | 查询 SCPI 版本 |
| `SYSTem:DISPlay:UPDate ON|OFF|1|0` | 开/关屏幕刷新（关闭可加速批量配置） |
| `SYSTem:TIMe?` | 查询系统时间 |
| `SYSTem:COMMunicate:LAN:ADDRess?` | 查询 LAN IP 地址 |
| `SYSTem:COMMunicate:GPIB:ADDRess?` | 查询 GPIB 地址 |

---

## 3. 显示控制 — DISPlay

| 指令 | 说明 |
|---|---|
| `DISPlay:WINDow<w>:STATe ON|OFF` | 开/关窗口 w |
| `DISPlay:WINDow<w>:TITLe:DATA "<title>"` | 设置窗口标题 |
| `DISPlay:WINDow<w>:TRACe<t>:FEED "<meas>"` | 将测量分配给窗口 w 的迹线 t |
| `DISPlay:WINDow<w>:TRACe<t>:STATe ON|OFF` | 开/关迹线显示 |
| `DISPlay:WINDow<w>:TRACe<t>:DELete` | 删除迹线 |
| `DISPlay:WINDow<w>:CATalog?` | 查询窗口中的迹线列表 |

---

## 4. 激励参数 — SENSe

> 所有 `<ch>` 表示通道号（1, 2, 3...），省略时默认 Channel 1。

### 4.1 频率

| 指令 | 说明 |
|---|---|
| `SENSe<ch>:FREQuency:STARt <freq>` | 设置起始频率 (Hz) |
| `SENSe<ch>:FREQuency:STOP <freq>` | 设置终止频率 (Hz) |
| `SENSe<ch>:FREQuency:CENTer <freq>` | 设置中心频率 (Hz) |
| `SENSe<ch>:FREQuency:SPAN <freq>` | 设置频率跨度 (Hz) |
| `SENSe<ch>:FREQuency:CW <freq>` | 设置点频 (Hz)，用于 CW 模式 |
| `SENSe<ch>:FREQuency:STARt?` | 查询起始频率 |
| `SENSe<ch>:FREQuency:STOP?` | 查询终止频率 |

### 4.2 扫描

| 指令 | 说明 |
|---|---|
| `SENSe<ch>:SWEep:POINts <num>` | 设置扫描点数（1 ~ 200,001） |
| `SENSe<ch>:SWEep:TIME <time>` | 设置扫描时间 (秒) |
| `SENSe<ch>:SWEep:TIME:AUTO ON|OFF` | 自动扫描时间 |
| `SENSe<ch>:SWEep:MODE <mode>` | 扫描模式: `HOLD` / `CONTinuous` / `SINGle` / `GROups` |
| `SENSe<ch>:SWEep:TYPE LINear|LOGarithmic|SEGMent|POWer|CW` | 扫描类型 |
| `SENSe<ch>:SWEep:TYPE:POWer <num>` | 功率扫描点数 |
| `SENSe<ch>:SWEep:GROup:COUNt <num>` | Groups 模式下接收的触发数 |

### 4.3 中频带宽

| 指令 | 说明 |
|---|---|
| `SENSe<ch>:BWIDth:RESolution <bw>` | 设置 IF 带宽 (Hz)，典型值 10 ~ 600 kHz |
| `SENSe<ch>:BWIDth:RESolution:AUTO ON|OFF` | 自动 IF 带宽 |

### 4.4 平均

| 指令 | 说明 |
|---|---|
| `SENSe<ch>:AVERage:STATe ON|OFF` | 开/关平均 |
| `SENSe<ch>:AVERage:COUNt <num>` | 平均次数 |
| `SENSe<ch>:AVERage:CLEar` | 清除当前平均值，重新开始平均 |
| `SENSe<ch>:AVERage:MODE POINt|SWEep` | 平均模式：逐点 / 逐次扫描 |

---

## 5. 计算与测量 — CALCulate

### 5.1 测量参数

| 指令 | 说明 |
|---|---|
| `CALCulate<ch>:PARameter:DEFine:EXT "<name>","<param>"` | 创建新测量（扩展定义） |
| `CALCulate<ch>:PARameter:DEFine "<name>",<param>` | 创建新测量（简写） |
| `CALCulate<ch>:PARameter:SELect "<name>"` | 选择当前激活的测量 |
| `CALCulate<ch>:PARameter:COUNt?` | 查询通道上的测量数量 |
| `CALCulate<ch>:PARameter:CATalog?` | 查询测量列表 |
| `CALCulate<ch>:PARameter:DELete "<name>"` | 删除测量 |
| `CALCulate<ch>:MEASure<meas>:PARameter "<param>"` | 旧式参数分配 |

> **参数类型**: `S11`, `S21`, `S12`, `S22`, `S33`, `S44`, `A1`, `B1`, `R1`, `IMPtr1`, `ADMIt1`, `Kfact`, `SMITht`, etc.

### 5.2 显示格式

| 指令 | 说明 |
|---|---|
| `CALCulate<ch>:FORMat <format>` | 设置显示格式 |

> **可选格式**:
> | 格式 | 说明 |
> |---|---|
> | `MLOGarithmic` | 对数幅度 (dB) |
> | `MLINear` | 线性幅度 |
> | `PHASe` | 相位 (°) |
> | `REAL` | 实部 |
> | `IMAGinary` | 虚部 |
> | `SWR` | 驻波比 |
> | `SMITht` | 史密斯圆图 |
> | `POLAR` | 极坐标 |
> | `GDELay` | 群延迟 |
> | `IMPedance` | 阻抗 |
> | `ADMittance` | 导纳 |

### 5.3 标记 (Marker)

| 指令 | 说明 |
|---|---|
| `CALCulate<ch>:MARKer<m>:STATe ON|OFF` | 开/关标记 m |
| `CALCulate<ch>:MARKer<m>:X <freq>` | 设置标记 X 轴位置 (Hz) |
| `CALCulate<ch>:MARKer<m>:Y?` | 查询标记 Y 值 |
| `CALCulate<ch>:MARKer<m>:SEARch:MAXimum` | 搜索最大值 |
| `CALCulate<ch>:MARKer<m>:SEARch:MINimum` | 搜索最小值 |
| `CALCulate<ch>:MARKer<m>:SEARch:TARGet <val>` | 搜索目标值 |
| `CALCulate<ch>:MARKer<m>:REFerence` | 设置参考标记 |

### 5.4 数学运算

| 指令 | 说明 |
|---|---|
| `CALCulate<ch>:MATH:MEMorize` | 存储当前迹线到内存 |
| `CALCulate<ch>:MATH:FUNCtion <func>` | 数学运算: `NORMal` / `SUBTract` / `ADD` / `MULTiply` / `DIVide` |
| `CALCulate<ch>:MATH:STATe ON|OFF` | 开/关数学运算 |

---

## 6. 信号源 — SOURce

| 指令 | 说明 |
|---|---|
| `SOURce<ch>:POWer<port>:LEVel:IMMediate:AMPLitude <power>` | 设置端口功率 (dBm) |
| `SOURce<ch>:POWer<port>:LEVel:IMMediate:AMPLitude?` | 查询端口功率 |
| `SOURce<ch>:POWer<port>:MODE ON|OFF` | 开/关端口功率输出 |
| `SOURce<ch>:POWer<port>:ATTenuation <att>` | 设置端口衰减 (dB) |
| `SOURce<ch>:POWer:STARt <power>` | 功率扫描起始功率 (dBm) |
| `SOURce<ch>:POWer:STOP <power>` | 功率扫描终止功率 (dBm) |
| `SOURce<ch>:POWer:CORRection:COLLect <mode>` | 功率校准采集模式 |

---

## 7. 触发 — TRIGger

| 指令 | 说明 |
|---|---|
| `TRIGger:SOURce <source>` | 触发源: `IMMediate` / `MANual` / `EXTernal` / `BUS` |
| `TRIGger:SCOPe <scope>` | 触发范围: `ALL`（全局）/ `CURRent`（当前通道） |
| `TRIGger:SLOPe POSitive|NEGative` | 触发边沿极性 |
| `TRIGger:TYPE EDGE|LEVEL` | 触发检测类型 |
| `TRIGger:SEQuence:SOURce <source>` | 序列触发源 |

---

## 8. 扫描控制 — INITiate

| 指令 | 说明 |
|---|---|
| `INITiate<ch>:IMMediate` | 立即触发一次扫描（手动触发模式下） |
| `INITiate<ch>:CONTinuous ON|OFF` | 开/关连续扫描 |
| `ABORt` | 中止当前扫描 |

---

## 9. 数据格式与读取

### 9.1 数据格式

| 指令 | 说明 |
|---|---|
| `FORMat:DATA ASCii|REAL,32|REAL,64` | 设置数据传输格式 |
| `FORMat:BORDer NORMal|SWAPped` | 二进制模式下的字节序 |

### 9.2 读取测量数据

| 指令 | 说明 |
|---|---|
| `CALCulate<ch>:DATA? FDATA` | 读取当前格式化数据（已应用校准和格式转换） |
| `CALCulate<ch>:DATA:FDATa?` | 同上（简写），返回 `值,频率,值,频率,...` 交替格式 (E5071C) |
| `CALCulate<ch>:MEASure<meas>:DATA:FDATa?` | 读取指定测量的格式化数据 |
| `CALCulate<ch>:DATA:SDATa?` | 读取未格式化的 S 参数复数数据 |
| `CALCulate<ch>:DATA:RAW?` | 读取原始未校准数据 |
| `SENSe<ch>:DATA:CORRected?` | 读取已修正的激励数据 |
| `SENSe<ch>:FREQuency:DATA?` | 读取频率点列表 |

> **N5225B 典型用法**:
> ```
> FORM:DATA ASCII                    ' 设置 ASCII 格式
> CALCulate:DATA? FDATA             ' 读取格式化数据
> ```
> 返回逗号分隔的数值列表（仅值，频率需单独计算）。

### 9.3 SnP 文件

| 指令 | 说明 |
|---|---|
| `MMEMory:STORe:TRACe:SNP <trace>,"<file>.s2p"` | 保存迹线为 SnP 文件 |
| `MMEMory:LOAD:SNP "<file>.s2p"` | 加载 SnP 文件 |

---

## 10. 校准 — SENSe:CORRection

| 指令 | 说明 |
|---|---|
| `SENSe<ch>:CORRection:STATe ON|OFF` | 开/关校准 |
| `SENSe<ch>:CORRection:COLLect:METHod <method>` | 校准方法: `SOLT1` / `SOLT2` / `TRL1` / `TRL2` / `ECAL` |
| `SENSe<ch>:CORRection:COLLect:ACQuire <standard>` | 采集校准标准: `OPEN` / `SHORT` / `LOAD` / `THRU` |
| `SENSe<ch>:CORRection:COLLect:SAVE` | 保存校准数据 |
| `SENSe<ch>:CORRection:COLLect:GUIDed "<ckt>"` | 引导式校准选择校准件 |
| `SENSe<ch>:CORRection:COLLect:CKIT "<name>"` | 选择校准套件（如 "85052B"、"85033E"） |
| `SENSe<ch>:CORRection:PREFerence:CSET:SAVE USER|CALR|REUSE` | 校准集保存策略 |

---

## 11. 状态报告 — STATus

| 指令 | 说明 |
|---|---|
| `STATus:OPERation:CONDition?` | 查询操作状态条件寄存器 |
| `STATus:OPERation:EVENt?` | 查询操作状态事件寄存器 |
| `STATus:OPERation:ENABle <mask>` | 设置操作状态使能寄存器 |
| `STATus:QUEStionable:ENABle <mask>` | 设置可疑状态使能寄存器 |
| `STATus:QUEStionable:EVENt?` | 查询可疑状态事件寄存器 |

---

## 12. 典型测量流程

### 12.1 基本 S 参数测量（最简）

```
*RST                                    ' 复位
SENSe1:FREQuency:STARt 1e9             ' 起始频率 1 GHz
SENSe1:FREQuency:STOP 5e9              ' 终止频率 5 GHz
SENSe1:SWEep:POINts 201                ' 点数 201
SENSe1:BWIDth:RESolution 10e3          ' IF 带宽 10 kHz
SOURce:POWer1:LEVel:IMMediate:AMPLitude 0   ' 功率 0 dBm
CALCulate1:PARameter:DEFine "Meas",S11 ' 定义测量
CALCulate1:FORMat MLOGarithmic         ' 格式 MLOG
INITiate:CONTinuous ON                 ' 开始连续扫描

' --- 读取数据 ---
FORM:DATA ASCII
CALCulate1:DATA? FDATA
```

### 12.2 多 S 参数 + 不同格式

```
*RST
SENS1:FREQ:STAR 2e9; STOP 18e9
SENS1:SWE:POIN 401
SENS1:BWID 30e3

CALC1:PAR:DEF:EXT 'S11_dB','S11'
CALC1:PAR:DEF:EXT 'S21_dB','S21'
CALC1:PAR:DEF:EXT 'S11_SWR','S11'

CALC1:PAR:SEL 'S11_dB'
CALC1:FORM MLOG
CALC1:PAR:SEL 'S21_dB'
CALC1:FORM MLOG
CALC1:PAR:SEL 'S11_SWR'
CALC1:FORM SWR

DISP:WIND1:TRAC1:FEED 'S11_dB'
DISP:WIND1:TRAC2:FEED 'S21_dB'
DISP:WIND1:TRAC3:FEED 'S11_SWR'

INIT:CONT ON
```

### 12.3 功率扫描

```
*RST
SENS1:FREQ 2e9                         ' 点频 2 GHz
SENS1:SWE:TYPE POW                     ' 功率扫描模式
SOUR1:POW:STAR -30; STOP 0             ' 功率范围 -30 ~ 0 dBm
SENS1:SWE:POIN 51                      ' 51 个点
CALC1:PAR:DEF "Meas",S21
INIT:CONT ON
```

### 12.4 VISA / Python 连接示例

```python
import pyvisa

rm = pyvisa.ResourceManager()
# LAN 连接
pna = rm.open_resource("TCPIP0::192.168.1.100::inst0::INSTR")
pna.timeout = 10000

# 查询 ID
print(pna.query("*IDN?"))

# 配置扫频
pna.write("SENSe1:FREQuency:STARt 1e9")
pna.write("SENSe1:FREQuency:STOP 10e9")
pna.write("SENSe1:SWEep:POINts 401")
pna.write("CALCulate1:PARameter:DEFine:EXT 'Meas','S21'")
pna.write("CALCulate1:FORMat MLOGarithmic")

# 单次扫描并读取数据
pna.write("INITiate1:CONTinuous OFF")
pna.write("INITiate1:IMMediate")
pna.query("*OPC?")                     # 等待完成

pna.write("FORMat:DATA ASCII")
data_str = pna.query("CALCulate1:DATA? FDATA")
values = [float(v) for v in data_str.strip().split(',')]
print(f"读取到 {len(values)} 个数据点")
```

## 附录：仪器连接地址格式

| 接口 | VISA 资源字符串格式 |
|---|---|
| LAN (VXI-11) | `TCPIP0::192.168.1.100::inst0::INSTR` |
| LAN (Sockets) | `TCPIP0::192.168.1.100::5025::SOCKET` |
| GPIB | `GPIB0::16::INSTR` |
| USB | `USB0::0x2A8D::0x0101::MY12345678::INSTR` |

> **默认端口**: VXI-11 = `inst0`, Sockets = `5025`

---

> 📖 **官方文档**: [Keysight PNA Programming Help (N52xxB)](https://helpfiles.keysight.com/csg/N52xxB/)
