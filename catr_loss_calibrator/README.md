# CATR Loss Calibrator

独立的 CATR 暗室路损自动校准软件。

本项目用于执行链路箱/VNA/SG/SA 相关路损校准，生成可追溯的带符号路损文件。它与当前静区测试软件解耦，不依赖 `quiet_zone_tester` 运行时。

## 当前阶段

当前为项目骨架阶段：

- 已建立独立 Python 包结构。
- 已定义校准项模型、硬件接口、路损公式和文件命名策略的基础骨架。
- 默认使用 mock 硬件，便于先开发流程和测试。

## 运行

```powershell
cd catr_loss_calibrator
python -m catr_loss_calibrator
```

## 设计文档

见：

```text
docs/CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md
docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.md
docs/CATR_CHAMBER_OPERATION_SUMMARY.md
docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN_TODO.md
```
