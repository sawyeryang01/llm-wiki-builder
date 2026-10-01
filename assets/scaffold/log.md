---
type: 日志
title: 操作日志
---

# 操作日志

> 只追加，不修改历史行。
> 每条记录以固定格式开头，方便用命令行快速翻看：
>
> ```bash
> grep "^## \[" log.md | tail -10
> ```
>
> 操作类型固定用：`ingest` / `query` / `lint` / `init` / `schema`

## [{{DATE}}] init | 知识库初始化

- 建立三层结构：`raw/`（只读）· `wiki/`（AI 维护）· `AGENTS.md`（规约）
- 建立四类页面目录：来源 / 实体 / 概念 / 对比
- 建立 `templates/` 页面模板，`index.md` 索引，本日志
- 预置 Obsidian 配置：附件目录 `raw/图片/`、排除 `.workbuddy/` 与 `outputs/`
- 建立 `raw/私有/` 公私分层，已加入 `.gitignore`
- 下一步：把第一批资料放进 `raw/素材/`，让 Agent 执行首次摄取
