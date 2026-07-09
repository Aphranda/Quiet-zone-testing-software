# 扫描管理设计

Status: Active
Domain: SCAN
Canonical: `docs/SCAN_MANAGEMENT_DESIGN.md`
Related: `docs/architecture_migration_plan.md`, `docs/DATA_MANAGEMENT_DESIGN.md`
Last updated: 2026-07-10

本文档定义扫描配置、路径规划、扫描状态机、步进/匀速扫描运行和扫描事实模型边界。

## 职责

- 管理扫描配置 dataclass。
- 规划二维蛇形扫描路径。
- 管理扫描状态转换。
- 编排步进扫描和匀速扫描主循环。
- 通过回调调用运动、链路、采样和数据保存服务。

## 当前实现

- 配置与事实模型：`domains/scan_management/models.py`
- 路径规划：`domains/scan_management/scan_planner.py`
- 状态机：`domains/scan_management/scan_state_machine.py`
- 扫描运行几何：`domains/scan_management/scan_runtime_geometry.py`
- 扫描运行服务：`domains/scan_management/scan_runtime_service.py`
- 设置 UI ViewModel：`presentation/modules/scan_setup/scan_setup_view_model.py`

## 边界

扫描管理不直接访问硬件 controller。

扫描运行服务只通过注入的能力调用：

- 运动：`MotionService`
- 采样：`AcquisitionService`
- 链路：`LinkService`
- 保存：`TraceStorage`

## 关键规则

- `ScanPlanner` 是扫描路径唯一来源。
- `ScanStateMachine` 管状态合法转换，不保存大体量 trace。
- `ScanSession` 保存事实，状态机保存流程阶段。
- 停止请求应返回已完成的部分结果。

## 后续迁移

- 将 `InstrumentService.run_scan()` 剩余锁和准备逻辑迁入 application 或扫描运行 ViewModel。
- 建立扫描点 Qt model，用于动画和结果索引展示。

