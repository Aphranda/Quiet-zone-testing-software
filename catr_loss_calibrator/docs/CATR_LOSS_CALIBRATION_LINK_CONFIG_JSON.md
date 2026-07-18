# CATR 路损校准链路配置 JSON 规范

Status: Draft
Domain: CATR_LOSS_CALIBRATOR
Canonical: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_LINK_CONFIG_JSON.md`
Related: `catr_loss_calibrator/docs/CATR_LOSS_CALIBRATION_UI_DESIGN.md`, `catr_loss_calibrator/docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`
更新时间：2026-07-18

本文定义“路损校准操作台”后续作为通用组件时的导入 JSON 形式。导入链路配置后，软件应能生成校准项、校准大步骤、细分步骤、链路箱命令、结果字段和接线路径节点图。

## 1. 设计原则

- JSON 是配置契约，不保存运行状态。
- 内部命令、结果参数和文件字段保持原始标识，不做 UI 简称替换。
- UI 展示用名称由 `display_name`、`nodes[].label` 或 `node_catalog` 控制。
- 接线路径采用节点图形式，不依赖从自然语言说明中猜测。
- 校准结构对齐当前代码模型：`CalibrationCatalog -> CalibrationItem -> CalibrationStep -> CalibrationSubStep`。
- `steps` 是大步骤，`substeps` 是执行最小单位；进度条、确认弹窗和保存确认都以 `substeps` 为最小粒度。
- 链路箱自动切换命令不单独要求人工确认；涉及人工接线、喇叭/馈源极化切换时必须在 `manual_instruction` 或 `operator_checks` 中声明。

## 2. 顶层结构

```json
{
  "schema_version": "catr-link-config.v1",
  "name": "CATR Chamber Loss Calibration",
  "description": "CATR 暗室路损校准配置",
  "node_catalog": {},
  "path_templates": {},
  "calibration_items": []
}
```

| 字段 | 必填 | 说明 |
|---|---:|---|
| `schema_version` | 是 | 当前建议固定为 `catr-link-config.v1`。 |
| `name` | 是 | 配置名称。 |
| `description` | 否 | 配置说明。 |
| `node_catalog` | 是 | 节点短码到 UI 标签、节点类型、样式角色的映射。 |
| `path_templates` | 否 | 可复用的接线路径节点模板。 |
| `calibration_items` | 是 | 校准项列表。 |

## 3. 节点字典

节点字典用于统一控制 UI 节点图，避免在代码里写死简称展开规则。

```json
{
  "node_catalog": {
    "PORT1": { "label": "网分 PORT1", "kind": "instrument", "style": "vna" },
    "PORT2": { "label": "网分 PORT2", "kind": "instrument", "style": "vna" },
    "AUX-B": { "label": "AUX-B", "kind": "cable", "style": "aux" },
    "CP-V": { "label": "暗室接口板 V", "kind": "panel", "style": "panel" },
    "FEED-V": { "label": "馈源 V", "kind": "feed", "style": "normal" },
    "REFLECTOR": { "label": "反射面", "kind": "space", "style": "normal" },
    "STD-HORN": { "label": "标准增益喇叭", "kind": "reference", "style": "reference" },
    "CP-DUT": { "label": "暗室接口板 DUT", "kind": "panel", "style": "panel" }
  }
}
```

建议保留原始短码作为 key，例如 `PORT1`、`CP-V`、`LB-SA`、`AMP1`。UI 只显示 `label`，命令和结果字段仍使用原始标识。

## 4. 接线路径模板

接线路径应直接定义为节点数组，参考 HTML 报告中的节点图。

```json
{
  "path_templates": {
    "CAL001_V_INTERNAL": {
      "title": "DUT-V 内部链路",
      "routes": [
        {
          "id": "main",
          "nodes": [
            "PORT1",
            "AUX-B",
            "CP-V",
            "FEED-V",
            "REFLECTOR",
            "STD-HORN",
            "CP-DUT",
            "AUX-C",
            "PORT2"
          ]
        }
      ],
      "caption": "测量 DUT-V，闭合路径包含馈源 V、反射面、标准增益喇叭。链路箱不参与。"
    }
  }
}
```

`routes` 支持多条路径，用于一个大步骤包含直通和放大两种路径的展示。每个 route 的 `nodes` 必须引用 `node_catalog` 中的 key；临时节点可直接写完整中文 label，但不建议长期这样做。

## 5. 校准项结构

```json
{
  "id": "LINK-CAL-001",
  "name": "暗室内部链路校准",
  "purpose": "校准暗室 H/V 经馈源、反射面、标准增益喇叭到 DUT 口。",
  "steps": []
}
```

| 字段 | 必填 | 对应代码模型 |
|---|---:|---|
| `id` | 是 | `CalibrationItem.id` |
| `name` | 是 | `CalibrationItem.name` |
| `purpose` | 否 | `CalibrationItem.purpose` |
| `steps` | 是 | `CalibrationItem.steps` |

## 6. 大步骤结构

```json
{
  "id": "CAL001-V",
  "name": "DUT-V 闭合测量",
  "role": "vna_s21",
  "input_port": "PORT1",
  "output_port": "PORT2",
  "manual_instruction": "确认 DUT-V 内部链路接线完成后开始测量。",
  "path_template": "CAL001_V_INTERNAL",
  "route_ids": [],
  "link_commands": [],
  "raw_outputs": ["S21_CH_INT_V_RAW"],
  "final_outputs": ["L_CH_INT_V"],
  "required_inputs": ["L_AUX_B", "L_AUX_C", "G_STD_HORN_V"],
  "notes": "",
  "substeps": []
}
```

| 字段 | 必填 | 说明 |
|---|---:|---|
| `id` | 是 | 大步骤稳定 ID。 |
| `name` | 是 | UI 标题。 |
| `role` | 是 | 当前支持 `manual`、`vna_s21`、`compute`。 |
| `input_port` / `output_port` | 否 | 端口摘要，使用节点 key 或原始端口标识。 |
| `manual_instruction` | 否 | 操作员确认弹窗提示。 |
| `path_template` | 否 | 引用 `path_templates`。 |
| `path` | 否 | 内联路径；与 `path_template` 二选一，优先级高于 `path_template`。 |
| `route_ids` | 否 | 链路服务中的路线 ID。 |
| `link_commands` | 否 | 链路箱原始命令，必须原样保存。 |
| `raw_outputs` | 否 | 原始/追溯输出字段。 |
| `final_outputs` | 否 | 最终路损输出字段。 |
| `required_inputs` | 否 | 本步骤计算依赖。 |
| `notes` | 否 | 补充说明。 |
| `substeps` | 否 | 显式细分步骤。为空时软件可按大步骤生成单个默认小步骤。 |

## 7. 细分步骤结构

细分步骤是 runner 执行、确认和进度更新的最小单位。

```json
{
  "id": "V-THRU",
  "name": "V 极化 VNA 主链路直通",
  "input_port": "LB-VNA1",
  "output_port": "LB-VNA2",
  "manual_instruction": "标准增益喇叭替代 DUT；确认喇叭/馈源极化已手动切到 V。",
  "operator_checks": [
    "确认标准增益喇叭安装完成",
    "确认馈源/喇叭为 V 极化"
  ],
  "path_template": "CAL002_VNA_V_THRU",
  "route_ids": ["DUT_VNA2", "V_VNA1"],
  "link_commands": [
    "CONFigure:LINK DUT, VNA2",
    "CONFigure:LINK V, VNA1"
  ],
  "raw_output": "L_VNA_V",
  "final_output": "L_VNA_FEED_V",
  "required_inputs": ["G_STD_HORN_V", "L_DUT_VNA"],
  "notes": ""
}
```

字段含义与大步骤一致。区别是 `raw_output` / `final_output` 为单值，方便一个小步骤保存一次测量数据。

## 8. 矩阵生成

对于 H/V 极化、直通/AMP1/AMP2 工况，可用 `substep_matrix` 生成细分步骤，减少重复 JSON。

```json
{
  "id": "CAL002-MAIN",
  "name": "VNA 主链路三工况",
  "role": "vna_s21",
  "substep_matrix": {
    "order": ["polarization", "case"],
    "dimensions": {
      "polarization": [
        { "key": "V", "label": "V 极化", "horn_gain": "G_STD_HORN_V" },
        { "key": "H", "label": "H 极化", "horn_gain": "G_STD_HORN_H" }
      ],
      "case": [
        {
          "key": "THRU",
          "label": "VNA 主链路直通",
          "path_template": "CAL002_VNA_{polarization}_THRU",
          "route_ids": ["DUT_VNA2", "{polarization}_VNA1"],
          "link_commands": [
            "CONFigure:LINK DUT, VNA2",
            "CONFigure:LINK {polarization}, VNA1"
          ],
          "raw_output": "L_VNA_{polarization}",
          "final_output": "L_VNA_FEED_{polarization}",
          "required_inputs": ["{horn_gain}", "L_DUT_VNA"]
        }
      ]
    },
    "id_template": "{polarization}-{case}",
    "name_template": "{label:polarization} {label:case}",
    "manual_instruction_template": "标准增益喇叭替代 DUT；确认馈源/喇叭极化已手动切到 {polarization}。"
  }
}
```

生成规则：

- `dimensions` 中的数组顺序就是执行顺序。
- 当前建议极化顺序使用 `["V", "H"]`，以减少现场手动极化切换次数。
- `{polarization}`、`{case}`、`{horn_gain}` 等占位符在生成时替换。
- `substeps` 与 `substep_matrix` 不应同时出现；如同时出现，以显式 `substeps` 为准。

## 9. 最小示例

```json
{
  "schema_version": "catr-link-config.v1",
  "name": "CATR Loss Calibration Minimal Example",
  "node_catalog": {
    "PORT1": { "label": "网分 PORT1", "kind": "instrument", "style": "vna" },
    "PORT2": { "label": "网分 PORT2", "kind": "instrument", "style": "vna" },
    "AUX-B": { "label": "AUX-B", "kind": "cable", "style": "aux" },
    "AUX-C": { "label": "AUX-C", "kind": "cable", "style": "aux" },
    "CP-V": { "label": "暗室接口板 V", "kind": "panel", "style": "panel" },
    "FEED-V": { "label": "馈源 V", "kind": "feed", "style": "normal" },
    "REFLECTOR": { "label": "反射面", "kind": "space", "style": "normal" },
    "STD-HORN": { "label": "标准增益喇叭", "kind": "reference", "style": "reference" },
    "CP-DUT": { "label": "暗室接口板 DUT", "kind": "panel", "style": "panel" }
  },
  "path_templates": {
    "CAL001_V_INTERNAL": {
      "title": "DUT-V 内部链路",
      "routes": [
        {
          "id": "main",
          "nodes": ["PORT1", "AUX-B", "CP-V", "FEED-V", "REFLECTOR", "STD-HORN", "CP-DUT", "AUX-C", "PORT2"]
        }
      ],
      "caption": "测量 DUT-V，闭合路径包含馈源 V、反射面、标准增益喇叭。"
    }
  },
  "calibration_items": [
    {
      "id": "LINK-CAL-001",
      "name": "暗室内部链路校准",
      "purpose": "校准暗室内部 H/V 闭合链路。",
      "steps": [
        {
          "id": "CAL001-V",
          "name": "DUT-V 闭合测量",
          "role": "vna_s21",
          "input_port": "PORT1",
          "output_port": "PORT2",
          "manual_instruction": "确认 DUT-V 内部链路接线完成后开始测量。",
          "path_template": "CAL001_V_INTERNAL",
          "raw_outputs": ["S21_CH_INT_V_RAW"],
          "final_outputs": ["L_CH_INT_V"],
          "required_inputs": ["L_AUX_B", "L_AUX_C", "G_STD_HORN_V"]
        }
      ]
    }
  ]
}
```

## 10. 导入校验规则

- `schema_version` 必须匹配当前软件支持版本。
- `calibration_items[].id`、`steps[].id`、`substeps[].id` 在各自作用域内必须唯一。
- `role` 必须是已支持枚举。
- `path_template` 必须能在 `path_templates` 中找到。
- `path.routes[].nodes[]` 必须能在 `node_catalog` 中找到，除非明确允许内联 label。
- `link_commands` 必须保持原始命令文本，不做中文化。
- `raw_outputs`、`final_outputs`、`required_inputs` 必须保持原始参数名，不做中文化。
- 存在 `substep_matrix` 时，生成后的 `id` 也必须唯一。
- 涉及极化切换的步骤必须包含 `operator_checks` 或在 `manual_instruction` 中明确提示人工确认。

## 11. 后续落地建议

1. 新增 `calibration/config_loader.py`，负责 JSON 读取、校验和生成 `CalibrationCatalog`。
2. 新增 `calibration/config_schema.py` 或 JSON Schema 文件，固化字段约束。
3. UI 优先使用导入配置中的 `path` / `path_template` 绘制节点图。
4. `default_calibration_catalog()` 可逐步改为读取内置 JSON，而不是手写 Python 定义。
5. 保留 Python 定义作为单元测试基准，直到 JSON 导入链路稳定。
