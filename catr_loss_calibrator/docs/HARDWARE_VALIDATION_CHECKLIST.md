# CATR 真实硬件验证清单

Status: Draft  
Domain: CATR_LOSS_CALIBRATOR  
Canonical: `catr_loss_calibrator/docs/HARDWARE_VALIDATION_CHECKLIST.md`  
Related: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`

## 验证范围

- 真实 VNA 连接与断开
- 真实 LCD74000F 链路箱连接与断开
- 资源独占与互锁
- 链路切换命令下发
- 采样触发与 S21 读取
- raw / final / metadata 保存
- 故障恢复与清理

## 验证步骤

1. 连接 VNA，确认 `*IDN?` 返回有效信息。
2. 连接链路箱，确认可下发 `CONFigure:LINK ...`。
3. 申请资源锁，确认静区测试软件不可同时占用。
4. 执行一次链路切换，确认端口状态与预期一致。
5. 执行一次扫频，读取 `S21`。
6. 保存 raw trace、metadata 和最终路损文件。
7. 人工中止一次流程，确认连接和锁释放。
8. 触发一次异常，确认半连状态回滚。

## 记录项

- 日期
- 操作人
- VNA 型号 / 序列号 / 固件
- 链路箱型号 / 固件
- 连接方式
- 测试项 ID
- 异常与恢复结果
