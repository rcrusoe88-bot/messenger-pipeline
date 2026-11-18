# messenger-pipeline

「信使引擎」公众号推文全流程流水线 Skill。

一次跑完：深度写作（rnascript-wechat）→ 公众号 HTML 排版（wechat-article-html）→ 封面设计（wechat-cover-design）。

## 包含

- `SKILL.md` —— 五阶段调度、人工卡点、交接契约、交付门禁
- `scripts/pipeline_check.py` —— Stage 2 排版门禁

## 安装

把本目录放到 `~/.claude/skills/messenger-pipeline`，或建软链接指向它。

## 依赖

- rnascript-wechat
- wechat-article-html
- wechat-cover-design
