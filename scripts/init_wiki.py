#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""部署 LLM Wiki 知识库脚手架。

把本 skill 的 assets/scaffold/ 完整复制到目标目录，并将模板中的 {{DATE}}
占位符替换为指定日期（默认取系统当天）。

用法:
    python init_wiki.py <目标目录> [--date YYYY-MM-DD] [--force]

示例:
    python init_wiki.py D:/my-wiki
    python init_wiki.py ./knowledge --date 2026-10-01
"""

import argparse
import datetime
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = SKILL_ROOT / "assets" / "scaffold"
PLACEHOLDER = "{{DATE}}"

# 部署后自检用的关键路径
EXPECTED = [
    "AGENTS.md", "CLAUDE.md", "QWEN.md",
    "README.md", "方法论.md", "操作指令.md",
    "index.md", "log.md", ".gitignore",
    "templates/来源.md", "templates/实体.md", "templates/概念.md", "templates/对比.md",
    "raw/素材", "raw/图片", "raw/归档", "raw/私有",
    "wiki/综述.md", "wiki/待建概念.md",
    "wiki/来源", "wiki/实体", "wiki/概念", "wiki/对比",
]


def main() -> int:
    ap = argparse.ArgumentParser(description="部署 LLM Wiki 知识库脚手架")
    ap.add_argument("target", help="目标目录（将成为知识库根目录）")
    ap.add_argument("--date", default=None, help="写入 frontmatter 的日期，默认取今天")
    ap.add_argument("--force", action="store_true", help="覆盖目标目录中已存在的同名文件")
    args = ap.parse_args()

    if not SCAFFOLD.is_dir():
        print(f"x 找不到脚手架目录: {SCAFFOLD}", file=sys.stderr)
        return 2

    date = args.date or datetime.date.today().isoformat()
    target = Path(args.target).expanduser().resolve()

    print(f"脚手架: {SCAFFOLD}")
    print(f"目标  : {target}")
    print(f"日期  : {date}")
    print()

    # 冲突预检：目标目录里已存在同名文件时，默认不动任何东西
    conflicts = []
    if target.exists():
        for src in SCAFFOLD.rglob("*"):
            if src.is_file():
                rel = src.relative_to(SCAFFOLD)
                if (target / rel).exists():
                    conflicts.append(rel)
    else:
        target.mkdir(parents=True, exist_ok=True)

    if conflicts and not args.force:
        print(f"x 目标目录已有 {len(conflicts)} 个同名文件，未做任何改动：")
        for rel in conflicts[:15]:
            print(f"    {rel}")
        if len(conflicts) > 15:
            print(f"    ... 另有 {len(conflicts) - 15} 个")
        print()
        print("确认要覆盖请加 --force，或换一个空目录。")
        return 1

    shutil.copytree(SCAFFOLD, target, dirs_exist_ok=True)

    # 替换日期占位符（只处理 md，其他文件不含占位符）
    replaced = 0
    for p in target.rglob("*.md"):
        try:
            t = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if PLACEHOLDER in t:
            p.write_text(t.replace(PLACEHOLDER, date), encoding="utf-8")
            replaced += 1

    missing = [e for e in EXPECTED if not (target / e).exists()]

    print(f"OK 脚手架已部署，{replaced} 个文件写入了日期 {date}")
    if missing:
        print("x 以下关键路径缺失:")
        for e in missing:
            print(f"    {e}")
        return 3
    print(f"OK 关键路径自检通过（{len(EXPECTED)} 项）")
    print()
    print("下一步:")
    print("  1. 用 Obsidian「打开文件夹作为仓库」打开该目录，把图谱视图固定到侧边栏")
    print("  2. 把 AGENTS.md 交给 Agent，让它先复述规则再动手")
    print("  3. 填写 wiki/综述.md 的「当前主攻方向」（主题边界）")
    print("  4. 丢一篇资料进 raw/素材/，然后说「按 AGENTS.md 执行摄取」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
