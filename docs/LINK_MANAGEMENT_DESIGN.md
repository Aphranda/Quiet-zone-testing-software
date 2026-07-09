# 链路管理设计

Status: Active
Domain: LINK
Canonical: `docs/LINK_MANAGEMENT_DESIGN.md`
Related: `docs/architecture_migration_plan.md`, `docs/INSTRUMENT_MANAGEMENT_DESIGN.md`
Last updated: 2026-07-10

本文档定义 S 参数链路路由、开关箱 profile 和链路控制 UI/ViewModel 的边界。

## 职责

- 规范化 `S11/S21/S12/S22`。
- 将 S 参数解析为开关箱命令。
- 支持 LCD74000F、TC500 和 Mock profile。
- 执行开关箱链路切换和原始命令发送。

## 当前实现

- 路由规则：`domains/link_management/link_router.py`
- profile：`domains/link_management/switch_box_profiles.py`
- 执行服务：`domains/link_management/link_service.py`
- UI 状态和链路图派生状态：`presentation/modules/link_control/link_control_view_model.py`
- Widget 兼容入口：`ui/widgets/switch_box_control_panel.py`

## 边界

链路管理不负责底层串口/TCP 通信；真实通信在 `hardware/switch_box/` 中实现。

链路管理不负责 VNA 采样；采样由 `AcquisitionService` 管理。

## 关键规则

- Widget 不直接拼接业务命令。
- `LinkRouter` 可独立测试，不依赖真实开关箱。
- `LinkService` 只依赖开关箱 controller 协议。
- 链路图高亮 token 由 `LinkControlViewModel.diagram_state()` 派生，Widget 只负责绘制。

## 后续迁移

- 为当前链路状态建立结构化 model，供日志、UI 和扫描记录复用。
