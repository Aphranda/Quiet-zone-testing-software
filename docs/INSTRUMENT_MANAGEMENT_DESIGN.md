# 仪表管理设计

Status: Active
Domain: INSTRUMENT
Canonical: `docs/INSTRUMENT_MANAGEMENT_DESIGN.md`
Related: `docs/architecture_migration_plan.md`, `docs/APP_DESIGN.md`
Last updated: 2026-07-10

本文档定义 VNA、扫描架、开关箱的连接生命周期、controller 创建和连接配置边界。

## 职责

- 管理连接配置 dataclass。
- 根据虚拟/真实配置创建 controller。
- 执行连接、断开、批量断开和失败清理。
- 暴露仪表连接状态。

## 当前实现

- 配置模型：`domains/instrument_management/models.py`
- controller 创建：`InstrumentControllerFactory`
- 连接生命周期：`InstrumentConnectionService`
- UI 连接状态派生：`presentation/modules/connection/connection_view_model.py`
- facade 入口：`services/instrument_service.py`
- 硬件接口和实现：`hardware/`

## 边界

仪表管理负责“设备是否存在、如何创建、如何连接”，不负责：

- S 参数到开关箱命令映射。
- 扫描路径规划。
- VNA sweep 配置和采样。
- 数据保存。

## 关键规则

- Mock/真实后端选择只由连接配置决定。
- 真实模式拒绝 `MOCK` 资源。
- 单设备连接失败时清理该设备 controller。
- `connect_all()` 任一设备失败时清理部分连接。
- 连接面板整体状态文本和按钮启用规则由 `ConnectionViewModel.panel_state()` 派生。
- 旧 `drivers/` 和 `instruments/` 导入路径只作为兼容 re-export。

## 后续迁移

- 可新增 `InstrumentManager` 聚合连接状态和连接快照。
- 可进一步将连接状态快照迁入 `InstrumentManager` 或 Qt model，供更多 UI 复用。
