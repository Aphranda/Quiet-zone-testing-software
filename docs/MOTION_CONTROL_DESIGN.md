# 运动控制设计

Status: Active
Domain: MOTION
Canonical: `docs/MOTION_CONTROL_DESIGN.md`
Related: `docs/architecture_migration_plan.md`, `docs/SCAN_MANAGEMENT_DESIGN.md`
Last updated: 2026-07-10

本文档定义扫描架手动运动、轴级运动、运行时配置和位置显示边界。

## 职责

- 查询当前位置。
- 执行点动、停止、绝对运动、相对运动。
- 更新扫描架运行时配置。
- 处理 X/Y 语义到硬件轴号的映射。
- 为扫描运行提供按轴定位和连续 jog 到目标能力。

## 当前实现

- domain service：`domains/motion_control/motion_service.py`
- UI ViewModel：`presentation/modules/motion_control/motion_control_view_model.py`
- 运动期间位置轮询：`presentation/modules/motion_control/position_tracker.py`
- Widget 兼容入口：`ui/widgets/positioner_control_panel.py`
- 硬件实现：`hardware/positioner/` 和 `hardware/mock/positioner.py`

## 边界

运动控制不负责扫描路径规划、VNA 采样、链路切换或数据保存。

扫描运行可以调用 `MotionService`，但运动服务不决定扫描流程状态。

## 关键规则

- 手动运动命令保持旧 dict signal 兼容。
- 运行时配置更新由 `MotionService.update_runtime_config()` 统一处理。
- 运动期间位置轮询由 `PositionTracker` 管理定时器和任务互斥。
- 扫描停止时优先调用安全停止和取消运动能力。

## 后续迁移

- 为运动状态建立轻量状态机：Idle、Moving、Jogging、Stopping、Fault。
