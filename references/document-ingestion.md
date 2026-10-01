# 文档入库实操：把 PDF / 网页 / 微信变成干净的 Markdown

知识库的质量上限由 `raw/` 决定。这份文档记录把各类来源转成 **AI 可读的干净 Markdown** 的可靠做法，以及验证「没丢内容、没杜撰内容」的流程。

> 原则：**不要把 PDF / 图片直接丢给 AI**。先转成 Markdown，人工或脚本扫一眼，再放进 `raw/素材/`。

---

## 一、先判断 PDF 类型（决定走哪条路）

```python
import pdfplumber
with pdfplumber.open(path) as pdf:
    for i, page in enumerate(pdf.pages, 1):
        txt = page.extract_text() or ""
        print(f"p{i}: {len(txt)} 字符, 图片 {len(page.images)} 个, 曲线 {len(page.curves)} 条")
```

- **文本型**（每页有几百字符）→ 走第二节，文本层抽取
- **扫描型**（字符数接近 0 但图片数多）→ 走第六节，OCR / MinerU

---

## 二、文本型 PDF：用 pdfplumber，不要用 pypdf

**pypdf 会按自己的阈值往中文里插多余空格**，抽出来是 `开 标 时 间` 这种碎裂文本。pdfplumber 的 `extract_text_lines()` 表现好得多。

```python
# 推荐参数：x_tolerance=5 能消除「2024 年 07 月 26 日」这类碎空格，
# 又不会破坏「甲方：… 乙方：…」这种列间距
lines = page.extract_text_lines(x_tolerance=5, y_tolerance=3)
# 每行返回 {'text', 'x0', 'x1', 'top', 'bottom', 'chars'}
```

**不要自己按 `round(top/3)` 之类的分桶逻辑归并行**——那会把编号从正文里撕出来（`1.4` 和 `60` 被错误合并成 `1.460`）。pdfplumber 原生归并是可靠的。

---

## 三、字符规范化（必做，否则全文检索形同虚设）

中文 PDF 有两个隐蔽陷阱：

### 3.1 康熙部首 / CJK 兼容区字符

PDF 里的 `湖南⾼速`、`项⽬`，用的不是正常汉字，而是**康熙部首字符**（`⾼` 是 U+2FBC，而非 `高` U+9AD8）。这种字在 Obsidian / 检索引擎里**一个字都搜不到**。

处理：单字 NFKC 转换 + 手工映射表。

```python
import unicodedata

# 4 个 NFKC 转不动的（标准化后仍是自身），必须手工映射
MANUAL_RADICAL = {
    "\u2eda": "页",  # ⻚
    "\u2ed3": "长",  # ⻓
    "\u2ea0": "民",  # ⺠
    "\u2ecb": "车",  # ⻋
}

def normalize_char(ch: str) -> str:
    if ch in MANUAL_RADICAL:
        return MANUAL_RADICAL[ch]
    if 0x2E80 <= ord(ch) <= 0x2FDF or 0xF900 <= ord(ch) <= 0xFAFF:
        return unicodedata.normalize("NFKC", ch)
    return ch

# 注意：不要对整串做 NFKC，会把全角标点转成半角
text = "".join(normalize_char(c) for c in text)
```

### 3.2 私用区字符（PUA）

网页图标字体会残留 `\ue646` 这类私用区字符（U+E000–U+F8FF），一律剔除：

```python
text = "".join(c for c in text if not (0xE000 <= ord(c) <= 0xF8FF))
```

---

## 四、段落重排：判据必须是坐标，不是行长

**核心错误**：按「行有多长」判断要不要合并上一行 → 会把签名区的 `采购人：…` / `联系人：…` / `电话：…` 拼成一大坨。

**正确判据**：**该行的右边界是否顶到正文右边界**——顶到了才说明它是折行，需要和下一行合并。

```python
# 正文右边界必须逐份测量，各文件不同
# 实测：某公告正文右边界 683.5pt，而页眉/导航会到 817.9pt
max_x1 = max(l["x1"] for l in page.extract_text_lines())
```

### 多栏行检测

签名区/联系人区的 `地址：… 地址：…` 是**双栏行**，恰好也顶到右边界，会被误判成折行。用「行内最大字符间隙」区分：

```python
chars = line["chars"]
gaps = [chars[i]["x0"] - chars[i-1]["x1"] for i in range(1, len(chars))]
max_gap = max(gaps) if gaps else 0.0
# 实测：双栏行 max_gap ≥ 24（常见 24 / 60 / 132），正文行 ≤ 12
MULTICOL_THRESHOLD = 15.0
```

多栏行**本身不是折行**，它后面那行也不该被当作它的续行。

### 强标点阻断

上一行以 `。！？；` 结尾时不要合并下一行——修复列表项 `a、/b、/c、` 被拼成一行的 bug。

---

## 五、表格：显式指定，别信默认

`page.find_tables()` **误报很多**（常见把带下划线的正文当表格）。做法：

1. 先列出所有候选表，肉眼确认哪些是真的
2. 只对确认的 bbox 调 `extract()`，渲染成 Markdown 表格
3. 用 `page.outside_bbox(table.bbox)` 把表格区域**从正文文字里物理排除**，避免同一内容出现两次
4. 跨页表格要手工合并（表头 + 数据行在两页）

---

## 六、扫描件 / 复杂版式：用 MinerU

**MinerU**（上海人工智能实验室 OpenDataLab 开源）是当前最合适的选择：PDF / 扫描件 / Word / PPT / Excel / 图片 → 干净 Markdown，公式表格识别率高，有 MCP 接口可被 Agent 直接调用。

---

## 七、网页打印件：逐份写清洗规则

网页打印的 PDF 每页都带页眉页脚（`2026/9/30 16:55…`、URL + 页码）和站点导航、ICP 备案号。需要逐文件配置清洗正则。

**坑**：正则要容忍被 pdfplumber 插入的空格。例如 `主办单位：江苏省公共资源交易中心 地址：` 中间有个空格，写得死板的正则会失配，导致页脚没被剔除。用宽松匹配或在清洗前先规范化空白。

---

## 八、校验流程（不可省）

转换完必须验证两件事：**没丢内容**、**没编内容**。

### 8.1 逐行比对，找出真正缺失的行

```python
md_flat = re.sub(r"\s|<br>|\|", "", md_text)
missing = [l for l in pdf_lines if l and re.sub(r"\s", "", l) not in md_flat]
# 再逐条人工判断：缺失的是页眉页脚（正常）还是正文（严重）
```

### 8.2 杜撰检查（最关键的检查）

Markdown 里**不应出现 PDF 原文之外的任何汉字**：

```python
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
invented = Counter(c for c in md_text if CJK.match(c)) - Counter(c for c in pdf_text if CJK.match(c))
# invented 必须是空的
```

### 8.3 统计口径陷阱

做字数比对时**只统计汉字**。把标点、数字、空白也算进分母，会得出「删除了 1634 字」这类假警报，让人误判成内容丢失。

---

## 九、转换件的固定格式

放进 `raw/素材/` 的每份转换件，顶部都要有 provenance 块，便于回溯：

```markdown
> **原始文件**：`xxx.pdf`（1211 KB / 6 页）
> **文件性质**：招标公告网页打印件（开标时间 2025-07-21）
> **来源链接**：https://...
> **转换日期**：2026-10-01　**转换方式**：pdfplumber 文本层抽取（未使用 OCR）
```

底部不要加工结论。**来源页的解读写在 `wiki/来源/` 里，不要在 `raw/` 里做**。
