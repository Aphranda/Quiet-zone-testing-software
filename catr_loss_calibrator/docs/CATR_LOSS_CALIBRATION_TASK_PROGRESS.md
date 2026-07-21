# CATR 路损校准软件任务进度记录

Status: Active  
Domain: CATR_LOSS_CALIBRATOR  
Canonical: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`  
Related: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`, `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_SOFTWARE_DESIGN.md`  
Last updated: 2026-07-20

本文档记录 `catr_loss_calibrator` 的正式开发任务进度。每完成一个正式任务后，在“任务记录”章节顶部追加记录，说明任务目标、完成内容、验证结果、剩余工作和下一步计划。

## 记录规则

- 每个正式任务使用独立编号：`CATR-CAL-TASK-YYYYMMDD-NNN`。
- 只记录已经进入文档、代码或测试的正式任务，不记录临时讨论。
- 如果任务只完成阶段性目标，状态写为 `进行中`，不能写成 `完成`。
- 如果没有执行测试，需要在验证结果中明确写出“未执行测试”或原因。
- 涉及真实硬件但未接入设备时，应明确写出“仅完成 Mock/导入验证，未做真实硬件验证”。
- 最新记录追加在最前面。

## 状态定义

| 状态 | 含义 |
|---|---|
| `完成` | 当前任务目标已经达成，并完成必要验证。 |
| `进行中` | 已完成阶段性工作，但任务闭环还未完成。 |
| `阻塞` | 当前无法继续，需要外部条件、硬件、资料或决策。 |
| `暂停` | 暂时不推进，但不是技术阻塞。 |

## 记录模板

```markdown
### CATR-CAL-TASK-YYYYMMDD-NNN - 任务标题

- 状态：进行中 / 完成 / 阻塞 / 暂停
- 日期：YYYY-MM-DD
- 任务目标：
  - ...
- 完成内容：
  - ...
- 验证结果：
  - ...
- 还需完成：
  - ...
- 关联文件：
  - `path/to/file`
- 下一步：
  - ...
```

## 任务记录

### CATR-CAL-TASK-20260720-001 - 续测发布闸门与测量条件一致性修复

- 状态：进行中
- 日期：2026-07-20
- 任务目标：
  - 将独立评审发现的 latest 发布、skip 完成判定、历史导入重测条件一致性、喇叭增益和插值边界风险纳入 TODO。
  - 先修复会污染 latest 或混用不同测量条件 raw 的高风险路径。
- 完成内容：
  - `MockCalibrationRunner` 增加 `publishable`、`publish_blockers`、`skipped_substep_ids` 和 `measurement_settings`。
  - `skip` 不再计入 `completed_substep_ids`；存在 skip、缺 raw 或缺 final 时不写 latest。
  - 单步重测 session 仍写入 `session_manifest.json` 供识别和后续合成，但不发布 latest。
  - 历史导入生成续测结果时检查 config hash、频段/馈源/喇叭、起止频、点数、功率、IFBW、S 参数和 raw 频轴；异常写入 warning，不阻断测试流程。
  - 标准喇叭增益缺失时继续测试并标记 `horn_gain_status=missing_default_zero`；喇叭增益导入和内部重采样异常进入 warning/追溯信息。
  - 每步 metadata、session manifest、历史 summary 和结果详情文本都带出 measurement/resume warning，便于现场识别异常但不中断测试。
  - 将生产执行器名称拆为 `CalibrationRunner`，presentation 层改用正式执行器导入；`MockCalibrationRunner` 保留为兼容旧测试/旧集成的别名。
- 验证结果：
  - `d:/Microsoft/uv-venvs/catr-loss-calibrator/Scripts/python.exe -m pytest`：129 passed。
  - `d:/Microsoft/uv-venvs/catr-loss-calibrator/Scripts/python.exe -m py_compile src\catr_loss_calibrator\calibration\__init__.py src\catr_loss_calibrator\calibration\calibration_runner.py src\catr_loss_calibrator\calibration\mock_runner.py src\catr_loss_calibrator\presentation\main.py src\catr_loss_calibrator\presentation\viewmodels.py`：通过。
- 还需完成：
  - 将 warning 从结果详情文本进一步升级为结构化 UI 列/图标。
  - 喇叭增益曲线 hash 在报告导出中进一步展开。
  - SG/SA 是否纳入真实执行闭环仍需结合现场校准方案确认。
  - UI 对 `publish_blockers` 和测量条件不一致的可读提示。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
- 下一步：
  - 跑通相关测试并补齐失败用例。

### CATR-CAL-TASK-20260719-050 - 历史导入续测与曲线质量方案登记

- 状态：进行中
- 日期：2026-07-19
- 任务目标：
  - 明确“导入测了一半的历史校准项目后，点击细分步骤独立补测/重测”的产品逻辑。
  - 将 `skip` 拆分为“沿用历史数据”和“标记不测”，避免部分数据被误判为正式成功。
  - 将曲线是否存在、曲线是否正常纳入是否建议重测的判断。
- 完成内容：
  - 新增 `CATR_LOSS_CALIBRATION_RESUME_PLAN.md`，定义历史导入、细分步骤状态、session 完成状态、导入校验、按钮语义和实施顺序。
  - 细分步骤状态增加 `NO_CURVE`、`SUSPECT_CURVE` 等曲线质量相关状态。
  - 曲线质量判断增加 `OK`、`NO_CURVE`、`BROKEN`、`SUSPECT`、`STALE`，用于给出“可沿用 / 建议重测 / 必须重测”。
  - 明确 `导入历史数据` 按钮放在校准执行页“校准批次”输入栏后侧，导入后刷新细分步骤状态和数据展示页签。
  - 开发 TODO 新增 `P5-16` 至 `P5-22`。
  - 文件管理 TODO 新增 `FM-18` 至 `FM-24`。
  - UI TODO 新增 `UI-92` 至 `UI-98`，其中 `UI-98` 明确细分步骤区域改为 `链路说明 / 数据展示` 页签。
  - 文档索引增加续测方案入口。
  - 校准执行页细分步骤列表右侧详情区域已改为 `链路说明 / 数据展示` 页签；保存确认时默认显示数据展示页，也可以手动切回链路说明。
  - 校准批次行新增 `导入历史数据` 按钮，可导入 workspace/session/latest/旧版目录摘要。
  - 导入历史数据后，细分步骤列表能按 raw 文件名标记历史数据状态，右侧 `数据展示` 页能预览对应历史 raw CSV 曲线。
  - 曲线质量改为人工判定：软件只检查 CSV 是否可读、是否存在 dB 曲线列、点数和明显读取异常；操作员在数据展示页选择 `正常可沿用` 或 `异常需重测`。
  - 数据展示页新增 `沿用历史` 和 `重测当前` 按钮；`重测当前` 支持只执行当前细分步骤并生成新的 session raw/metadata/loss 文件。
  - 人工判定结果写入当前 workspace 的 `resume_decisions/*.json`，重新导入同一历史 session 时可恢复。
  - 单步重测后的新 raw 会合并到当前历史索引并优先显示，不会丢失其他历史步骤。
  - `生成/更新结果` 会基于人工判定可沿用的历史 raw 和本次重测 raw 复算 final/loss；完整时写 `RESUMED_DONE` 并更新 latest，不完整时写 `PARTIAL` 且不更新 latest。
  - 复算 session manifest 写入 `resume_source`、`substep_status`、`reused_files`、`new_files`、`invalid_files`，便于追溯历史沿用和本次重测来源。
- 验证结果：
  - `D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_presentation_gui_smoke.py` 通过。
  - `D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_resume.py` 通过。
  - `D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_presentation_viewmodels.py` 通过。
  - `D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests` 通过，121 passed。
- 还需完成：
  - 按 TODO 实现 config/hash 校验、复算输入/输出 hash 记录。
  - 将数据展示页继续扩展为“历史来源明细 / 标记不测”。
- 关联文件：
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_RESUME_PLAN.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
  - `catr_loss_calibrator/docs/README.md`
- 下一步：
  - 优先实现 `P5-16/FM-19/UI-93/UI-98`，先让导入历史数据后每个细分步骤能显示状态和曲线。

### CATR-CAL-TASK-20260719-049 - exe 运行时路径与用户资源目录策略

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 完成 `P5-13/FM-17`，让源码、wheel 和 exe 运行时都能区分内置资源、用户配置目录、用户资源目录和校准输出目录。
  - 默认 JSON/CSV 作为只读内置资源随包发布，首次使用时复制到用户可写目录。
  - 新运行默认不再依赖当前工作目录下的 `catr_loss_calibrator_output`。
- 完成内容：
  - 扩展 `runtime_resources.py`：新增 `RuntimePaths`、PyInstaller 运行态识别、用户配置目录、用户资源目录、默认输出目录和初始化复制逻辑。
  - 默认用户配置路径为 `%APPDATA%/CATRLossCalibrator/calibration/configs/catr_chamber_loss_calibration.json`；默认用户 CSV 路径为 `%APPDATA%/CATRLossCalibrator/resources/*.csv`。
  - 默认校准输出路径改为用户文档目录下 `CATR Loss Calibrator/Calibrations`；可用 `CATR_LOSS_CALIBRATOR_OUTPUT` 覆盖。
  - `CalibrationViewModel.load_default_catalog()` 现在会初始化用户配置/资源副本，并优先加载用户配置副本。
  - CLI/interactive mock 输出改到运行时默认输出目录下的 `cli` / `interactive` 子目录。
  - 测试环境通过 `CATR_LOSS_CALIBRATOR_HOME` 和 `CATR_LOSS_CALIBRATOR_OUTPUT` 指到临时目录，避免污染真实用户目录。
- 验证结果：
  - 通过针对性测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_runtime_resources.py catr_loss_calibrator\tests\test_project_boundaries.py catr_loss_calibrator\tests\test_calibration_catalog.py catr_loss_calibrator\tests\test_presentation_gui_smoke.py`，共 20 项。
  - 通过失败项回归测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_mock_runner.py::test_presentation_cli_runs_demo_flow catr_loss_calibrator\tests\test_presentation_viewmodels.py`，共 21 项。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 114 项。
  - 本轮未做真实硬件验证。
- 还需完成：
  - 后续真正打包 exe 时，需要在 PyInstaller spec 或等价打包脚本里确认 `pyproject.toml` package-data 被正确收集。
  - 真实硬件验证仍放在最后阶段。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/runtime_resources.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/workspace.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/conftest.py`
  - `catr_loss_calibrator/tests/test_runtime_resources.py`
  - `catr_loss_calibrator/tests/test_presentation_gui_smoke.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
- 下一步：
  - 继续评估 `P5-04/P5-05/P5-06` 或 UI 拆分。

### CATR-CAL-TASK-20260719-048 - 重测数据一致性与打包资源清单修复

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 将评审中的非实机、非异常审计项补入 TODO，并优先修复会影响现场使用的数据一致性与资源打包问题。
  - 保存确认阶段点击“上一步”重测后，新 raw 必须让依赖它的 final/loss 输出失效，避免继续使用旧曲线。
  - 默认 JSON、默认喇叭增益 CSV、样式、LOGO 和图标进入包资源清单，降低 wheel/exe 场景找不到资源的风险。
- 完成内容：
  - 完成 `P5-14`：`MockCalibrationRunner` 在重写已存在 raw 记录时清空已保存 final/loss 缓存，后续保存会用新 raw 重新计算。
  - 完成 `P5-15`：默认喇叭增益 CSV 复制到包内 `src/catr_loss_calibrator/resources`，默认链路配置改为引用包内 CSV。
  - 新增 `runtime_resources.resolve_data_file()`，相对路径优先按 JSON 所在目录解析，找不到时回退到包内默认 CSV，支持 workspace 配置快照预览/复用。
  - `pyproject.toml` 补齐 package-data：默认配置、默认 CSV、QSS/CSS、SVG、PNG 和 icons。
  - `.gitignore` 为包内默认 CSV 增加例外，避免默认喇叭增益 CSV 被运行输出规则误忽略。
  - `UI-91` 已加入 UI TODO，仅登记主界面拆分，不在本轮大改。
- 验证结果：
  - 通过针对性测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_mock_runner.py catr_loss_calibrator\tests\test_calibration_catalog.py catr_loss_calibrator\tests\test_project_boundaries.py`，共 40 项。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 112 项。
  - 本轮未做真实硬件验证；按当前安排，真实硬件验证保持在后续最后阶段。
- 还需完成：
  - `P5-13/FM-17` 仍需实现 exe 打包后的用户配置目录、用户资源目录、输出目录和首次启动复制策略。
  - 异常/拒收数据审计历史暂不处理。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/runtime_resources.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/configs/catr_chamber_loss_calibration.json`
  - `catr_loss_calibrator/pyproject.toml`
  - `.gitignore`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
  - `catr_loss_calibrator/tests/test_calibration_catalog.py`
  - `catr_loss_calibrator/tests/test_project_boundaries.py`
- 下一步：
  - 继续推进 `P5-13/FM-17` 或其他非实机 TODO。

### CATR-CAL-TASK-20260719-047 - 保存确认阶段显示当前保存曲线

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 保存数据确认时直接显示当前小步骤刚保存的曲线。
  - 操作员发现曲线异常时，可直接点击“上一步”重测当前小步骤，避免错误数据继续流入后续步骤。
  - 接线/开始确认阶段仍显示原来的接线路径、命令说明和步骤详情。
- 完成内容：
  - `StepViewData` 增加 `saved_files` 字段。
  - `CalibrationRunWorker` 在保存确认 prompt 中带出当前小步骤生成的 final/raw CSV 文件。
  - 步骤执行右侧详情区域改为内部切换：开始确认显示说明页，保存确认显示曲线页。
  - 曲线页复用结果页 CSV 解析逻辑，支持 dB 列自动识别和自适应坐标。
  - 新增测试覆盖保存确认 prompt 能暴露当前保存 CSV。
  - 完成 `UI-90`。
- 验证结果：
  - 通过针对性测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_presentation_viewmodels.py catr_loss_calibrator\tests\test_presentation_gui_smoke.py`，共 21 项。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 108 项。
- 还需完成：
  - 后续可考虑在保存确认曲线页增加“打开文件”或“标记异常”动作。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 继续处理剩余 UI TODO，或推进 exe 打包路径策略。

### CATR-CAL-TASK-20260719-046 - workspace 自包含配置与独立历史预览

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 解决单独加载 workspace 时结果页没有数据的问题。
  - 新生成的 workspace 内保存链路配置快照，便于之后自动恢复配置。
  - 结果页在没有先导入链路配置时，也能独立预览历史 session 文件和曲线。
- 完成内容：
  - `storage/workspace.py` 增加 `workspace.json` 与 `config/link_config_snapshot.json` 写入能力。
  - 校准开始时写入当前链路配置快照。
  - 结果页加载 workspace 时，若存在配置快照则自动导入。
  - 结果页导入 workspace 后支持扫描所有项目的所有 `session_manifest.json`，不再强制依赖当前项目代号和当前校准项。
  - 旧版目录查看在未加载链路配置时也可扫描全部 metadata。
  - 更新历史文件查找手册，说明 workspace 配置快照和独立预览行为。
- 验证结果：
  - 通过针对性测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_workspace_management.py catr_loss_calibrator\tests\test_presentation_gui_smoke.py`，共 10 项。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 107 项。
- 还需完成：
  - 旧 workspace 没有配置快照，只能靠 `session_manifest.json` 独立预览，不能自动恢复链路配置。
  - `P5-13/FM-17`：exe 打包后的运行时路径策略仍未实现。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/workspace.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/tests/test_workspace_management.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_HISTORY_PLAYBOOK.md`
- 下一步：
  - 继续做 exe 打包路径策略，或补一个旧 workspace 配置快照迁移工具。

### CATR-CAL-TASK-20260719-045 - 历史校准文件查找用户说明

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 补充现场用户可直接使用的文件管理说明。
  - 说明项目代号、校准阶段、批次/轮次的填写口径。
  - 说明结果页当前 session、最新成功、历史 session 和旧版目录的区别。
  - 说明软件关闭后重新打开如何导入 workspace 并查看历史数据。
- 完成内容：
  - 新增 `CATR_LOSS_CALIBRATION_HISTORY_PLAYBOOK.md`，覆盖新版 workspace 目录结构、历史 session 查找、latest 查看和旧版目录只读查看。
  - 更新 `README.md`，把历史文件查找手册加入 canonical 文档入口、软件设计文档列表和快速查找规则。
  - 完成 `FM-16`。
- 验证结果：
  - 文档任务，未执行 pytest。
  - 已检查文档索引和 TODO 引用。
- 还需完成：
  - `P5-13/FM-17`：exe 打包后的默认资源目录、用户配置目录、用户资源目录和校准输出目录策略仍未实现。
- 关联文件：
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_HISTORY_PLAYBOOK.md`
  - `catr_loss_calibrator/docs/README.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`
- 下一步：
  - 继续评估是否开始 `FM-17/P5-13`，或者优先处理非打包类 UI/配置 TODO。

### CATR-CAL-TASK-20260719-044 - 旧版输出目录只读兼容展示

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 支持查看旧版 `catr_loss_calibrator_output/raw`、`loss`、`metadata` 输出。
  - 明确旧版目录没有 config/workspace/session 绑定，结果页必须标记为只读和未绑定配置。
  - 新运行继续写入 workspace 新结构，不回写旧目录。
- 完成内容：
  - `storage/workspace.py` 增加 `load_legacy_output_summary()`，可从旧版输出根目录或 `metadata/raw/loss` 子目录识别旧版输出根。
  - 旧版扫描优先读取 metadata JSON 的 `calibration_item`、`input_files`、`output_files`，并按当前校准项过滤。
  - 结果页“结果视图”新增“旧版目录”。
  - 结果页路径框可填写旧版 `catr_loss_calibrator_output` 或其 `metadata` 子目录，点击“加载历史”后自动切换到旧版目录视图。
  - 旧版 summary 标记 `state=LEGACY_READONLY`、`workspace_id=UNBOUND_LEGACY`、`project_code=未绑定配置`。
  - “打开历史目录”在旧版目录视图下打开旧版输出根目录。
  - 完成 `FM-11`、`P5-12`，新增并完成 `UI-89`。
- 验证结果：
  - 通过针对性测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_workspace_management.py catr_loss_calibrator\tests\test_presentation_gui_smoke.py`，共 8 项。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 105 项。
- 还需完成：
  - `FM-16`：补用户文档，说明新 workspace、历史 session、旧版目录的区别和查找路径。
  - `P5-13/FM-17`：exe 打包后的默认资源目录、用户配置目录和输出目录策略仍未实现。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/workspace.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_workspace_management.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 优先补 `FM-16` 用户文档，降低现场人员找不到历史数据的概率。

### CATR-CAL-TASK-20260719-043 - 结果页历史 session 与 workspace 路径导入

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 解决软件关闭后重新打开，结果页无法查看之前校准数据的问题。
  - 结果页支持导入校准工作空间路径，并按当前项目代号、当前校准项列出历史 session。
  - 支持直接打开历史 session 目录，便于从资源管理器查看原始文件。
- 完成内容：
  - `storage/workspace.py` 增加 `load_session_summary_from_manifest()`、`list_session_summaries()`、`list_session_summaries_from_project_root()`。
  - 结果页“结果视图”增加“历史Session”，并增加历史 session 下拉框。
  - 结果页增加“校准工作空间”文本框，以及“浏览Workspace”“加载历史”“打开历史目录”按钮。
  - latest 和 history 查询优先使用导入的 workspace 路径；未填写时使用当前 run summary 或当前配置默认 workspace。
  - GUI smoke 覆盖从导入 workspace 路径加载历史 session，并显示文件表和 session 详情。
  - 文件管理 TODO 完成 `FM-10`，UI TODO 增加并完成 `UI-88`。
- 验证结果：
  - 通过针对性测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_workspace_management.py catr_loss_calibrator\tests\test_presentation_gui_smoke.py`，共 7 项。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 104 项。
- 使用说明：
  - 重新打开软件后，先加载同一个链路配置。
  - 在校准执行页确认项目代号与历史数据一致。
  - 到结果页填写或浏览选择 `catr_loss_calibrator_output/workspaces/{workspace_id}`。
  - 结果视图选择“历史Session”，再从历史下拉框选择要查看的 session。
- 还需完成：
  - `FM-11/P5-12`：旧版 `catr_loss_calibrator_output/metadata` 等非 workspace 目录仍未做只读兼容展示。
  - `FM-16`：用户文档还需补充如何填写项目代号、如何定位 workspace。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/workspace.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_workspace_management.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 做旧版输出目录只读兼容，或者补用户文档说明 workspace/history 的使用方式。

### CATR-CAL-TASK-20260719-042 - 主窗口初始尺寸自适应

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 明确当前主窗口初始尺寸来源。
  - 避免初始窗口因固定尺寸、右侧 LOG 和四列仪表卡片超出屏幕。
- 完成内容：
  - 将主窗口固定 `1180x780` 初始化改为 `_apply_initial_window_size()`。
  - 默认目标尺寸调整为 `1180x720`，并按当前屏幕可用区域裁剪：宽度不超过 `available.width() - 80`，高度不超过 `available.height() - 80`。
  - 仪表配置页设备卡片区域改为 `QScrollArea`，卡片过宽或过高时在页内滚动，不再强行撑大主窗口。
  - GUI smoke 增加主窗口尺寸不超过屏幕可用区域、仪表配置页存在滚动区的检查。
  - 更新 `UI-87` 状态。
- 验证结果：
  - 通过针对性测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_presentation_gui_smoke.py catr_loss_calibrator\tests\test_presentation_viewmodels.py`，共 20 项。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 103 项。
- 还需完成：
  - 如现场屏幕 DPI 或缩放比例导致控件仍显拥挤，可进一步把右侧 LOG 做成可折叠或默认更窄。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 继续处理结果历史 session 浏览或旧版输出目录只读兼容。

### CATR-CAL-TASK-20260719-041 - 仪表卡片三区布局与 SCPI 入口收敛

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 将网分、信号源、频谱仪卡片按竖向三区组织：资源连接、仪表配置、指令控制。
  - 去掉信号源/频谱仪常用 SCPI 快捷按钮，统一通过手动命令输入框发送 SCPI。
  - 保留结构化配置按钮，用于一键下发基础配置命令序列。
- 完成内容：
  - `DeviceCommandPanel` 将连接表单套入“资源连接”分组。
  - VNA/SG/SA 的配置表单统一标题为“仪表配置”。
  - 预设、手动命令、发送命令和当前响应统一套入“指令控制”分组。
  - 移除 SG/SA 快捷 SCPI 按钮及其专用 ViewModel action 接口，避免界面过重。
  - 保留 SG/SA 手动 SCPI 发送能力，测试覆盖通过 `send_device_command()` 发送并读取 Mock 状态。
  - GUI smoke 增加 VNA/SG/SA 三区标题检查。
  - 更新 `UI-84`、`UI-85`、`UI-86` 和 `P4-08` 的 TODO 描述。
- 验证结果：
  - 通过针对性测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_presentation_viewmodels.py catr_loss_calibrator\tests\test_presentation_gui_smoke.py`，共 20 项。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 103 项。
  - 仅完成 Mock/通用 SCPI 验证，未做 N5183B/N9020B 实机验证。
- 还需完成：
  - 实机阶段确认 N5183B/N9020B 的 SCPI 兼容性、错误返回和超时处理。
  - 如后续需要，可把设备卡片的三区高度做成更严格的响应式比例。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
- 下一步：
  - 继续非实机 TODO，优先处理旧版输出目录只读兼容展示或结果历史 session 浏览。

### CATR-CAL-TASK-20260719-040 - SG/SA 常用 SCPI 动作按钮与 Mock 查询状态

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 在信号源和频谱仪卡片上补齐常用 SCPI 动作入口，减少现场重复手输命令。
  - 所有快捷动作仍走统一 `send_command()` 链路，命令和响应进入 LOG。
  - Mock 模式下查询命令能返回可解释状态，而不是全部返回 `0`。
- 完成内容：
  - 信号源基础配置区新增输出开、输出关、查输出、查频率、查功率按钮。
  - 频谱仪基础配置区新增单次测量、峰值搜索、读频率、读幅度、查错误按钮。
  - `CalibrationViewModel` 新增 `run_signal_generator_action()` 和 `run_spectrum_analyzer_action()`，将动作名映射为 SCPI 命令序列。
  - `MockScpiInstrument` 增加常用 SCPI 状态跟踪，支持返回频率、功率、输出状态、频谱中心频率、marker 频率/幅度和错误状态。
  - GUI smoke 增加 SG/SA SCPI 快捷按钮启用检查。
  - 更新 `UI-84`、`UI-85`、`P4-08` 的 TODO 状态。
- 验证结果：
  - 通过针对性测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_presentation_viewmodels.py catr_loss_calibrator\tests\test_presentation_gui_smoke.py`，共 20 项。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 103 项。
  - 仅完成 Mock/通用 SCPI 验证，未做 N5183B/N9020B 实机验证。
- 还需完成：
  - 实机阶段需要确认 N5183B/N9020B 对这些 SCPI 的兼容性、返回格式和异常码。
  - 后续可增加“保存当前 SG/SA 配置为项目默认值”的配置持久化能力。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/hardware/mock.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
- 下一步：
  - 继续非实机 TODO，可优先处理旧版输出目录只读兼容或 SG/SA 配置持久化。

### CATR-CAL-TASK-20260719-039 - SG/SA 基础配置面板与 Mock 指令闭环

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 将信号源和频谱仪的基础配置做成类似网分配置的结构化面板。
  - 支持 Mock 模式下一键配置，并在 LOG 中记录实际下发的 SCPI 指令。
  - 暂不展开真实硬件兼容验证，保留到后续硬件阶段。
- 完成内容：
  - 信号源卡片新增“信号源基础配置”，包含频率、功率、输出开关和“配置”按钮。
  - 频谱仪卡片新增“频谱仪基础配置”，包含中心频率、Span、点数、RBW、VBW、参考电平、衰减、前置放大、连续测量和“配置”按钮。
  - `CalibrationViewModel` 新增 `configure_signal_generator()` 和 `configure_spectrum_analyzer()`，将结构化字段转换为通用 SCPI 命令序列。
  - 增加统一 `_send_device_command_sequence()`，让配置序列逐条进入 LOG，包含发送命令和返回响应。
  - GUI smoke 增加 SG/SA 配置组启用检查。
  - 更新 `UI-82`、`UI-83`、`P4-07` 的 TODO 状态。
- 验证结果：
  - 通过针对性测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests\test_presentation_viewmodels.py catr_loss_calibrator\tests\test_presentation_gui_smoke.py`，共 18 项。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 101 项。
  - 仅完成 Mock/通用 SCPI 指令验证，未做真实硬件验证。
- 还需完成：
  - 后续真实硬件阶段需要按 N5183B、N9020B 实机逐项确认 SCPI 兼容性、错误查询和安全输出默认值。
  - 可进一步将 SG/SA 型号特定策略下沉到 adapter/service，避免 ViewModel 长期承载硬件差异。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
- 下一步：
  - 继续推进非实机 TODO，优先处理旧版输出目录只读兼容展示或历史 session 列表浏览。

### CATR-CAL-TASK-20260719-038 - latest 成功 session 索引与结果页切换

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 成功完成校准后维护 `latest/{item_id}.json`，便于结果页快速找到当前项目的最新成功校准结果。
  - 失败或取消的 session 只保留 manifest，不覆盖 latest。
  - 结果页支持在“当前Session”和“最新成功”之间切换。
- 完成内容：
  - `storage/workspace.py` 增加 latest index 读写能力：`write_latest_index()`、`load_latest_summary()`、`load_latest_summary_from_index()`。
  - `session_manifest.json` 增加 `session_root` 字段，latest index 内嵌 manifest 并记录 `manifest_file`。
  - `MockCalibrationRunner` 在 `DONE` 状态写入 latest index；`FAILED/CANCELLED` 不写入 latest。
  - 结果页增加“结果视图”下拉框，支持“当前Session / 最新成功”切换。
  - 结果页的文件表、摘要、会话详情、打开 session/project/workspace 目录和导出摘要均跟随当前结果视图。
  - GUI smoke 覆盖 latest 视图，确认最新成功结果能显示文件行和 latest index 详情。
  - 增加 storage/runner 测试，覆盖 latest 指向成功 manifest、取消不覆盖 latest、失败不覆盖 latest。
- 验证结果：
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 99 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - `FM-10` 的完整历史 session 列表浏览仍未实现，目前只支持当前 session 和 latest 成功 session。
  - `P5-12/FM-11` 旧版输出目录只读兼容展示仍待实现。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/workspace.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_workspace_management.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`
- 下一步：
  - 继续实现历史 session 列表浏览，或转向旧版输出目录只读兼容展示。

### CATR-CAL-TASK-20260719-037 - 登记 exe 打包后文件管理 TODO

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 将 exe 打包后的资源路径、用户配置目录和校准输出目录策略纳入后续 TODO。
  - 暂不实现代码，避免打断当前功能主线。
- 完成内容：
  - 开发 TODO 新增 `P5-13`，要求建立 exe 打包后的运行时路径策略。
  - 文件管理计划新增 `FM-17`，明确区分内置资源目录、用户配置目录、用户资源目录和校准输出目录。
  - TODO 中记录 PyInstaller/源码运行模式识别、首次启动复制默认 JSON/CSV、JSON 相对 CSV 路径解析和内置资源只读兜底。
- 验证结果：
  - 本次仅更新 TODO 文档，未执行测试。
- 还需完成：
  - 后续实现 `runtime_paths.py` 或等价模块，并补充打包 smoke/路径解析测试。
- 关联文件：
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`
- 下一步：
  - 继续推进 latest 成功 session 索引和历史 session 浏览；exe 打包路径策略暂不进入实现。

### CATR-CAL-TASK-20260719-036 - 标准喇叭增益 CSV 由 JSON 引用

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 按“JSON 管配置，CSV 管曲线”的方案，将标准喇叭增益文件引用纳入 `band_config`。
  - 默认配置加载后，界面自动带出当前馈源/喇叭组合对应的增益 CSV。
- 完成内容：
  - `band_config.feed_horn_bands[]` 支持 `horn_gain_file` 字段。
  - UI 选择馈源/喇叭组合时，会按当前 JSON 文件所在目录解析相对路径并填入“喇叭增益文件”输入框。
  - 内置 CATR JSON 为 10-15G、14.5-22G、21.7-33G 组合配置了默认喇叭增益 CSV 引用。
  - 新增 `14P5_22G_horn_gain_10MHz.csv`，由 14.5-22G 标准喇叭增益图表识别后按 10 MHz 步进线性插值生成。
  - JSON 规范文档补充 `horn_gain_file` 字段说明，明确曲线点保存在 CSV 中，不写入主 JSON。
  - GUI smoke 增加默认喇叭增益文件自动带出且存在的检查。
- 验证结果：
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 96 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - 若后续拿到标准喇叭原始证书数据，可再用证书原始点替换当前图表识别曲线。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/config_loader.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/configs/catr_chamber_loss_calibration.json`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/loss_file_policy.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/resources/14P5_22G_horn_gain_10MHz.csv`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_LINK_CONFIG_JSON.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`
  - `catr_loss_calibrator/tests/test_calibration_catalog.py`
  - `catr_loss_calibrator/tests/test_loss_file_policy.py`
- 下一步：
  - 继续推进 latest 成功 session 索引和历史 session 浏览。

### CATR-CAL-TASK-20260719-035 - 频段配置改为 JSON 驱动

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 支持不同项目通过导入链路配置 JSON 定义自己的馈源、标准喇叭和有效频段组合。
  - 校准界面的频段配置和最终路损文件命名使用当前项目配置，而不是固定内置列表。
- 完成内容：
  - `CalibrationCatalog` 增加 `band_config` 字段。
  - 链路配置 JSON loader 支持可选 `band_config`，校验 `feed_horn_bands[].feed/horn/band`，并支持可选 `start_ghz/stop_ghz`。
  - 内置 `catr_chamber_loss_calibration.json` 增加默认 CATR 馈源/喇叭/频段交集配置。
  - `LossFilePolicy` 支持从 `band_config` 创建动态文件命名策略。
  - `CalibrationViewModel` 启动校准时使用当前 catalog 的动态策略。
  - GUI 频段配置下拉框改为从当前 catalog 加载；导入不同 JSON 后自动刷新馈源和喇叭列表，喇叭按当前馈源过滤。
  - 当某个馈源/喇叭组合配置了 `start_ghz/stop_ghz` 时，UI 自动同步网分扫频起止频。
  - 更新 `CATR_LOSS_CALIBRATION_LINK_CONFIG_JSON.md`，补充 `band_config` 结构说明和示例。
- 验证结果：
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 96 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - 如现场需要中文显示馈源/喇叭名称，可在后续扩展 `label` 字段，同时保持文件名短码不变。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/config_loader.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/configs/catr_chamber_loss_calibration.json`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/loss_file_policy.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_LINK_CONFIG_JSON.md`
  - `catr_loss_calibrator/tests/test_calibration_catalog.py`
  - `catr_loss_calibrator/tests/test_loss_file_policy.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
- 下一步：
  - 继续推进 latest 成功 session 索引和历史 session 浏览。

### CATR-CAL-TASK-20260719-034 - 配置绑定的校准文件空间落地

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 按文件管理方案先落地配置绑定 workspace、项目/阶段/轮次 session 目录和结果页基础展示。
  - 让新执行的 Mock 校准文件不再混在旧版输出根目录中。
- 完成内容：
  - 新增 `storage/workspace.py`，提供 `CalibrationRunContext`、`WorkspaceContext`、`SessionContext`、配置 hash、workspace/session 目录生成和 `session_manifest.json` 写入。
  - 校准界面增加“校准批次”输入区：项目代号、校准阶段、批次/轮次、操作员、备注。
  - `CalibrationViewModel.start_selected()` 根据当前链路配置和批次字段创建 session，并让 runner 输出到 `catr_loss_calibrator_output/workspaces/{workspace_id}/projects/{project_code}/sessions/{session_id}`。
  - `MockCalibrationRunner` 在 metadata 和 overview 中写入 `run_uid`、`workspace_id`、`session_root`、`config_hash`、`project_code`、`calibration_stage`、`run_label` 等字段，并在完成/失败/取消时生成 manifest。
  - 结果页摘要和会话详情增加 workspace/project/session/manifest 信息，文件表增加 `MANIFEST` 行，并支持打开当前 workspace/project/session 目录。
  - 新增 workspace 单元测试和 runner session 输出测试，GUI smoke 覆盖 session 模式结果页。
- 验证结果：
  - 通过编译检查：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m py_compile ...`。
  - 通过完整测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 93 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - `FM-08/P5-11`：成功完成后维护 latest 成功输出索引，并支持结果页切换当前/latest/历史 session。
  - `FM-11/P5-12`：旧版输出目录只读兼容展示。
  - `FM-15`：补失败/取消 session 不覆盖 latest 的测试。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/workspace.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_workspace_management.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
  - `catr_loss_calibrator/tests/test_presentation_gui_smoke.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`
- 下一步：
  - 实现 latest 成功 session 索引和结果页 session 浏览能力。

### CATR-CAL-TASK-20260719-033 - 校准文件管理方案与 TODO

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 针对不同链路配置、不同项目、不同阶段/轮次校准文件混淆的问题，形成文件管理完善方案。
  - 对比市面/开源测试采集方案，并沉淀为本项目文件管理 TODO。
- 完成内容：
  - 新增 `CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`。
  - 方案定义配置绑定 workspace、project、session、manifest、latest 索引和旧目录兼容策略。
  - 方案建议校准界面增加项目代号、校准阶段、批次/轮次、操作员和备注字段。
  - 对比 QCoDeS Dataset、Bluesky/Databroker、PyMeasure Results 的数据组织经验。
  - 新增 `FM-01` 至 `FM-16` 文件管理 TODO。
  - 开发 TODO 增加 `P5-08` 至 `P5-12`，把文件管理方案纳入主线任务。
- 验证结果：
  - 本次为文档和 TODO 方案更新，未执行测试。
- 还需完成：
  - 按 `P5-08/P5-09` 先实现 workspace 生成和校准批次 UI。
- 关联文件：
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_FILE_MANAGEMENT_PLAN.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`
- 下一步：
  - 实现 `FM-01` 至 `FM-05`，先完成配置 hash、workspace/session root 和 UI 批次字段。

### CATR-CAL-TASK-20260719-032 - 非法确认操作拦截

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 完成 `UI-66`，在非法操作时进行拦截并给出明确提示。
- 完成内容：
  - `CalibrationViewModel.submit_action()` 改为返回布尔值，调用方可判断操作是否被接受。
  - 对未知动作进行 ERROR 级别拦截，并更新状态栏文本。
  - 对没有活动确认步骤时的确认/跳过/重试/取消进行 WARNING 级别拦截，并提示“当前没有等待确认的校准步骤”。
  - 保持运行中合法动作正常下发给 worker。
  - 增加单元测试覆盖未知动作和无活动 prompt 两类非法操作。
- 验证结果：
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 88 项。
- 还需完成：
  - `UI-65`：支持暂停 / 继续等现场操作动作。
  - `UI-55` 等体验优化项仍待排期。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 根据现场需求决定先做 `UI-65` 暂停/继续，还是做 `UI-55` 折叠 LOG 区。

### CATR-CAL-TASK-20260719-031 - 校准执行按钮状态绑定

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 完成 `UI-64`，将校准执行页按钮状态严格绑定到校准运行状态。
- 完成内容：
  - 收敛“开始校准 / 重新校准”按钮规则：
    - 未运行/Ready：只允许“开始校准”。
    - 运行中/等待确认：两个按钮都禁用。
    - 完成/失败/取消：只允许“重新校准”。
  - GUI smoke 自动检查 idle、running、done 三类按钮状态，防止后续回归。
  - smoke 失败时输出具体失败检查项，方便定位 UI 启动或状态同步问题。
- 验证结果：
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 86 项。
- 还需完成：
  - `UI-65/UI-66`：继续完善暂停/继续和非法操作提示。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_presentation_gui_smoke.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 推进 `UI-66` 非法操作提示，减少无效点击只写 LOG 的情况。

### CATR-CAL-TASK-20260719-030 - GUI Smoke 与 Mock 校准闭环验证

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 完成 `UI-63`，补充 UI 启动和主要交互的自动化测试。
  - 完成 `UI-51`，完成一轮 Mock 校准的完整 UI 流程闭环验证。
- 完成内容：
  - 新增 `--gui-smoke` 启动参数，用于自动化测试中创建 QApplication 和主窗口，但不进入长期事件循环。
  - GUI smoke 路径会导入默认链路配置、连接四类 mock 设备、同步设备卡片和 LOG。
  - GUI smoke 路径会运行一轮完整 Mock 校准，将运行摘要写入 ViewModel，并刷新结果页。
  - smoke 检查覆盖页签、校准项列表、步骤列表、LOG 内容、连接状态、raw/loss/metadata 文件清单和结果表格。
  - 新增 subprocess 级 GUI smoke 测试，使用 `QT_QPA_PLATFORM=offscreen`，更接近真实入口启动路径。
- 验证结果：
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 86 项。
  - 该验证使用 Mock 设备和 offscreen GUI，未做真实显示器截图验证。
- 还需完成：
  - `UI-64/UI-65/UI-66`：继续完善执行按钮状态、暂停/继续和非法操作提示。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_presentation_gui_smoke.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 推进 `UI-64`，将校准执行页按钮状态更严格地绑定到 state machine。

### CATR-CAL-TASK-20260719-029 - 当前步骤自动滚动可见

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 修复校准执行推进到后续细分步骤时，列表选中项可能不在可视区域内的问题。
- 完成内容：
  - 新增列表选中 helper，设置当前行后调用 `scrollToItem(..., PositionAtCenter)`。
  - 校准项列表、步骤列表、细分步骤列表刷新时都会自动滚动到当前选中项。
  - 细分步骤随 runner 推进到新的小步骤时，会自动滚动到当前小步骤。
- 验证结果：
  - `py_compile` 通过：`catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`。
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 85 项。
  - 未做 GUI 手工滚动截图验证。
- 还需完成：
  - `UI-51/UI-63`：补完整 Mock GUI 流程验证和主要 UI 自动化测试。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 继续补 UI 自动化验证，覆盖执行推进时当前步骤可见。

### CATR-CAL-TASK-20260719-028 - 清理历史命令残留状态

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 完成 `UI-62`，清理 ViewModel 中不再展示的历史命令残留状态。
- 完成内容：
  - 删除 `CalibrationViewModel._command_history` 和 `command_history` 属性。
  - `send_device_command()` 不再维护独立历史命令列表，命令发送与响应统一进入实时 LOG。
  - 保留 `command_response` 和 `command_response_changed`，继续支持设备卡片显示当前响应。
  - 增加测试确认命令追踪通过 LOG 完成，且不再暴露旧 `command_history`。
- 验证结果：
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 85 项。
- 还需完成：
  - `UI-51/UI-63`：补完整 Mock GUI 流程验证和主要 UI 自动化测试。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 运行全量测试后继续推进 UI 自动化验证。

### CATR-CAL-TASK-20260719-027 - LOG 复制选中与复制全部

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 完成 `UI-54`，让 LOG 区支持复制选中内容或复制当前可见全部内容。
- 完成内容：
  - LOG 工具栏新增“复制选中”和“复制全部”两个动作。
  - “复制选中”读取 QTextEdit 当前选区，保持换行后写入系统剪贴板。
  - “复制全部”复制当前 LOG 面板可见纯文本内容，因此会跟随当前级别筛选和时间戳开关结果。
- 验证结果：
  - `py_compile` 通过：`catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`。
  - 未做 GUI 手工点击或截图验证。
- 还需完成：
  - `UI-51/UI-63`：补完整 Mock GUI 流程验证和主要 UI 自动化测试。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 继续推进非实机项目，优先补 UI 自动化验证或 UI-62 历史命令残留清理。

### CATR-CAL-TASK-20260719-026 - 校准失败恢复策略

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 完成 `P4-05`，建立 VNA 采样超时、链路箱无响应、保存失败、人工取消的统一失败恢复策略。
  - 失败时必须能回答：失败类型、发生状态、步骤/小步骤、原始错误、建议恢复动作。
- 完成内容：
  - 新增 `calibration/recovery.py`，定义 `CalibrationFailureKind`、`RecoveryAction`、`CalibrationFailure` 和 `CalibrationRunError`。
  - runner 在小步骤执行异常时进入 `FAILED`，记录 `failure:*` 事件，并在 `overview()` 中暴露 `failure_kind`、`failure_action`、`failure_state`、`failure_step_id`、`failure_substep_id`、`failure_message`。
  - 人工取消保持 `CANCELLED` 终态，同时记录 `operator_cancelled` 和 `stopped_by_operator`，便于 session 追溯。
  - LOG 事件格式化支持 `failure:*`，在 UI 中按 `ERROR` 等级显示失败类型、步骤、状态和建议动作。
  - 单元测试覆盖链路箱超时、VNA 读数超时、保存路径失败、人工取消和 LOG failure 格式化。
- 验证结果：
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 84 项。
  - 本次使用 Mock/单元测试验证失败策略，未接真实 VNA 或 LCD74000F 做故障注入。
- 还需完成：
  - `P4-01/P4-02`：真实 VNA 和 LCD74000F 实机联调，确认真实超时/错误队列能正确映射到当前 failure kind。
  - `UI-51/UI-63`：补完整 GUI 流程和异常路径自动化验证。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/recovery.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
- 下一步：
  - 优先推进 `P4-01/P4-02` 实机验证，或者先补 `UI-54` LOG 复制以提升现场排障效率。

### CATR-CAL-TASK-20260719-025 - TODO 优先级重排与参数角色分类

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 重新审查当前 TODO 与代码实现的吻合度，按当前验收风险调整后续优先级。
  - 完成 `P1-05`，让正式输出、原始 `S21_*`、临时追溯参数具备结构化角色。
  - 完成 `P1-06`，用单元测试锁定链路模板的直通、AMP1、AMP2、SG、SA、VNA1/VNA2 工况。
- 完成内容：
  - 将开发 TODO 的推荐执行顺序更新为当前剩余风险优先：参数角色、链路矩阵测试、失败恢复、实机验证、UI 验证、长期治理。
  - 新增 `OutputRole`、`OutputParameter` 和 `classify_output_parameter()`，支持按声明位置区分 raw/final，避免把 `raw_outputs` 中的中间 `L_*` 误判为正式输出。
  - `TraceRecord`、CSV 输出和 metadata 增加 `output_role` / `input_roles` / `output_roles`，生成文件可直接追溯参数角色。
  - 增加链路模板矩阵测试，覆盖 DUT-SA、DUT-AMP1-SA、DUT-VNA2、DUT-AMP1-VNA2、H/V-VNA1、H/V-AMP2-VNA1、H/V-SA、H/V-AMP2-SA、H/V-SG、H/V-AMP2-SG。
  - 增加 AMP1/AMP2 方向非法用例测试，防止链路方向回归。
- 验证结果：
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 80 项。
  - 本次不涉及真实硬件验证。
- 还需完成：
  - `P4-05`：补 VNA 超时、链路箱无响应、保存失败、人工取消后的统一恢复策略。
  - `UI-51/UI-54/UI-63`：补完整 Mock GUI 流程验证、LOG 复制和 UI 自动化测试。
- 关联文件：
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/csv_storage.py`
  - `catr_loss_calibrator/tests/test_calibration_catalog.py`
  - `catr_loss_calibrator/tests/test_link_management.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
- 下一步：
  - 推进 `P4-05`，先定义失败恢复策略与 runner/ViewModel 的错误状态边界。

### CATR-CAL-TASK-20260719-024 - N5245B VNA 命令链路同步

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 对照 `docs/N5245B_SCPI_Command_Reference.md` 和静区测试软件稳定 VNA 实现同步真实 VNA adapter 和 UI 预设。
  - 优先使用 N5245B/PNA-X 推荐的复数 `SDATA` 读取路径。
- 完成内容：
  - 参考 `src/quiet_zone_tester/hardware/vna/scpi.py` 和 `tests/test_vna_scpi.py`，自动采集路径收敛为稳定链路：`TRIG:SOUR IMM` + `SENS1:SWE:MODE SING`，不额外下发 `INIT1:IMM`。
  - `PyVisaVna.configure_power()` 默认使用静区测试已验证的 `SOUR:POW`，保留 N5245B 端口功率命令为 UI 手动预设。
  - `PyVisaVna.read_s_parameter()` 设置 `FORM:DATA REAL,64` 和 `FORM:BORD SWAP` 后读取 `CALC:DATA? SDATA`，优先使用二进制 `query_binary_values`，无二进制能力时回退 ASCII。
  - `PyVisaVna.configure_sweep()` 配置后读取 `SENS:FREQ:STAR?`、`SENS:FREQ:STOP?`、`SENS:SWE:POIN?`，以仪器实际值更新内部状态。
  - VNA 预设增加 N5245B 端口功率、N5245B INIT 手动验证命令、`FORM:DATA REAL,64`、`FORM:BORD SWAP`、ASCII 数据和 `CALC1:DATA? SDATA/FDATA`；默认“立即触发”仍使用稳定的 `SENS1:SWE:MODE SING`。
  - 增加单元测试覆盖 SDATA 优先、稳定功率命令、稳定单次触发流程和扫频实际值回读。
- 验证结果：
  - `py_compile` 通过：`hardware/vna/pyvisa_vna.py`、`presentation/viewmodels.py`。
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 76 项。
  - 未做真实 N5245B 硬件联机验证。
- 还需完成：
  - 真实硬件接入时核对二进制 REAL64 / ASCII 数据模式、VISA 端序和仪器错误队列。
- 关联文件：
  - `docs/N5245B_SCPI_Command_Reference.md`
  - `catr_loss_calibrator/src/catr_loss_calibrator/hardware/vna/pyvisa_vna.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/tests/test_pyvisa_vna.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
- 下一步：
  - 按真实 VNA 资源地址执行最小 sweep 验证并记录硬件信息。

### CATR-CAL-TASK-20260719-023 - N5183B 与 N9020B 常用预设命令

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 信号源型号列表包含 `N5183B`。
  - 频谱仪型号列表包含 `N9020B`。
  - 为信号源和频谱仪补齐现场常用基础 SCPI 预设。
- 完成内容：
  - 信号源预设增加清状态、查询错误、频率查询、功率查询、关闭输出和输出状态查询。
  - 频谱仪预设增加清状态、查询错误、频谱模式、频谱测量配置、中心/起止频、Span、点数、RBW/VBW、参考电平、衰减、前置放大、连续测量、频谱数据读取、峰值搜索和 Marker 读数。
  - 增加 ViewModel 单元测试，锁定 `N5183B` / `N9020B` 型号选项和关键预设命令。
  - 参考 QCoDeS `KeysightN5183B` / `KeysightN9030B` 驱动和 Keysight X-Series 资料交叉核对命令方向；N9020B 与 N9030B 均按 X-Series 信号分析仪基础频谱测量口径处理。
- 验证结果：
  - `py_compile` 通过：`presentation/viewmodels.py`。
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 75 项。
  - 未做真实 N5183B / N9020B 硬件联机验证。
- 还需完成：
  - 后续接真实仪表时按设备固件版本核对 SCPI 响应和错误队列。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`
- 下一步：
  - 运行回归测试并在真实硬件验证清单中记录后续联机结果。

### CATR-CAL-TASK-20260719-022 - 结果曲线自适应范围按钮

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 在结果页曲线预览区增加一键自适应当前曲线范围的操作。
- 完成内容：
  - 在曲线预览工具栏增加“自适应”按钮。
  - 加载 CSV 曲线后自动启用按钮，并在绘图后执行一次自动范围适配。
  - 点击按钮时调用 pyqtgraph `autoRange`，按当前曲线重新适配 X/Y 轴范围。
  - 无可绘制曲线或未安装 pyqtgraph 时禁用按钮或给出状态提示。
- 验证结果：
  - `py_compile` 通过：`presentation/main.py`。
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 70 项。
  - 未做 GUI 截图验证，未做真实硬件验证。
- 还需完成：
  - 后续可补 GUI 截图或人工操作记录，确认按钮在实际窗口中的位置和交互效果。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`
- 下一步：
  - 继续根据现场使用反馈优化结果页曲线交互。

### CATR-CAL-TASK-20260719-021 - 结果页文件索引与曲线预览

- 状态：完成
- 日期：2026-07-19
- 任务目标：
  - 让结果页显示本次运行生成的 raw、final/loss、metadata 文件。
  - 支持结果文件路径复制、打开目录、导出 session 摘要。
  - 支持选中 CSV 后直接预览频率-GHz / dB 曲线。
- 完成内容：
  - `MockCalibrationRunner.overview()` 增加 `output_root`、`raw_files`、`loss_files`、`metadata_files`。
  - 结果页新增生成文件表格，按 `FINAL`、`RAW`、`METADATA` 分类展示文件名、大小、修改时间和完整路径。
  - 结果页新增刷新结果、复制路径、打开目录和导出摘要按钮。
  - 结果页新增 CSV 曲线预览，自动识别频率列和常见 dB 数据列。
  - 同步更新 UI TODO、开发 TODO 和 LOG 功能描述。
- 验证结果：
  - `py_compile` 通过：`calibration/mock_runner.py`、`presentation/main.py`。
  - 通过测试：`D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe -m pytest catr_loss_calibrator\tests`，共 70 项。
  - 仅完成 Mock/UI 代码验证，未做真实硬件验证。
- 还需完成：
  - 后续可补 GUI 自动化截图验证结果页表格和曲线在实际窗口中的布局。
  - LOG 复制选中内容或全部内容仍按 `UI-54` 跟踪。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`
- 下一步：
  - 继续补结果页 GUI 截图验证，或推进真实硬件下的文件输出一致性检查。

### CATR-CAL-TASK-20260718-020 - 小步骤确认内嵌到步骤执行页

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 避免小步骤确认弹窗遮挡步骤执行内容。
  - 将确认动作改为页面内嵌状态组件，而不是弹窗式去重逻辑。
- 完成内容：
  - 在“开始校准”按钮右侧新增内嵌确认条，显示当前 STEP 的接线确认或保存确认。
  - 保留“上一步 / 确认 / 下一步 / 取消”动作，其中开始确认阶段隐藏“上一步”，保存确认阶段显示“上一步”。
  - 移除小步骤确认的 `_last_confirmation_prompt_key` 和 `_show_prompt_action_dialog` 弹窗式逻辑。
  - 当前 runner prompt 通过 `StepViewData.confirm_phase` 直接同步到页面确认条；无确认阶段时自动隐藏。
- 验证结果：
  - `py_compile` 通过：`presentation/main.py`。
  - 通过测试：`test_calibration_catalog.py`、`test_mock_runner.py`、`test_link_management.py`、`test_presentation_viewmodels.py`，共 33 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - 后续可补 GUI 自动化截图验证确认条在不同阶段的按钮状态。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/style/style_bule.qss`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 继续按实际操作体验优化确认条文案和按钮布局。

### CATR-CAL-TASK-20260718-019 - runner 使用仪表配置页网分参数

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 校准执行时使用仪表配置页中的网分扫频参数，而不是 runner 固定默认参数。
- 完成内容：
  - `MockCalibrationRunner` 增加 `vna_settings`，每个小步骤按传入的起频、止频、点数、功率、IFBW、S 参数和连续扫描设置配置网分。
  - GUI 开始校准确认时读取网分卡片当前配置，并传入 `CalibrationViewModel.start_selected()`。
  - 开始确认弹窗显示本次使用的网分扫频范围、点数和步进。
- 验证结果：
  - `py_compile` 通过：`calibration/mock_runner.py`、`presentation/viewmodels.py`、`presentation/main.py`。
  - 通过测试：`test_calibration_catalog.py`、`test_mock_runner.py`、`test_link_management.py`、`test_presentation_viewmodels.py`，共 33 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - 后续接真实网分时验证 SCPI 配置、触发、读数与实际仪器状态一致。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 继续推进真实硬件验证与采集数据计算闭环。

### CATR-CAL-TASK-20260718-018 - STEP 级细分步骤说明

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将小步骤说明从宽泛的大步骤话术改为具体 STEP 操作说明。
- 完成内容：
  - 内置 CATR JSON 中所有显式细分步骤 `manual_instruction` 均以 `STEPn` 开头。
  - 每条 STEP 说明包含当前接线路径、极化人工确认要求、链路箱命令和 raw/final 保存输出。
  - 确认弹窗和“命令 / 说明”区域显示当前 `STEPn`，与左侧细分步骤列表保持一致。
- 验证结果：
  - 检查内置 JSON 中细分步骤说明均包含 STEP，且无 `??` 乱码。
  - `py_compile` 通过：`presentation/main.py`、`presentation/viewmodels.py`。
  - 通过测试：`test_calibration_catalog.py`、`test_mock_runner.py`、`test_link_management.py`、`test_presentation_viewmodels.py`，共 31 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - 后续根据现场操作口径继续优化每个 STEP 的文字粒度。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/configs/catr_chamber_loss_calibration.json`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 继续检查实际操作流程中是否还有大步骤话术残留。

### CATR-CAL-TASK-20260718-017 - 启动空配置与默认配置导入按钮

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - GUI 启动时不自动加载默认 CATR 配置，校准项列表保持空。
  - 在导入链路配置入口右侧增加“导入默认配置”按钮，由用户手动加载内置配置。
- 完成内容：
  - `CalibrationViewModel` 启动时使用空 catalog，并在 LOG 中提示未加载链路配置。
  - 新增 `load_default_catalog()`，点击“导入默认配置”后加载内置 `catr_chamber_loss_calibration.json`。
  - GUI 空状态下保护校准项列表、步骤列表、overview 和“开始校准”动作，避免未加载配置时误启动 runner。
  - 链路配置文本框显示“未加载链路配置”，导入默认或外部配置后同步更新路径。
- 验证结果：
  - `py_compile` 通过：`presentation/viewmodels.py`、`presentation/main.py`。
  - 通过测试：`test_calibration_catalog.py`、`test_mock_runner.py`、`test_link_management.py`、`test_presentation_viewmodels.py`，共 31 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - 后续可补充 GUI 自动化验证按钮点击后的列表刷新。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 继续完善配置导入后的执行参数、硬件连接和数据计算闭环。

### CATR-CAL-TASK-20260718-016 - 外部链路配置导入入口

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 完成 UI-68 / UI-70 / UI-72，支持在 GUI 中导入链路配置 JSON，并显示当前配置来源。
- 完成内容：
  - `CalibrationViewModel.load_catalog()` 支持加载外部 JSON、替换当前 catalog、清空旧运行状态并刷新 overview。
  - GUI header 区分“通用路损校准控制台”和“当前配置”，显示配置名称、schema 版本和来源文件路径。
  - 在“校准执行”页的“频段配置”上方新增“导入链路配置”入口，支持选择 JSON 文件；导入成功后刷新校准项、步骤、细分步骤、接线路径和链路箱命令预设。
  - 导入失败时弹窗显示文件路径和 loader 返回的字段/错误原因。
- 验证结果：
  - `py_compile` 通过：`presentation/viewmodels.py`、`presentation/main.py`。
  - 通过测试：`test_calibration_catalog.py`、`test_mock_runner.py`、`test_link_management.py`、`test_presentation_viewmodels.py`，共 30 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - 后续可补充 GUI 自动化冒烟，直接验证文件选择后的界面刷新。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 继续按 TODO 推进真实硬件、数据计算或 GUI 自动化验证项。

### CATR-CAL-TASK-20260718-015 - JSON 驱动接线路径与细分步骤详情

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将接线路径节点图从 UI 层硬编码迁移到内置 CATR JSON 配置。
  - 让步骤执行页的接线路径、命令和说明随细分步骤切换而变化。
- 完成内容：
  - 为内置 `catr_chamber_loss_calibration.json` 补齐 `node_catalog`、`path_templates` 和步骤/细分步骤 `path_template` 引用。
  - `StepViewData`、`SubStepViewData` 和 Mock runner 自动生成的小步骤均携带 `path_template` / `path`。
  - UI 接线路径优先读取 JSON `path` / `path_templates`，节点标签和样式角色从 `node_catalog` 获取。
  - 步骤执行页点击细分步骤时，同步刷新接线路径、命令说明和步骤详情；运行中的确认提示仍自动聚焦当前小步骤。
- 验证结果：
  - `py_compile` 通过：`config_loader.py`、`models.py`、`mock_runner.py`、`presentation/viewmodels.py`、`presentation/main.py`。
  - 通过测试：`test_calibration_catalog.py`、`test_mock_runner.py`、`test_link_management.py`、`test_presentation_viewmodels.py`，共 28 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - 增加用户可选文件的“导入链路配置”入口和错误提示。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/configs/catr_chamber_loss_calibration.json`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/viewmodels.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_calibration_catalog.py`
  - `catr_loss_calibrator/tests/test_presentation_viewmodels.py`
- 下一步：
  - 执行 UI-68 / UI-72，增加外部 JSON 配置导入入口，并在导入失败时显示字段路径和错误原因。

### CATR-CAL-TASK-20260718-014 - 通用控制台与 JSON catalog 导入基础

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将 UI/CLI 名称从“CATR 路损校准操作台”调整为“通用路损校准控制台”。
  - 生成当前 CATR 五个 `LINK-CAL` 校准项的内置 JSON 配置。
  - 建立链路配置 JSON loader，并让默认 catalog 从内置 JSON 加载。
- 完成内容：
  - 新增 `calibration/configs/catr_chamber_loss_calibration.json`，包含 `LINK-CAL-001` 至 `LINK-CAL-005` 的校准项、大步骤、细分步骤、链路命令和输出/依赖参数。
  - 新增 `calibration/config_loader.py`，支持校验 schema 版本、加载 JSON 并转换为 `CalibrationCatalog`。
  - 扩展 `CalibrationCatalog`、`CalibrationStep`、`CalibrationSubStep`，为后续 JSON 驱动节点图预留 `node_catalog`、`path_templates`、`path_template` 和 `path` 字段。
  - `default_calibration_catalog()` 已改为加载内置 JSON，原 Python catalog 保留为 `legacy_python_calibration_catalog()` 供迁移期测试对照。
  - UI/CLI 标题改为“通用路损校准控制台”，当前 CATR 作为已加载配置显示。
  - 更新开发 TODO 与 UI TODO，标记已完成阶段并保留 JSON 节点图迁移任务。
- 验证结果：
  - `py_compile` 通过：`models.py`、`config_loader.py`、`definitions.py`、`presentation/main.py`。
  - 通过测试：`test_calibration_catalog.py`、`test_mock_runner.py`、`test_link_management.py`、`test_presentation_viewmodels.py`，共 25 项。
  - 仅完成 Mock/导入验证，未做真实硬件验证。
- 还需完成：
  - 为内置 CATR JSON 补齐 `node_catalog`、`path_templates` 和每个步骤/细分步骤的 `path_template` 引用。
  - 将 UI 接线路径节点图从 presentation 层硬编码模板迁移到 JSON 配置。
  - 增加用户可选文件的“导入链路配置”入口和错误提示。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/config_loader.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/configs/catr_chamber_loss_calibration.json`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/definitions.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_calibration_catalog.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_TODO.md`
- 下一步：
  - 执行 P1-13 / P1-12 / UI-71，先把 HTML 节点图落入 JSON，再让 UI 使用 JSON 路径绘制。

### CATR-CAL-TASK-20260718-013 - P5 追溯与导出基础

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 建立校准 session 管理、日志与错误报告、结果导出基础。
  - 让最终结果和运行记录具备追溯与浏览能力。
- 完成内容：
  - 扩展 `CalibrationSessionRepository`，支持会话记录保存。
  - 扩展 `ErrorReport` 与 `LogRecord`，支持 JSON 落盘。
  - 新增 `report_exporter.py`，支持 session 报告 JSON/CSV 导出。
  - 新增 `tests/test_p5_reporting.py`。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - 生成的 session、log、error、report 文件可正常写出。
- 还需完成：
  - P5-04 / P5-05：长期稳定性测试与版本管理。
  - P5-06：继续跟随 HTML 方案同步文档变更。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/calibration_session_repository.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/diagnostics/error_report.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/diagnostics/log_record.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/report_exporter.py`
  - `catr_loss_calibrator/tests/test_p5_reporting.py`
- 下一步：
  - 推进 P5-04 / P5-05，补长期稳定性和版本管理。

### CATR-CAL-TASK-20260718-012 - P4 超时回滚与硬件验证记录

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 建立真实硬件连接失败后的超时/回滚策略。
  - 建立真实硬件验证记录模型。
  - 固化真实硬件验证 checklist。
- 完成内容：
  - 新增 `ConnectionRecoveryPolicy`，支持连接重试与回滚清理。
  - `InstrumentConnectionService` 连接失败后会自动清理已连接仪表，并支持按策略重试。
  - 新增 `HardwareValidationRecord` 与 `save_hardware_validation_record()`。
  - 新增 `tests/test_hardware_validation.py`。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - 未接入真实 VNA/LCD74000F，未做真实硬件验证。
- 还需完成：
  - P4-01 / P4-02：真实设备实机联调。
  - 若现场需要，可继续补充更细的命令级错误映射。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/instrument_management/recovery.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/instrument_management/connection_service.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/diagnostics/hardware_validation.py`
  - `catr_loss_calibrator/tests/test_instrument_management.py`
  - `catr_loss_calibrator/tests/test_hardware_validation.py`
- 下一步：
  - 回到 P4-01 / P4-02，等真实设备信息补全后做上机验证。

### CATR-CAL-TASK-20260718-011 - P4 硬件适配与连接管理骨架

- 状态：进行中
- 日期：2026-07-18
- 任务目标：
  - 建立真实 VNA VISA adapter 和真实 LCD74000F 链路箱 adapter。
  - 建立仪表连接管理、状态快照、资源互锁和失败回滚。
  - 准备真实硬件验证清单。
- 完成内容：
  - 新增 `PyVisaVna`，支持真实 VNA 连接、扫频配置、触发和读取接口骨架。
  - 新增 `Lcd74000fLinkBox`，支持真实链路箱连接与命令下发骨架。
  - 重构 `InstrumentConnectionService`，支持 mock / real-capable 配置、连接快照和异常回滚。
  - 新增 `InstrumentManagementService`，提供资源独占、连接管理与统一快照。
  - 新增 `HARDWARE_VALIDATION_CHECKLIST.md`。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - 未接入真实 VNA/LCD74000F，未做真实硬件验证。
- 还需完成：
  - P4-01 / P4-02：真实设备上机验证与命令兼容性确认。
  - P4-05：超时、失败恢复和人工取消的完整策略。
  - P4-06：真实硬件验证记录落地。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/hardware/vna/pyvisa_vna.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/hardware/link_box/lcd74000f.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/instrument_management/connection_service.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/instrument_management/instrument_management_service.py`
  - `catr_loss_calibrator/docs/HARDWARE_VALIDATION_CHECKLIST.md`
- 下一步：
  - 推进真实硬件接入验证，优先补 P4-01 / P4-02 的实机联调。

### CATR-CAL-TASK-20260718-010 - P3 状态展示与非法操作防护

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 让 UI/CLI 显示当前校准项、步骤、接线说明、链路命令和运行状态。
  - 对未连接仪表、重复启动等非法操作进行阻止。
- 完成内容：
  - 为 `MockCalibrationRunner` 增加 `overview()` 和 `format_step_status()`。
  - 在 runner 中加入运行前连接检查，并禁止 busy 状态重复启动。
  - `presentation.main` 在 demo 和交互模式下输出状态概览。
  - 新增测试覆盖状态概览和未连接仪表异常。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - CLI demo 输出状态概览正常。
  - 未执行真实硬件验证。
- 还需完成：
  - 进入 P4，开始真实硬件适配与可靠性。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
- 下一步：
  - 推进 P4-01 / P4-02，接真实 VNA 和 LCD74000F adapter。

### CATR-CAL-TASK-20260718-009 - P3 人工确认与交互入口

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 建立人工接线确认步骤，支持暂停、跳过、重试和取消。
  - 建立一期 UI/CLI 操作入口，面向操作人员逐步执行。
- 完成内容：
  - 扩展 `MockCalibrationRunner`，支持 `confirm_step` 回调与 `continue/skip/retry/cancel` 行为。
  - `presentation.main` 增加 `--interactive` 模式，可按步骤输出接线说明、链路命令并接收操作员选择。
  - 新增/扩展 `tests/test_mock_runner.py`，覆盖 skip/cancel 流程。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - CLI demo 和交互入口均可运行。
  - 未执行真实硬件验证。
- 还需完成：
  - P3-05 / P3-06：UI 状态展示与非法操作阻止。
  - 后续可把交互入口从 CLI 扩展为正式图形界面。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
- 下一步：
  - 推进 P3-05 / P3-06，把 UI 状态展示和非法操作防护补上。

### CATR-CAL-TASK-20260718-008 - P3 Mock 流程与状态机

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 建立 Mock VNA 与 Mock 链路箱的完整校准流程模拟。
  - 建立校准执行状态机。
  - 提供一个最简 UI/CLI 入口展示校准项与执行状态。
- 完成内容：
  - 新增 `CalibrationStateMachine`，支持 `IDLE -> WAIT_MANUAL_CONFIRM -> CONFIGURE_LINK -> CONFIGURE_VNA -> TRIGGER_SWEEP -> READ_TRACE -> SAVE_RAW -> COMPUTE_OUTPUT -> SAVE_OUTPUT -> DONE` 的受控迁移。
  - 新增 `MockCalibrationRunner`，可按步骤执行 Mock 校准、保存 raw trace 和 metadata。
  - `presentation.main.run()` 现在会展示校准项，并跑一遍 demo Mock 流程。
  - 新增 `tests/test_mock_runner.py` 覆盖状态机、Mock runner 和 CLI 入口。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - CLI demo 可运行并输出校准项与 Mock runner 状态。
  - 未执行真实硬件验证。
- 还需完成：
  - P3-03：人工接线确认步骤的暂停、跳过、重试和取消。
  - P3-04：正式 UI 主窗口或 CLI/TUI 操作入口。
  - P3-05 / P3-06：UI 状态展示与非法操作阻止。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/state_machine.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/mock_runner.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/presentation/main.py`
  - `catr_loss_calibrator/tests/test_mock_runner.py`
- 下一步：
  - 推进 P3-03 / P3-04，把人工确认和 UI 入口做成真正可操作的流程。

### CATR-CAL-TASK-20260718-007 - P2 文件命名与频段交集闭环

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将最终路损文件命名规则串到保存流程。
  - 建立馈源/喇叭有效频段交集校验。
- 完成内容：
  - 在 `LossFilePolicy` 中新增 `validate_feed_horn()`、`filename_for()`、`path_for()`。
  - 在 `save_loss_record_with_policy()` 中自动推导 band 并写回最终记录。
  - 扩展 `tests/test_loss_file_policy.py` 和 `tests/test_storage_models.py`。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用当前测试函数通过。
  - 未执行真实硬件验证。
- 还需完成：
  - 进入 P3：Mock 流程与操作员 UI。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/loss_file_policy.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/loss_file_storage.py`
  - `catr_loss_calibrator/tests/test_loss_file_policy.py`
  - `catr_loss_calibrator/tests/test_storage_models.py`
- 下一步：
  - 推进 P3-01 / P3-02，开始 Mock 校准流程与状态机。

### CATR-CAL-TASK-20260718-006 - P2 公式与 metadata 闭环

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将 5 个校准项的最终输出公式落到代码。
  - 建立 metadata 保存策略，记录项目、仪表、链路命令和文件追溯信息。
  - 为每个最终输出参数建立带符号 dB 的单元测试。
- 完成内容：
  - 在 `calibration/formulas.py` 中补齐 `LINK-CAL-001` 至 `LINK-CAL-005` 的核心最终输出公式。
  - 新增 `aux_loss()`、`link_cal_002_*()`、`link_cal_003_*()`、`link_cal_004_*()`、`link_cal_005_*()` 等公式入口。
  - 新增 `storage.models.MetadataRecord`，并让 `write_metadata()` 支持直接写出 dataclass。
  - 扩展 `tests/test_formulas.py` 与 `tests/test_storage_models.py`，覆盖带符号 dB 计算和 metadata 落盘。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动加载并调用当前测试函数通过。
  - 未执行真实硬件验证。
- 还需完成：
  - P2-06：进一步打通最终路损文件命名规则与保存流程。
  - P2-07：补齐馈源/喇叭频段交集校验。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/formulas.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/metadata_writer.py`
  - `catr_loss_calibrator/tests/test_formulas.py`
  - `catr_loss_calibrator/tests/test_storage_models.py`
- 下一步：
  - 继续推进 P2-06 / P2-07，并开始把 metadata 串到 session 级保存流程。

### CATR-CAL-TASK-20260718-001 - 项目骨架与开发 TODO 建立

- 状态：进行中
- 日期：2026-07-18
- 任务目标：
  - 建立 `catr_loss_calibrator` 独立项目骨架。
  - 将 UI / presentation 层提前，面向操作人员组织入口。
  - 建立 P0-P5 开发 TODO 与任务进度记录机制。
- 完成内容：
  - 补齐 `presentation`、`application`、`instrument_management`、`link_management`、`hardware`、`storage`、`project`、`diagnostics` 等基础目录。
  - 新增 `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`。
  - 新增 `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`。
  - 将校准 catalog 调整为 `LINK-CAL-001` 至 `LINK-CAL-005`。
  - 初步建立链路端口枚举、链路命令模板和 LCD74000F profile 骨架。
- 验证结果：
  - `PYTHONPATH=src python -m catr_loss_calibrator` 可运行，并列出 5 个校准项。
  - 当前环境未安装 `pytest`，未执行 pytest 测试。
  - 未做真实硬件验证。
- 还需完成：
  - 按 `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` 逐项核对 catalog、公式和输出参数。
  - 建立 import 边界测试，确认不依赖 `quiet_zone_tester.*`。
  - 增加链路模板和公式单元测试。
- 关联文件：
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_TASK_PROGRESS.md`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/definitions.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/link_management/`
- 下一步：
  - 优先执行 P0-05 和 P0-06，收口 catalog 与公式口径。

### CATR-CAL-TASK-20260718-002 - P0 口径收口与边界测试

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将 `LINK-CAL-001` 至 `LINK-CAL-005` 的 catalog 与 HTML 方案对齐。
  - 检查并固定公式口径，避免引入 `AUX_CORR` 或将 `L_AUX_*` 误改成正损耗约定。
  - 建立项目级 import 边界测试。
- 完成内容：
  - 修正 `calibration/definitions.py` 中 `LINK-CAL-003`、`LINK-CAL-004`、`LINK-CAL-005` 的名称与输出参数。
  - 增加 catalog 单元测试，覆盖 `LINK-CAL-003`、`LINK-CAL-004`、`LINK-CAL-005` 的关键输出。
  - 增加公式源代码检查测试，确认未出现 `AUX_CORR` 或正损耗转换口径。
  - 增加项目边界测试，确认 `src/catr_loss_calibrator` 与 `tests` 中不包含旧运行时导入依赖。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用所有测试函数通过。
  - `python -m pytest` 在当前环境中末尾卡住，未作为最终验证依据。
- 还需完成：
  - 后续继续推进 P1：链路箱 profile 数据化和每个校准步骤的输入/输出/接线定义。
  - 进一步将 `LINK-CAL-002/003/004/005` 的公式实现补齐到 `calibration/formulas.py`。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/definitions.py`
  - `catr_loss_calibrator/tests/test_calibration_catalog.py`
  - `catr_loss_calibrator/tests/test_formulas.py`
  - `catr_loss_calibrator/tests/test_project_boundaries.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
- 下一步：
  - 进入 P1-03 / P1-04，开始把链路箱 profile 和各校准步骤字段数据化。

### CATR-CAL-TASK-20260718-003 - 链路箱 profile 数据化

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 将 `resource/LCD74000F.md` 中的常用链路命令整理为软件内 profile 数据。
  - 让 `LinkService` 能按 route_id 直接应用链路。
  - 为后续校准步骤模型提供稳定的链路模板入口。
- 完成内容：
  - 在 `link_management/lcd74000f_profile.py` 中建立默认 route catalog，覆盖 DUT/SA、DUT/VNA2、H/V、AMP1、AMP2、SG 等常用链路。
  - 为 `LinkService` 增加 `apply_route_id()`。
  - 增加 `test_link_management.py`，验证 route catalog、route_id 应用和命令生成。
  - 修复 `LinkService` 默认 profile 共享实例问题，改为 `default_factory`。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用全部测试函数通过。
  - `pytest` 在该环境中仍存在收集/运行卡顿问题，未作为最终依据。
- 还需完成：
  - 继续 P1-04：为每个 `LINK-CAL` 步骤补齐输入端口、输出端口、人工接线说明和链路箱指令。
  - 后续根据 HTML 方案进一步细化 CAL-004 / CAL-005 的路由对应关系。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/link_management/lcd74000f_profile.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/link_management/link_service.py`
  - `catr_loss_calibrator/tests/test_link_management.py`
  - `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_DEVELOPMENT_TODO.md`
- 下一步：
  - 进入 P1-04，开始把每个校准步骤的数据字段补齐。

### CATR-CAL-TASK-20260718-004 - 校准步骤结构化字段补齐

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 为每个 `LINK-CAL` 步骤补齐输入端口、输出端口、人工接线说明和链路箱指令字段。
  - 让校准 catalog 不再只依赖自然语言说明，而是提供可编排的结构化数据。
- 完成内容：
  - 扩展 `CalibrationStep`，新增 `input_port`、`output_port` 和 `route_ids` 字段。
  - 为 `LINK-CAL-001` 至 `LINK-CAL-005` 的各个步骤补齐结构化端口信息。
  - 为 `LINK-CAL-003/004/005` 关键步骤补齐 route IDs，便于后续 UI / runner 直接复用链路模板。
  - 新增 `tests/test_link_management.py` 的步骤字段测试。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用全部测试函数通过。
  - 未执行真实硬件验证。
- 还需完成：
  - 继续 P2：把 `CalibrationStep` 的结构化字段连接到 raw trace、metadata 和最终输出保存链路。
  - 进一步把 `LINK-CAL-002` 的三工况和 `LINK-CAL-004/005` 的一致性校验量补成执行器可直接消费的模型。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/calibration/definitions.py`
  - `catr_loss_calibrator/tests/test_link_management.py`
- 下一步：
  - 转入 P2-01 / P2-02，开始做 trace 与 raw/final 存储闭环。

### CATR-CAL-TASK-20260718-005 - trace 模型与 raw/final 存储边界

- 状态：完成
- 日期：2026-07-18
- 任务目标：
  - 建立统一 trace 数据模型。
  - 建立原始 S21 保存策略，区分 raw trace 和最终路损文件。
- 完成内容：
  - 新增 `storage/models.py`，定义 `TraceRecord` 作为统一 trace 记录。
  - 扩展 `raw_trace_storage.py`，增加 `trace_record_from_sparameter()`。
  - 新增 `loss_file_storage.py` 的 `save_loss_record()`，统一最终路损 CSV 保存入口。
  - 新增 `tests/test_storage_models.py`，覆盖 trace 记录生成与最终文件保存。
- 验证结果：
  - 使用 `d:\Microsoft\Python\quiet-zone-tester-venv\Scripts\python.exe` 手动调用全部测试函数通过。
  - 未执行真实硬件验证。
- 还需完成：
  - P2-03：补齐 metadata 保存策略，记录项目配置、仪表信息、链路命令和 hash。
  - P2-04：将 5 个校准项的最终输出公式逐项落到 `calibration/formulas.py`。
- 关联文件：
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/models.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/raw_trace_storage.py`
  - `catr_loss_calibrator/src/catr_loss_calibrator/storage/loss_file_storage.py`
  - `catr_loss_calibrator/tests/test_storage_models.py`
- 下一步：
  - 进入 P2-03 / P2-04，开始补 metadata 和公式闭环。
