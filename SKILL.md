---
name: messenger-pipeline
description: 信使引擎公众号推文全流程流水线：输入论文 PDF、主题关键词或行业新闻，一次跑完「深度写作 → 公众号 HTML 排版 → 封面设计」并交付成品。当用户要求"全流程""一条龙""从论文到封面""跑完整流水线""出一篇带封面的推文"时使用；批量多篇 PDF 同样适用。只写作、只排版或只做封面时不要用本 skill，直接调用 rnascript-wechat / wechat-article-html / wechat-cover-design。
---

# 信使引擎推文流水线

本 skill 是调度层，不重复三个业务 skill 的规则。每个阶段必须完整执行对应 skill 的 SKILL.md，本 skill 只补充：阶段顺序、人工卡点、交接契约、交付门禁。

```text
Stage 0 立案 → Stage 1 写作(rnascript-wechat) → Stage 2 排版门禁
            → Stage 3 封面(wechat-cover-design) → Stage 4 交付
```

## 适用判定

- 适用：一次交付「文章 + 封面」；单篇或批量多篇 PDF。
- 不适用：用户只要文章、只要排版、或只要封面——直接用对应业务 skill。
- 品牌统一为「信使引擎」，任何输出不得出现旧称。

## 目录约定

每篇一个自包含目录；批量时每篇一个子目录，各自独立跑 Stage 2–3。

```text
drafts/<YYYYMMDD>-<slug>/
├── input/                    原始 PDF / 来源材料（从外部复制进来）
├── figures/                  提取图片 + figure_scores.json
├── draft.docx                Word 中间稿
├── <slug>.wechat.html        最终公众号 HTML
├── cover/
│   ├── raw.png               生图原始输出
│   ├── background.png        裁切到 1584x672 的无字底图
│   ├── cover.png             叠字成品
│   └── cover_brief.json      主题、命题、prompt、审计 JSON
└── meta.json                 全流程状态
```

## Stage 0：立案

1. 判定输入类型：`pdf` / `topic` / `news`。
2. 生成 slug：英文小写短横线，不超过 5 个词（如 `acd7-tlnp-editing`）。
3. 建目录，把输入文件复制进 `input/` 并验证路径存在。
4. 选 HTML 主题（三选一，写入 meta）：论文解读 / CMC 工艺 / 深度综述 → `kami`；机制科普 / 产品拆解 → `esther`；教程 / 清单 / SOP → `punk`。用户指定时以用户为准。
5. 写 `meta.json` 初版：

```json
{
  "slug": "",
  "created": "YYYY-MM-DD",
  "input_type": "pdf|topic|news",
  "html_theme": "kami",
  "cover_theme_id": 0,
  "article": { "title": "", "subtitle": "", "tier": "", "word_count": 0 },
  "gates": { "html": "PENDING", "cover": "PENDING" }
}
```

## Stage 1：写作（rnascript-wechat）

完整执行 `rnascript-wechat` 的 Phase 0–4。本流水线追加强制约束：

1. **唯一人工卡点**：Phase 2 结束、动笔前输出「动笔前设计稿」（节奏规划 + 标题备选），停下来等用户确认后才进入 Phase 3。其余阶段自动推进。
   - 批量时合并为**一张总表**（每篇一行：拟定主标题 + 核心主张 + CMC 抓手）一次确认，不逐篇打断。
2. **标题按 [`references/title_naming.md`](references/title_naming.md) 产出**：22–45 字，数据锚点 + 冒号 + 判断，至少一个硬数字。定稿后标题里的数字回原文核对，对不上记 `title_issue`。
3. **选题角度按 [`references/cmc_angles.md`](references/cmc_angles.md) 落到 mRNA / LNP CMC**：处方变量、工艺步骤、分析方法、质量属性、稳定性与放大，至少选一类，并在小节标题里体现。生物学数据后必须跟 CMC 解读。
4. 所有提取图片写入 `figures/`，`figure_scores.json` 一并存放。
5. Phase 4 的 `draft.docx` 与 `<slug>.wechat.html` 直接落盘到篇目目录根；HTML 必须经 `wechat-article-html` 的 `convert.py` 生成（含自动校验），不得手写 HTML。

## 批量处理

2 篇及以上时，每篇独立执行完整 Stage 0–4，互不影响：

1. Stage 0 一次性并发：用脚本复制 PDF、抽全文与图片、降采样到 `figures_web/`，再逐篇写 `meta.json`。
2. Phase 0–2 可并发派子代理，每篇产出 `phase0_2.md` + `figure_scores.json`；要求子代理一次只读 1–2 张图，避免图片过载。
3. 汇总成一张总表等确认（见 Stage 1 第 1 条）。
4. Phase 3 并发写正文，每篇产出 `articles/<slug>_article.md` 与 `_meta.json`；标题以 `tools/final_titles.json` 为准。
5. Stage 2–3 逐篇串行跑门禁与封面，单篇失败不阻塞其他篇。
6. 输出 `summary_index.json`：标题、核心主张、CMC 抓手、字数、图数、门禁状态、失败项。

## Stage 2：排版门禁

```bash
python ~/.claude/skills/messenger-pipeline/scripts/pipeline_check.py \
  --html drafts/<dir>/<slug>.wechat.html \
  --docx drafts/<dir>/draft.docx \
  --theme <kami|esther|punk>
```

退出码非 0 即停，修好后重跑，不得带病进入 Stage 3。检查项：`validate_html.py`、`<style>`/`http(s)://`/`font-family` 归零、`<h2>` 存在、`<thead>`/`<tbody>` 归零、docx 表格数对 `<td>` 的交叉核对、docx 内嵌图片数对 HTML `data:image` 的交叉核对。

通过后把 `gates.html` 写为 `PASS`，`article` 字段按定稿补齐。

## Stage 3：封面（wechat-cover-design，默认直出）

完整执行 `wechat-cover-design` SKILL.md，执行路径固定为 **direct image generation**，不再询问用户。

1. 从定稿文件反查 title inventory（见交接契约），禁止手抄。
2. 按 `references/theme_registry.md` 选 1–13 主题，写入 `cover_theme_id`。
3. 按 `references/theme_specs.md` 写英文 prompt：主体占右侧 60%，左侧 `x=76..620, y=88..585` 留静区，全图无字，附 negative prompt。
4. 生图：`magpie-image` 的 `generate_image`，`size` 用 `16:9`；模型首选 `antigravity/gemini-3.1-flash-image`（gemini flash，出图干净无水印），备选 `cccx/gpt-image-2.5-flare`、`cccx/gpt-image-2`。**禁用** `workbuddy/hunyuan-*`（烧水印）和 `workbuddy-ai/hy-image-3.5`（实测忽略尺寸，只出 256x256）。输出存 `cover/raw.png`。
5. 中心裁切到 `1584x672`，存 `cover/background.png`。
6. 审计，必须返回 `"status": "PASS"`：

```bash
python ~/.claude/skills/wechat-cover-design/scripts/validate_cover.py \
  --input drafts/<dir>/cover/background.png --theme <id> --json
```

失败就重生成底图，最多 2 次；**不得**移动标题去迁就画面。

7. 叠字（不让模型画字）：

```bash
python ~/.claude/skills/wechat-cover-design/scripts/compose_cover.py \
  --input drafts/<dir>/cover/background.png \
  --output drafts/<dir>/cover/cover.png \
  --theme <id> \
  --eyebrow "信使引擎 / <内容类别>" \
  --title "<主标题第一行>" --title-line2 "<第二行，可空>" \
  --subtitle-line1 "<副标题>" --subtitle-line2 "<可空>" \
  --footer ""
```

**footer 必须显式传**：不传会写入默认的「抗体精准定位 · mRNA · 体内生成 CAR-T」，与大多数文章无关；传 `--footer ""` 省略，或按文章内容给一句短的。

8. 两次重生成仍失败：降级交付 prompt-only 包（完整英文 prompt + 叠字规格写入 `cover_brief.json`），并明确标注「非成品」。

## 交接契约（Stage 1 → Stage 3）

全部字段从 `draft.docx` / `<slug>.wechat.html` 反查，不允许凭记忆填写。

| 封面字段 | 来源 | 约束 |
| --- | --- | --- |
| eyebrow | 固定 `信使引擎 / <内容类别>` | 类别 ∈ 论文解读、CMC 工艺、临床证据、机制解析、行业观察 |
| 主标题 1–2 行 | Phase 3 定稿标题，按语义断行 | 每行 ≤500px（62px 字号），默认 62px、最小 52px |
| 副标题 | 导语或摘要首句 | 最多 2 行 |
| 文章命题 | Phase 1 反差角度的一句话 | 只陈述原文结论 |
| 读者收获 | Phase 2 钩子句压缩 | 3 秒可读 |
| 核心对象链 | Phase 0 核心发现 + 材料体系 | 焦点对象、支撑对象、结果 |
| 证据 ≤2 条 | Phase 0 关键数据点 | 具体数字，不用"显著" |

HTML 主题（ kami/esther/punk ）与封面主题（1–13）是两套独立体系，按各自内容信号选，不做联动。

## Stage 4：交付

1. 复跑 Stage 3 审计确认；更新 `meta.json` 的 `gates`。
2. 交付清单：HTML 路径、`cover/cover.png`、定稿标题与摘要、两套主题编号、门禁 JSON。
3. 任一 gate 不是 `PASS`，不得声称完成；降级交付必须写明缺什么。

## 禁止项

- 不修改三个上游 skill 的任何文件；同步冲突时只改本 skill。
- 不跳过 `validate_cover.py`，不以"审计一次过"之类措辞代替 JSON 结果。
- 封面左侧 39% 静区不放任何主体、标签、高对比线条。
- HTML 不允许外链图片、`<style>`、`font-family`。
- 不把 docx 中间稿当默认交付物。
