# Keysight E5080B ENA 网络分析仪 SCPI 常用指令参考

> **适用型号**：Keysight E5080B ENA  
> **频率范围**：随硬件配置和选件变化，常见上限覆盖 4.5 GHz 至 53 GHz；以 `*IDN?`、`*OPT?` 和铭牌为准  
> **接口**：LAN（VXI-11 / HiSLIP / Raw Socket）、USB、GPIB  
> **官方帮助入口**：<https://helpfiles.keysight.com/csg/e5080b/>

本文汇总本项目需要的连接、线性扫频、S 参数、单次触发和复数数据读取命令，并补充平均、
校准状态、迹线显示、存储和诊断命令。命令中的 `<ch>`、`<port>`、`<trace>` 分别表示通道、
端口和迹线编号。

## 1. 识别、状态与诊断

| 用途 | SCPI 指令 |
|---|---|
| 查询厂商、型号、序列号、固件 | `*IDN?` |
| 查询已安装选件 | `*OPT?` |
| 清除状态寄存器和错误队列 | `*CLS` |
| 等待前序操作完成 | `*OPC?` |
| 查询最近一条错误 | `SYSTem:ERRor?` |
| 查询错误数量 | `SYSTem:ERRor:COUNt?` |
| 中止当前操作 | `ABORt` |
| 系统预设 | `SYSTem:PRESet` |

典型连接检查：

```text
*IDN?
*OPT?
SYST:ERR?
```

软件选择 E5080B 时，应检查 `*IDN?` 返回值的第二段是否为 `E5080B`。

## 2. VISA 网络地址

```text
TCPIP0::192.168.1.10::inst0::INSTR
TCPIP0::192.168.1.10::hislip0::INSTR
TCPIP0::192.168.1.10::5025::SOCKET
```

Raw Socket 通常使用端口 5025，并以换行符结束命令。VXI-11 或 HiSLIP 一般比 Raw Socket
更容易正确处理二进制块结束符。

## 3. 频率与扫描

| 用途 | SCPI 指令 |
|---|---|
| 设置/查询起始频率 | `SENSe<ch>:FREQuency:STARt <Hz>` / `...?` |
| 设置/查询终止频率 | `SENSe<ch>:FREQuency:STOP <Hz>` / `...?` |
| 设置/查询中心频率 | `SENSe<ch>:FREQuency:CENTer <Hz>` / `...?` |
| 设置/查询跨度 | `SENSe<ch>:FREQuency:SPAN <Hz>` / `...?` |
| 设置/查询 CW 频率 | `SENSe<ch>:FREQuency:CW <Hz>` / `...?` |
| 设置/查询扫描点数 | `SENSe<ch>:SWEep:POINts <count>` / `...?` |
| 设置扫描类型 | `SENSe<ch>:SWEep:TYPE LINear|LOGarithmic|SEGMent|POWer|CW` |
| 查询扫描时间 | `SENSe<ch>:SWEep:TIME?` |
| 查询实际频率点 | `SENSe<ch>:FREQuency:DATA?` |

线性扫描示例：

```text
SENS1:FREQ:STAR 10E9
SENS1:FREQ:STOP 17E9
SENS1:SWE:TYPE LIN
SENS1:SWE:POIN 801
```

项目当前通过起止频率和点数生成线性频率轴。使用分段、对数或功率扫描时，应改用
`SENS1:FREQ:DATA?` 读取实际横轴，不能继续使用等间隔插值。

## 4. IF 带宽与平均

| 用途 | SCPI 指令 |
|---|---|
| 设置/查询 IF 带宽 | `SENSe<ch>:BWIDth:RESolution <Hz>` / `...?` |
| 开关自动 IFBW | `SENSe<ch>:BWIDth:RESolution:AUTO ON|OFF` |
| 开关平均 | `SENSe<ch>:AVERage:STATe ON|OFF` |
| 设置平均次数 | `SENSe<ch>:AVERage:COUNt <count>` |
| 清除平均结果 | `SENSe<ch>:AVERage:CLEar` |
| 设置平均模式 | `SENSe<ch>:AVERage:MODE POINt|SWEep` |

```text
SENS1:BAND:RES 1000
SENS1:AVER:STAT ON
SENS1:AVER:COUN 8
SENS1:AVER:CLE
```

启用扫描平均后，单次采集需要等待多次扫描完成，VISA 超时应按扫描时间和平均次数增加。

## 5. 源功率

| 用途 | SCPI 指令 |
|---|---|
| 设置通道默认功率 | `SOURce<ch>:POWer <dBm>` |
| 查询通道默认功率 | `SOURce<ch>:POWer?` |
| 设置指定端口功率 | `SOURce<ch>:POWer<port>:LEVel:IMMediate:AMPLitude <dBm>` |
| 查询指定端口功率 | `SOURce<ch>:POWer<port>:LEVel:IMMediate:AMPLitude?` |

```text
SOUR1:POW -10
```

项目当前采用 `SOUR:POW <dBm>`。当各端口需要不同功率时，应改用带 `<ch>` 和 `<port>` 的
完整命令。允许功率范围取决于频段、端口、衰减器和选件，设置后应查询 `SYST:ERR?`。

## 6. 创建和选择 S 参数测量

推荐给自动化测量使用固定、唯一的测量名称：

```text
CALC1:PAR:DEF:EXT 'CH1_SPARAM','S21'
CALC1:PAR:SEL 'CH1_SPARAM'
DISP:WIND1:TRAC1:FEED 'CH1_SPARAM'
```

| 用途 | SCPI 指令 |
|---|---|
| 创建扩展测量 | `CALCulate<ch>:PARameter:DEFine:EXT '<name>','<parameter>'` |
| 创建测量 | `CALCulate<ch>:PARameter:DEFine '<name>',<parameter>` |
| 选择测量 | `CALCulate<ch>:PARameter:SELect '<name>'` |
| 修改当前测量参数 | `CALCulate<ch>:PARameter:MODify <parameter>` |
| 查询测量目录 | `CALCulate<ch>:PARameter:CATalog?` |
| 删除指定测量 | `CALCulate<ch>:PARameter:DELete '<name>'` |
| 删除全部测量 | `CALCulate<ch>:PARameter:DELete:ALL` |
| 将测量送入显示迹线 | `DISPlay:WINDow<w>:TRACe<t>:FEED '<name>'` |

常用测量参数：`S11`、`S21`、`S12`、`S22`。四端口配置可使用 `S11` 至 `S44` 中实际
硬件支持的端口组合。

如果仪器当前不存在 `CH1_SPARAM`，先执行 `CALC:PAR:SEL` 会产生错误；应先查询目录，或在
创建失败时读取 `SYST:ERR?` 并尝试兼容命令。

## 7. 显示格式与迹线

| 用途 | SCPI 指令 |
|---|---|
| 对数幅度 | `CALCulate<ch>:FORMat MLOGarithmic` |
| 线性幅度 | `CALCulate<ch>:FORMat MLINear` |
| 相位 | `CALCulate<ch>:FORMat PHASe` |
| 实部/虚部 | `CALCulate<ch>:FORMat REAL` / `IMAGinary` |
| 驻波比 | `CALCulate<ch>:FORMat SWR` |
| 史密斯图 | `CALCulate<ch>:FORMat SMITht` |
| 极坐标 | `CALCulate<ch>:FORMat POLar` |
| 群时延 | `CALCulate<ch>:FORMat GDELay` |

显示格式只影响 `FDATA` 和前面板显示，不应影响 `SDATA` 的复数 S 参数读取。

## 8. 触发和单次采集

```text
INIT1:CONT OFF
TRIG:SOUR IMM
INIT1:IMM
*OPC?
```

| 用途 | SCPI 指令 |
|---|---|
| 开关连续扫描 | `INITiate<ch>:CONTinuous ON|OFF` |
| 立即触发一次 | `INITiate<ch>:IMMediate` |
| 设置触发源 | `TRIGger:SOURce IMMediate|MANual|EXTernal|BUS` |
| 等待扫描完成 | `*OPC?` |
| 中止扫描 | `ABORt` |

自动采集建议明确关闭连续扫描，避免读到前一次扫描或正在更新的数据。项目当前发送
`INIT:IMM` 后查询 `*OPC?`，但没有显式关闭连续扫描；现场验证时应确认仪器状态，必要时加入
`INIT1:CONT OFF`。

## 9. 复数与格式化数据读取

### 9.1 二进制复数 SDATA（推荐）

```text
FORM:DATA REAL,64
FORM:BORD SWAP
CALC1:DATA? SDATA
```

返回顺序为：

```text
real[0], imag[0], real[1], imag[1], ...
```

`REAL,64 + SWAP` 对应 PC 常用的小端 64 位浮点解析。也可使用 `REAL,32` 降低传输量，但必须
同步修改 VISA 解析类型。

### 9.2 ASCII 复数数据

```text
FORM:DATA ASC,0
CALC1:DATA? SDATA
```

ASCII 适合诊断，速度和数据体积不如二进制。

### 9.3 格式化数据

```text
CALC1:FORM MLOG
CALC1:DATA? FDATA
```

`FDATA` 返回当前显示格式的数据。需要同时得到幅度与相位时，优先读取一次 `SDATA`，再由程序
计算：

```text
magnitude_db = 20 * log10(abs(s))
phase_deg = angle(s) * 180 / pi
```

## 10. 标记与搜索

| 用途 | SCPI 指令 |
|---|---|
| 开关标记 | `CALCulate<ch>:MARKer<m>:STATe ON|OFF` |
| 设置标记频率 | `CALCulate<ch>:MARKer<m>:X <Hz>` |
| 查询标记频率 | `CALCulate<ch>:MARKer<m>:X?` |
| 查询标记值 | `CALCulate<ch>:MARKer<m>:Y?` |
| 搜索最大值 | `CALCulate<ch>:MARKer<m>:SEARch:MAXimum` |
| 搜索最小值 | `CALCulate<ch>:MARKer<m>:SEARch:MINimum` |

标记命令适合人工诊断或快速查询峰值；批量扫描结果分析应在软件中对完整 `SDATA` 处理。

## 11. 校准与误差修正状态

| 用途 | SCPI 指令 |
|---|---|
| 查询/设置误差修正 | `SENSe<ch>:CORRection:STATe?` / `... ON|OFF` |

校准集查询、校准采集、ECal 和校准套件命令与仪器固件及选件关系较强，应从实际固件版本的
E5080B Help 中核对 `SENSe:CORRection:CSET` 和 `SENSe:CORRection:COLLect` 命令树。
自动化测试程序不应在连接时执行
`*RST`、`SYST:PRES` 或关闭误差修正，否则可能破坏现场已加载的校准状态。

## 12. 文件和截图

下列命令形式需按 E5080B 固件帮助确认文件系统路径和参数：

| 用途 | 常见命令族 |
|---|---|
| 查询文件目录 | `MMEMory:CATalog? '<path>'` |
| 删除文件 | `MMEMory:DELete '<file>'` |
| 保存仪器状态 | `MMEMory:STORe:STATe '<file>'` |
| 调用仪器状态 | `MMEMory:LOAD:STATe '<file>'` |
| 保存 Touchstone | `MMEMory:STORe:TRACe:SNP ...` |
| 保存屏幕图像 | `HCOPy:FILE '<file>'` / `MMEMory:DATA? '<file>'` |

由于路径格式和 SNP 参数在不同固件间可能变化，本项目若增加文件下载功能，应先在实际 E5080B
上通过 `SYST:ERR?` 验证，不能只依据 PNA-X 示例实现。

## 13. 本项目推荐采集流程

```text
*IDN?
*OPT?
*CLS
SENS1:FREQ:STAR 10E9
SENS1:FREQ:STOP 17E9
SENS1:SWE:TYPE LIN
SENS1:SWE:POIN 801
SENS1:BAND:RES 1000
SOUR1:POW -10
CALC1:PAR:DEF:EXT 'CH1_SPARAM','S21'
CALC1:PAR:SEL 'CH1_SPARAM'
INIT1:CONT OFF
TRIG:SOUR IMM
INIT1:IMM
*OPC?
FORM:DATA REAL,64
FORM:BORD SWAP
CALC1:DATA? SDATA
SYST:ERR?
```

采集结果至少检查：

- `*IDN?` 型号为 `E5080B`。
- `SYST:ERR?` 返回零错误。
- `SDATA` 数值数量为偶数。
- 复数点数等于 `SENS1:SWE:POIN?`。
- 非线性扫描时，频率轴来自 `SENS1:FREQ:DATA?`。

## 14. 与 N5245B 共用和分离的部分

可以共用：

- VISA 会话、`*IDN?` 和错误队列处理。
- 频率、点数、IFBW、通道功率等基础配置。
- `CALC:PAR:DEF/SEL` 测量管理。
- `INIT:IMM + *OPC?` 单次触发。
- `REAL,64 + SWAP + CALC:DATA? SDATA` 复数读取。

应按型号或能力查询分离：

- PNA-X 双源、频偏、互调、噪声和脉冲等高级功能。
- 最大频率、最小/最大功率、端口数和最大扫描点数。
- 校准向导、校准集管理和高级接收机访问。
- 仪器文件路径、Touchstone 保存参数及截图命令。

## 15. 来源与交叉验证

- Keysight E5080B Help：<https://helpfiles.keysight.com/csg/e5080b/>
- Keysight E5080B 产品资料页：<https://www.keysight.com/find/E5080B>
- 本项目实际控制器：[scpi.py](../src/quiet_zone_tester/hardware/vna/scpi.py)
- scikit-rf Keysight PNA 驱动：<https://github.com/scikit-rf/scikit-rf/blob/master/skrf/vi/vna/keysight/pna.py>
- QCoDeS Keysight N52xx 驱动：<https://github.com/QCoDeS/Qcodes/blob/main/src/qcodes/instrument_drivers/Keysight/N52xx.py>
- PyMeasure Keysight PNA 驱动：<https://github.com/pymeasure/pymeasure/blob/master/pymeasure/instruments/keysight/keysightPNA.py>

后三个开源驱动用于交叉验证 Keysight VNA 的通用扫频、触发、格式和数据读取模式，并不表示
这些项目明确支持 E5080B 的全部功能。E5080B 高级功能和参数范围必须以对应固件版本的官方
Help 为最终依据。Keysight 帮助站目前对自动目录访问返回 403，但浏览器通常可以直接打开。
