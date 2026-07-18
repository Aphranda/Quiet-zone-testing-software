# HTML 报告截图检查操作指南

Status: Active  
Domain: REPORT  
Canonical: `catr_loss_calibrator/docs/REPORT_SCREENSHOT_CHECK_PLAYBOOK.md`  
Related: `catr_loss_calibrator/docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html`  
Last updated: 2026-07-18

本文总结本项目生成 HTML 报告时的截图检查经验，可复用于 `1120 × 630` PPT 型报告、A4 报告和其他固定画布 HTML 报告。

## 1. 检查目的

截图检查用于发现浏览器真实渲染后的版面问题，尤其是：

- 页面内容是否压到页脚。
- 表格是否超出页面。
- 长文件名、长公式、长命令是否撑破表格。
- 图片是否过大导致页面被撑高。
- 页码是否与页面总数一致。
- 页眉、页脚是否完整显示。
- 打印/导出 PDF 前是否存在分页异常。

模板约束参考：

- 页面固定尺寸，不建议修改 `.page` 的宽度和高度。
- 单页内容不得依赖滚动显示。
- 表格过长时应拆页或压缩字号。
- 生成后必须用浏览器截图检查页面是否溢出。

## 2. 推荐临时文件位置

截图和临时检查 HTML 统一放入：

```text
docs/temp/
```

不要放在 `docs/` 根目录，避免和正式设计文档混在一起。

命名建议：

```text
docs/temp/<报告名>_PAGE_PREVIEW.png
docs/temp/<报告名>_PAGE_CHECK_P23_P25.html
docs/temp/<报告名>_page_23.png
```

示例：

```text
docs/temp/CATR_PAGE_PREVIEW.png
docs/temp/CATR_PAGE_CHECK_P23_P25.html
docs/temp/CATR_page_23.png
```

## 3. Edge Headless 截图基础命令

Windows / PowerShell 示例：

```powershell
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$html = (Resolve-Path 'docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html').Path.Replace('\','/')
$out = (Resolve-Path 'docs/temp').Path + '\CATR_PAGE_PREVIEW.png'
$userData = Join-Path $env:TEMP ('edge-codex-preview-' + [guid]::NewGuid().ToString('N'))

& $edge `
  --headless `
  --disable-gpu `
  --disable-gpu-compositing `
  --disable-software-rasterizer `
  --no-sandbox `
  --no-first-run `
  --disable-extensions `
  --hide-scrollbars `
  --allow-file-access-from-files `
  "--user-data-dir=$userData" `
  --window-size=1200,18000 `
  "--screenshot=$out" `
  "file:///$html"
```

参数说明：

| 参数 | 作用 |
|---|---|
| `--headless` | 无界面运行浏览器 |
| `--disable-gpu` | 避免 GPU 渲染导致失败 |
| `--disable-gpu-compositing` | 避免 GPU 合成异常 |
| `--disable-software-rasterizer` | 避免部分环境下软件光栅化崩溃 |
| `--no-sandbox` | 某些 Windows 环境下提高 headless 稳定性 |
| `--hide-scrollbars` | 截图中隐藏滚动条 |
| `--allow-file-access-from-files` | 允许本地 HTML 读取本地图片 |
| `--user-data-dir` | 使用临时浏览器用户目录，避免占用日常 Edge 配置 |
| `--window-size` | 控制截图视口尺寸 |
| `--screenshot` | 输出 PNG 路径 |

## 4. 常见问题与处理

### 4.1 截图文件没有生成

现象：

- 命令执行结束，但目标 PNG 不存在。
- Edge 输出 GPU、sandbox、Update key 等错误。

处理：

- 加上以下参数：

```text
--disable-gpu
--disable-gpu-compositing
--disable-software-rasterizer
--no-sandbox
```

- 使用独立 `--user-data-dir`。
- 输出路径优先使用英文临时路径，再复制回中文目录。

### 4.2 中文路径或 OneDrive 路径不稳定

处理方式：

1. 先输出到 `$env:TEMP` 下的英文文件名。
2. 截图生成成功后再 `Copy-Item` 到 `docs/temp/`。

示例：

```powershell
$tmp = Join-Path $env:TEMP ('catr_preview_' + [guid]::NewGuid().ToString('N') + '.png')
# Edge --screenshot=$tmp ...
Copy-Item -LiteralPath $tmp -Destination 'docs/temp/CATR_PAGE_PREVIEW.png' -Force
```

### 4.3 超长报告整页截图不完整

长报告一次性截图可能受浏览器或显卡限制，导致：

- 截图高度被截断。
- 超高 `--window-size` 不生成图片。
- 最后几页看不清。

推荐处理：

- 不强行截整份报告。
- 生成局部检查 HTML，只包含需要检查的页面。
- 单独截图局部页面。

## 5. 局部检查 HTML 生成方法

适用于只检查某几页，例如 P23–P25。

Python 示例：

```python
from pathlib import Path
import re

src = Path("docs/CATR_CHAMBER_CALIBRATION_TEST_PLAN.html").read_text(encoding="utf-8")
head = src.split("<body>")[0] + "<body>\n"

pages = []
for n in [23, 24, 25]:
    m = re.search(
        rf"<!-- P{n} -->\s*(<div class=\"page\">.*?</div>\s*)(?=<!-- P{n+1} -->|\s*</body>)",
        src,
        re.S,
    )
    if m:
        pages.append(f"<!-- P{n} -->\n" + m.group(1))

out = head + "\n".join(pages) + "\n</body></html>\n"
Path("docs/temp/CATR_PAGE_CHECK_P23_P25.html").write_text(out, encoding="utf-8")
```

然后对 `docs/temp/CATR_PAGE_CHECK_P23_P25.html` 执行 Edge 截图。

## 6. 页面裁剪检查方法

如果已经生成整页长图，也可以按页面尺寸裁剪。

对于当前 PPT 型报告：

- 页面宽度：`1120 px`
- 页面高度：`630 px`
- 页面间距：通常约 `24 px`
- 左边距：通常约 `40 px`
- 顶部起始：通常约 `20 px`

Python 裁剪示例：

```python
from PIL import Image
from pathlib import Path

img = Image.open("docs/temp/CATR_PAGE_PREVIEW.png")

page_w = 1120
page_h = 630
gap = 24
left = 40
top0 = 20

for n in [23, 24, 25]:
    top = top0 + (n - 1) * (page_h + gap)
    crop = img.crop((left, top, left + page_w, top + page_h))
    crop.save(Path("docs/temp") / f"CATR_page_{n}.png")
```

注意：

- 如果截图本身没有完整包含所有页面，裁剪结果会错位。
- 对长报告更推荐“局部检查 HTML”方式。

## 7. 检查清单

截图生成后逐页检查：

- [ ] 页眉完整，标题和 Logo 未裁切。
- [ ] 页脚完整，页码未被正文覆盖。
- [ ] 页面内容没有压到页脚。
- [ ] 表格行数不过多，长表格已拆页。
- [ ] 长文件名、长公式、长命令未撑破表格。
- [ ] 图片没有超出页面边界。
- [ ] 页面总数和页脚一致。
- [ ] 临时截图和检查 HTML 已放入 `docs/temp/`。

## 8. 本次 CATR 报告检查经验

本次 `CATR_CHAMBER_CALIBRATION_TEST_PLAN.html` 检查中遇到的问题：

- 原 P23“整机发射/接收与 SA/SG 校准”为重复总结页，信息价值不高，建议删除。
- 原 P24“实际路损文件命名规则”内容偏多，包含短码、交集、示例、CSV 字段和注意事项，单页密度过高。
- 处理方式：
  - 删除重复 P23。
  - 将命名规则拆成两页：
    - P23：命名规则、馈源/喇叭短码、有效频段交集。
    - P24：示例文件名和 CSV 字段。
- Edge headless 在当前环境下需要追加 GPU/sandbox 规避参数，普通命令可能不生成截图。

## 9. 建议固化为脚本

后续可以新增脚本：

```text
scripts/check_html_report_screenshot.py
```

建议功能：

- 输入 HTML 路径。
- 自动创建 `docs/temp/`。
- 调用 Edge headless 截图。
- 支持全报告截图和指定页局部截图。
- 自动按 `.page` 数量校验页码。
- 输出待人工检查的 PNG 路径。
- 可选检测 `.page` 的 `scrollHeight > clientHeight`，自动发现内容溢出。
