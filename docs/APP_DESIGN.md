# APP 管理设计

Status: Active
Domain: APP
Canonical: `docs/APP_DESIGN.md`
Related: `docs/architecture_migration_plan.md`, `docs/ARCH_MIGRATION_TODO.md`
Last updated: 2026-07-10

本文档定义应用入口、QApplication 生命周期、主窗口装配、后台任务调度和全局状态管理边界。

## 职责

- `run.py` 只作为开发期启动脚本。
- `quiet_zone_tester.__main__` 支持 `python -m quiet_zone_tester`。
- `quiet_zone_tester.main:main` 是统一程序入口。
- `quiet_zone_tester.app` 负责 QApplication 创建、全局样式和主窗口启动。
- `application/` 后续承接应用上下文、全局状态机、任务调度和全局错误处理。

## 当前状态

- 入口已收口到 `quiet_zone_tester.main:main`。
- `app.py` 仍负责 QApplication 和主窗口启动。
- `ui/main_window.py` 仍是主窗口装配和顶层路由位置。
- `ui/async_task.py` 暂时保留，后续可迁到 `application/task_runner.py`。

## 目标边界

```text
main.py
  -> app.run_app()
  -> application app context
  -> presentation shell
```

APP 管理不应直接实现业务流程，也不应直接调用硬件 controller。

## 后续迁移

- 新增 `application/app_context.py`，集中创建 service、ViewModel 和主窗口依赖。
- 新增 `application/task_runner.py`，替代当前 UI 侧异步任务 helper。
- 将 `MainWindow` 中的全局忙碌状态、扫描任务状态和错误路由逐步迁出。

