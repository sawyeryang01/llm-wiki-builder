#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM Wiki 一致性校验（机械性检查部分）。

只做可以确定判断的检查，不涉及「页面之间说法是否矛盾」这类需要人类裁决的问题。

用法:
    python lint_wiki.py <知识库根目录>

检查项:
    1. wiki/ 页面清单
    2. frontmatter 是否存在 / 是否为合法 YAML / 是否含 type 字段
    3. 文件是否带 BOM（带 BOM 会导致 Obsidian 解析不出 frontmatter）
    4. 空链接（[[某页]] 指向尚未建立的页面）
    5. 孤儿页面（没有被任何页面链接）
    6. index.md 的统计数字与实际文件数是否吻合

依赖: 可选 pyyaml（未安装时降级为结构检查，不做 YAML 深度解析）
"""

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LINK = re.compile(r"\[\[([^\]\|#]+)(?:[#\|][^\]]*)?\]\]")
FM = re.compile(r"^---\r?\n(.*?)\r?\n---", re.S)

# 由 index.md 固定链接，不算孤儿
SKIP_ORPHAN = {"综述", "待建概念"}
# 目录 → 统计类别
CATEGORY = {"来源": "来源", "实体": "实体", "概念": "概念", "对比": "对比"}

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def load_pages(wiki: Path):
    """返回 {页面名: 相对路径}"""
    pages = {}
    for p in sorted(wiki.rglob("*.md")):
        pages[p.stem] = p
    return pages


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python lint_wiki.py <知识库根目录>")
        return 2
    root = Path(sys.argv[1]).expanduser().resolve()
    wiki = root / "wiki"
    if not wiki.is_dir():
        print(f"x 找不到 wiki/ 目录: {wiki}")
        return 2

    pages = load_pages(wiki)
    problems = 0

    print("=" * 60)
    print(f"LLM Wiki Lint — {root}")
    print("=" * 60)

    # 1. 清单 + frontmatter + BOM
    print(f"\n[1] 页面清单（{len(pages)} 个）")
    fm_missing, fm_bad, bom_bad = [], [], []
    for name, p in pages.items():
        rel = p.relative_to(root)
        raw = p.read_bytes()
        is_bom = raw[:3] == b"\xef\xbb\xbf"
        if is_bom:
            bom_bad.append(rel)
        txt = raw.decode("utf-8-sig")
        m = FM.match(txt)
        if not m:
            fm_missing.append(rel)
            print(f"    {rel}   <-- 无 frontmatter")
            continue
        note = ""
        if HAS_YAML:
            try:
                d = yaml.safe_load(m.group(1))
                if not isinstance(d, dict) or "type" not in d:
                    fm_bad.append(rel)
                    note = "   <-- frontmatter 缺 type 字段"
            except Exception as e:
                fm_bad.append(rel)
                note = f"   <-- YAML 解析失败: {str(e).splitlines()[0][:50]}"
        print(f"    {rel}{note}")

    # 2. 空链接
    print("\n[2] 空链接（指向未建立的页面）")
    empties = {}
    for name, p in pages.items():
        txt = p.read_text(encoding="utf-8-sig")
        for tgt in set(LINK.findall(txt)):
            t = tgt.strip().split("/")[-1]
            if t not in pages:
                empties.setdefault(t, set()).add(p.stem)
    if empties:
        for t, srcs in sorted(empties.items()):
            print(f"    [[{t}]]  <- {len(srcs)} 处: {', '.join(sorted(srcs))}")
        print("    (约定：空链接必须同时记入 wiki/待建概念.md 排队)")
    else:
        print("    无")

    # 3. 孤儿页面
    print("\n[3] 孤儿页面（没有任何页面链接到它）")
    linked = set()
    for p in pages.values():
        txt = p.read_text(encoding="utf-8-sig")
        for tgt in LINK.findall(txt):
            linked.add(tgt.strip().split("/")[-1])
    orphans = [n for n in pages if n not in linked and n not in SKIP_ORPHAN]
    if orphans:
        for n in sorted(orphans):
            print(f"    {pages[n].relative_to(root)}")
        print("    (摄取后新页面若出现在此列表，说明它没有被整合进知识结构)")
    else:
        print("    无")

    # 4. index.md 统计核对
    print("\n[4] index.md 统计核对")
    idx = root / "index.md"
    actual = {"来源": 0, "实体": 0, "概念": 0, "对比": 0}
    for name, p in pages.items():
        cat = p.parent.name
        if cat in CATEGORY:
            actual[cat] += 1
    print(f"    实际: 来源 {actual['来源']} · 实体 {actual['实体']} · 概念 {actual['概念']} · 对比 {actual['对比']}")
    if idx.is_file():
        t = idx.read_text(encoding="utf-8-sig")
        m = re.search(r"来源\s*(\d+)\s*篇.*?实体\s*(\d+)\s*个.*?概念\s*(\d+)\s*个.*?对比\s*(\d+)\s*篇", t)
        if m:
            claimed = dict(zip(["来源", "实体", "概念", "对比"], map(int, m.groups())))
            drift = {k: (claimed[k], actual[k]) for k in actual if claimed[k] != actual[k]}
            if drift:
                for k, (c, a) in drift.items():
                    print(f"    x {k}: index.md 写 {c}，实际 {a}")
                problems += 1
            else:
                print("    OK index.md 统计与实际情况一致")
        else:
            print("    未找到统计行（格式应为「来源 N 篇 · 实体 N 个 · 概念 N 个 · 对比 N 篇」）")
    else:
        print("    x 缺少 index.md")

    # 汇总
    print("\n" + "=" * 60)
    print("汇总")
    if not HAS_YAML:
        print("  注意: 未安装 pyyaml，frontmatter 只做了结构检查，跳过 YAML 深度解析")
    print(f"  无 frontmatter : {len(fm_missing)}")
    print(f"  frontmatter 异常: {len(fm_bad)}")
    print(f"  带 BOM         : {len(bom_bad)}")
    print(f"  空链接         : {len(empties)}")
    print(f"  孤儿页面       : {len(orphans)}")
    total = len(fm_missing) + len(fm_bad) + len(bom_bad) + len(orphans) + problems
    print(f"  --> 需处理项合计: {total}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
