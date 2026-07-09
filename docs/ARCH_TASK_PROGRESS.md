# 架构迁移进度记录

Status: Active
Domain: ARCH
Canonical: `docs/ARCH_TASK_PROGRESS.md`
Related: `docs/architecture_migration_plan.md`, `docs/ARCH_MIGRATION_TODO.md`
Last updated: 2026-07-09

本文档记录架构迁移过程中已经发生的重要实施、验证、风险和决策。待办事项仍维护在 `docs/ARCH_MIGRATION_TODO.md`。

### ARCH-TASK-20260709-001 - P0 迁移骨架和扫描基础模型

- 目标：完成入口职责确认、新目录骨架、扫描事实模型、扫描状态机和基础测试闭环。
- 完成：保留旧 `ui/`、`services/`、`drivers/`、`instruments/` 不动，新增 `application/`、`domains/`、`hardware/`、`presentation/`、`shared/` 骨架；新增 `ScanSession`、`TraceRecord`、`ScanEvent`、`ScanStateMachine`。
- 验证：`py_compile` 通过；`python -m unittest discover -s tests` 通过 5 个测试；主窗口 offscreen 初始化输出 `ok`。
- 风险：pytest 暂未安装到当前 Conda 环境，安装请求被审批层拦截；测试暂采用标准库 `unittest`，pytest 后续可直接收集。
- 后续：进入 P1，优先抽出 `FilenamePolicy` 和 `TraceStorage`，继续保持旧扫描流程输出不回归。
- 涉及文件：`src/quiet_zone_tester/domains/scan_management/`、`tests/`、`docs/ARCH_MIGRATION_TODO.md`。
