# 数据管理设计

Status: Active
Domain: DATA
Canonical: `docs/DATA_MANAGEMENT_DESIGN.md`
Related: `docs/architecture_migration_plan.md`, `docs/SCAN_MANAGEMENT_DESIGN.md`
Last updated: 2026-07-10

本文档定义扫描事实、trace 文件、metadata、trace index、文件命名和输出目录边界。

## 职责

- 创建扫描输出目录。
- 生成 trace 文件名。
- 保存 trace CSV。
- 写入扫描 metadata。
- 维护 trace index。
- 为后续报告导出提供事实基础。

## 当前实现

- 文件名策略：`domains/data_management/filename_policy.py`
- trace 保存：`domains/data_management/trace_storage.py`
- 扫描事实写入入口：`domains/data_management/scan_repository.py`
- 报告导出：`domains/data_management/report_exporter.py`
- 扫描事实模型：`domains/scan_management/models.py`
- RF trace 模型：`models/rf_data.py`

## 边界

数据管理不控制硬件，不决定扫描状态跳转，不更新 UI。

扫描运行只在采样成功后调用数据管理保存结果。

## 关键规则

- 文件名清洗规则集中在 `FilenamePolicy`。
- 输出目录和 trace index 由 `TraceStorage` 管理。
- `ScanRepository` 统一创建 `ScanSession`、保存 trace record、追加事件和 finalize。
- `ReportExporter` 基于 `ScanSession` 导出 Markdown 报告。
- metadata 只保存 JSON 安全字段或安全字符串表示。
- 旧 CSV 和 trace index 输出格式必须保持兼容。

## 后续迁移

- 后续可为报告导出增加图表、统计指标和模板配置。
