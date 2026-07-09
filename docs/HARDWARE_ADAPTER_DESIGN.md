# 硬件适配层设计

Status: Active
Domain: HARDWARE
Canonical: `docs/HARDWARE_ADAPTER_DESIGN.md`
Related: `docs/INSTRUMENT_MANAGEMENT_DESIGN.md`
Last updated: 2026-07-10

本文档定义硬件接口、Mock 实现、真实仪器实现和旧导入兼容策略。

## 职责

- 通过 `hardware/interfaces.py` 暴露统一接口。
- 提供 Mock VNA、Mock 扫描架、Mock 开关箱。
- 提供真实 VNA、扫描架、开关箱协议实现。
- 提供 VISA/Modbus 等 transport helper。

## 当前结构

```text
hardware/
  interfaces.py
  mock/
  vna/
  positioner/
  switch_box/
  transport/
```

旧 `drivers/` 和 `instruments/` 只保留兼容 re-export。

## 边界

硬件层不关心 UI、扫描状态、文件输出或业务策略。

硬件层只实现“设备能做什么”，业务流程由 domains/application 编排。

## 关键规则

- 新代码应从 `quiet_zone_tester.hardware` 导入接口和 controller。
- 旧路径暂时保留，避免外部脚本或历史代码立即失效。
- Mock 和真实实现都必须满足 `hardware/interfaces.py` 中的协议。

## 后续迁移

- 后续可移除旧路径或标记为 deprecated。
- 为真实硬件实现补充设备级集成测试说明和手动验证清单。

