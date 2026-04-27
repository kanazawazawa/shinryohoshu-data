"""デモ用に第1章「基本診療料」のみを抽出して md/demo.md を生成する。

normalize.py との違い:
- 第1章のみ抽出（範囲を絞ってデモで diff を見せやすくする）
- 半角スペースを保持（読みやすさ優先）
- 項番（1, 2, 3.../注1, 注2.../(1)/イロハ）を Markdown の順序付きリスト
  または箇条書きに置換し、原文の項番文字は本文から取り除く
- 句点で 1 文 1 行
- ルビ除去、PDF折り返しの物理改行を段落として連結
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "raw"
DST = ROOT / "md"

KANJI = "\u4E00-\u9FFF"
HIRA = "\u3040-\u309F"
PAGE_MARK = re.compile(r"<!-- page \d+ -->")
HIRAGANA_ONLY = re.compile(rf"^[{HIRA}]{{1,5}}$")

CHAPTER_START = re.compile(r"^第[\d０-９]+章\s*基本診療料")
CHAPTER_NEXT = re.compile(r"^第[\d０-９]+章")

# 構造行（後続と連結しない）
HEADING_RULES = [
    (re.compile(r"^第[\d０-９]+章"), 2),
    (re.compile(r"^第[\d０-９]+部"), 3),
    (re.compile(r"^第[\d０-９]+節"), 4),
    (re.compile(r"^通則$"), 4),
    (re.compile(r"^第[\d０-９]+款"), 5),
    (re.compile(r"^[\uFF21-\uFF3A][\uFF10-\uFF19]{3}"), 6),  # 区分 A000
]

ITEM_HARD = [
    re.compile(r"^[(（][\d１-９]{1,3}[)）]"),
    re.compile(r"^[イロハニホヘトチリヌルヲワカヨタレソツネナラム][\s　]"),
]
ITEM_SOFT = [
    re.compile(r"^注[\s\d１-９]"),
    re.compile(r"^注$"),
    re.compile(r"^[\d１-９]{1,3}\s"),
]


def heading_level(line: str):
    s = line.strip()
    if not s or any(c in s for c in "、。（）"):
        return None
    for pat, lvl in HEADING_RULES:
        if pat.match(s):
            return lvl
    return None


def is_item_hard(line):
    s = line.strip()
    return any(p.match(s) for p in ITEM_HARD)


def is_item_soft(line):
    s = line.strip()
    return any(p.match(s) for p in ITEM_SOFT)


def is_ruby(line, prev):
    s = line.strip()
    if not HIRAGANA_ONLY.fullmatch(s):
        return False
    if not prev:
        return False
    return bool(re.search(rf"[{KANJI}]$", prev.rstrip()))


def slice_chapter1(text: str) -> str:
    """目次以外の本文中の『第１章 基本診療料』〜『第２章』直前を抽出。"""
    lines = text.split("\n")
    starts = [i for i, ln in enumerate(lines) if CHAPTER_START.match(ln.strip())]
    # 1つ目は目次。2つ目が本文先頭
    if len(starts) < 2:
        raise SystemExit("第1章 が見つからない")
    start = starts[1]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if CHAPTER_NEXT.match(s) and not CHAPTER_START.match(s):
            end = i
            break
    return "\n".join(lines[start:end])


def normalize(text: str) -> list[str]:
    """段落配列に変換（連結済み）。各要素は意味的な1段落。"""
    text = PAGE_MARK.sub("", text)
    raw = text.split("\n")

    # ルビ除去
    cleaned: list[str] = []
    for ln in raw:
        ln = ln.rstrip()
        prev = cleaned[-1] if cleaned else ""
        if is_ruby(ln, prev):
            continue
        cleaned.append(ln)

    # 段落連結
    paras: list[tuple[str, str]] = []  # (kind, text) ; kind は h{lvl} / item-{level}-{label} / body
    buf: list[str] = []
    cur_kind = "body"
    cur_label = ""  # 項番ラベル（「注1」「2」「(3)」「イ」など）

    def flush():
        nonlocal buf
        if not buf:
            return
        joined = "".join(s.strip() if i == 0 else s for i, s in enumerate(buf))
        joined = joined.strip()
        cjk = r"\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF00-\uFFEF"
        joined = re.sub(rf"(?<=[{cjk}]) +(?=[{cjk}])", "", joined)
        joined = re.sub(r" {2,}", " ", joined)
        joined = re.sub(r"\u3000{2,}", "\u3000", joined)
        # 句点改行
        joined = re.sub(r"。(?=[^\n」）)】])", "。\n", joined)
        if joined:
            kind = cur_kind if cur_kind == "body" else f"{cur_kind}|{cur_label}"
            paras.append((kind, joined))
        buf = []

    def split_item(s: str):
        """項番を切り出して (level, label, rest) を返す。levelは
        'top'/'sub1'/'sub2'/'note'。マッチしなければ None。"""
        # 注N
        m = re.match(r"^注\s*([\d１-９]{0,2})[\s　]*(.*)$", s, re.DOTALL)
        if m and (m.group(1) or s.startswith("注 ") or s == "注"):
            num = m.group(1).translate(HANSU)
            return ("note", f"注{num}" if num else "注", m.group(2))
        # (N)
        m = re.match(r"^[(（]([\d１-９]{1,3})[)）][\s　]*(.*)$", s, re.DOTALL)
        if m:
            num = m.group(1).translate(HANSU)
            return ("sub1", f"({num})", m.group(2))
        # イロハ
        m = re.match(
            r"^([イロハニホヘトチリヌルヲワカヨタレソツネナラム])[\s　]+(.*)$",
            s,
            re.DOTALL,
        )
        if m:
            return ("sub2", m.group(1), m.group(2))
        # 数字 N (空白必須)
        m = re.match(r"^([\d１-９]{1,3})[\s　]+(.*)$", s, re.DOTALL)
        if m:
            num = m.group(1).translate(HANSU)
            return ("top", num, m.group(2))
        return None

    for ln in cleaned:
        s = ln.strip()
        if not s:
            continue
        lvl = heading_level(ln)
        if lvl is not None:
            flush()
            paras.append((f"h{lvl}", s))
            cur_kind = "body"
            cur_label = ""
            continue
        # まず項番分離を試みる
        item = split_item(s)
        if item is not None:
            level, label, rest = item
            # SOFT (注/数字) は前段落が「。」「N点」で終わるときのみ新段落
            is_soft = level in ("note", "top")
            if not is_soft or (
                not buf
                or buf[-1].rstrip().endswith("。")
                or re.search(r"[0-9０-９]+点$", buf[-1].rstrip())
            ):
                flush()
                cur_kind = f"item-{level}"
                cur_label = label
                buf.append(rest if rest else "")
                continue
            # 連結扱い
            buf.append(s)
            continue
        buf.append(s)
    flush()
    return paras


HANSU = str.maketrans("０１２３４５６７８９", "0123456789")


def to_markdown(paras: list[tuple[str, str]]) -> str:
    """段落配列を Markdown へ。項番は順序付きリストに変換する。
    - top  : `1. ` (Markdown が自動採番)
    - note : `1. **注N** ` (注ラベルは本文に残す)
    - sub1 : `    1. ` （(N)は1段下げ、原番号は捨て自動採番）
    - sub2 : `        - イ ` （イロハは番号付与せず箇条書きでラベル保持）
    """
    out: list[str] = []
    last_was_list = False

    for kind, txt in paras:
        if kind.startswith("h"):
            if out and out[-1] != "":
                out.append("")
            lvl = int(kind[1:])
            out.append("#" * lvl + " " + txt)
            out.append("")
            last_was_list = False
            continue

        if kind.startswith("item-"):
            head, _, label = kind.partition("|")
            level = head[len("item-") :]
            indent = ""
            if level == "top":
                marker = "1. "
                body = txt
            elif level == "note":
                marker = "1. "
                body = f"**{label}** {txt}" if txt else f"**{label}**"
            elif level == "sub1":
                marker = "1. "
                indent = "   "
                body = txt
            elif level == "sub2":
                marker = f"- {label} "
                indent = "      "
                body = txt
            else:
                marker = ""
                body = txt
            sub_lines = body.split("\n")
            for i, sl in enumerate(sub_lines):
                if i == 0:
                    out.append(indent + marker + sl)
                else:
                    out.append(indent + " " * len(marker) + sl)
            last_was_list = True
            continue

        # body
        if last_was_list:
            out.append("")
            last_was_list = False
        for sl in txt.split("\n"):
            out.append(sl)
        out.append("")

    md = "\n".join(out)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"[ \u3000]+\n", "\n", md)
    return md.strip() + "\n"


FRONTMATTER = (
    "---\n"
    "title: 診療報酬の算定方法 別表第一 医科診療報酬点数表 抜粋（第1章 基本診療料）\n"
    "version: {version}\n"
    "source_pdf: {pdf}\n"
    "source_org: 厚生労働省\n"
    "source_url: https://www.mhlw.go.jp/\n"
    "license: 政府著作物（著作権法第13条により著作権の対象外）\n"
    "scope: 第1章 基本診療料 のみ抜粋（デモ用）\n"
    "---\n\n"
)


def main():
    for ver, pdf in [("r6", "001251499.pdf"), ("r8", "001686842.pdf")]:
        # demo は単一ファイル md/demo.md として書き出す（r6/r8 はコミットで切替）
        text = (SRC / f"{ver}.txt").read_text(encoding="utf-8")
        ch1 = slice_chapter1(text)
        paras = normalize(ch1)
        md = FRONTMATTER.format(version=ver, pdf=pdf) + to_markdown(paras)
        out = DST / f"demo-{ver}.md"
        out.write_bytes(md.encode("utf-8"))
        print(f"{ver}: chars={len(md)} lines={md.count(chr(10))}")


if __name__ == "__main__":
    main()
