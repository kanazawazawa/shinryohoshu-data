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
    (re.compile(r"^[\uFF21-\uFF3A][\uFF10-\uFF19]{3}"), 5),  # 区分 A000 → h5
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
    """『第１章 基本診療料』本文先頭〜『第２部 入院料等』直前を抽出（= 第１部 初・再診料）。"""
    lines = text.split("\n")
    starts = [i for i, ln in enumerate(lines) if CHAPTER_START.match(ln.strip())]
    if len(starts) < 2:
        raise SystemExit("第1章 が見つからない")
    start = starts[1]
    end = len(lines)
    part2 = re.compile(r"^第[\d０-９]+部\s*入院料等")
    for i in range(start + 1, len(lines)):
        if part2.match(lines[i].strip()):
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

    # 単独「N点」「削除」行は tariff（料金）として後付けで処理するため、
    # 段落連結のフェーズではフラグだけ立てておく。
    TARIFF_RE = re.compile(r"^[\d,]+点$")

    for ln in cleaned:
        s = ln.strip()
        if not s:
            continue
        if s == "区分":
            # PDF のラベル「区分」見出し行は捨てる（テーブル化で代替）
            flush()
            continue
        lvl = heading_level(ln)
        if lvl is not None:
            flush()
            paras.append((f"h{lvl}", s))
            cur_kind = "body"
            cur_label = ""
            continue
        # 単独行の点数 / 削除
        if TARIFF_RE.fullmatch(s) or s == "削除":
            flush()
            paras.append(("tariff", s))
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
    """整形ルール:
    - 区分 (h5) の直後の tariff は見出し並記 ` — 291点`
    - 節 (h4) 配下の各区分を集めて、節見出しの直後に区分一覧テーブルを挿入
    - 区分配下の top 数字項目は「注N」連番として強制ラベル付与（注1のみ明記、以降は数字省略の慣例を補完）
    - sub1=(N), sub2=イロハ
    """
    # --- 1) 区分見出しに点数を結合 + h4(節) ごとに区分一覧を準備 ---
    enriched: list[tuple[str, str]] = []
    section_tables: dict[int, list[tuple[str, str, str]]] = {}  # paras index -> rows
    last_section_idx: int | None = None
    last_section_pos: int | None = None  # in enriched
    pending_division = None  # (idx_in_enriched, code, name)

    i = 0
    while i < len(paras):
        kind, txt = paras[i]
        if kind == "h4":
            enriched.append((kind, txt))
            last_section_idx = len(enriched) - 1
            section_tables.setdefault(last_section_idx, [])
            i += 1
            continue
        if kind == "h5":
            # 区分: 「Ａ０００ 初診料」を分離
            m = re.match(r"^([\uFF21-\uFF3A][\uFF10-\uFF19]{3})[\s　]*(.*)$", txt)
            if m:
                code, name = m.group(1), m.group(2)
                # 直後の tariff を結合
                tariff = ""
                j = i + 1
                while j < len(paras) and paras[j][0] == "tariff":
                    tariff = paras[j][1]
                    j += 1
                heading = f"##### {code} {name}" + (f" — {tariff}" if tariff else "")
                enriched.append(("hraw", heading))
                if last_section_idx is not None:
                    section_tables[last_section_idx].append((code, name, tariff or "—"))
                i = j
                continue
        enriched.append((kind, txt))
        i += 1

    # --- 2) 節テーブルを enriched に挿入 ---
    # 節 hraw が処理されるタイミングで、その節の区分テーブルを直後に出す
    out: list[str] = []
    last_was_list = False

    def emit_blank():
        nonlocal last_was_list
        if out and out[-1] != "":
            out.append("")
        last_was_list = False

    # 節 index を再計算（enriched 上で）
    sec_indices: list[int] = [k for k, (kk, _) in enumerate(enriched) if kk == "h4"]
    sec_tables: dict[int, list[tuple[str, str, str]]] = {}
    # 元の paras index → enriched index の対応取得が面倒なので作り直し
    cur_sec = None
    cur_sec_rows: list[tuple[str, str, str]] = []
    for k, (kk, vv) in enumerate(enriched):
        if kk == "h4":
            if cur_sec is not None:
                sec_tables[cur_sec] = cur_sec_rows
            cur_sec = k
            cur_sec_rows = []
        elif kk == "hraw" and vv.startswith("##### "):
            m = re.match(r"^##### ([\uFF21-\uFF3A][\uFF10-\uFF19]{3}) (\S+)(?: — (.+))?$", vv)
            if m and cur_sec is not None:
                cur_sec_rows.append((m.group(1), m.group(2), m.group(3) or "—"))
    if cur_sec is not None:
        sec_tables[cur_sec] = cur_sec_rows

    for k, (kind, txt) in enumerate(enriched):
        if kind == "h4":
            emit_blank()
            out.append("#### " + txt)
            out.append("")
            rows = sec_tables.get(k, [])
            if rows:
                out.append("| 区分 | 名称 | 点数 |")
                out.append("|---|---|---|")
                for code, name, tariff in rows:
                    out.append(f"| {code} | {name} | {tariff} |")
                out.append("")
            continue

        if kind == "hraw":
            emit_blank()
            out.append(txt)
            out.append("")
            continue

        if kind.startswith("h"):
            emit_blank()
            lvl = int(kind[1:])
            out.append("#" * lvl + " " + txt)
            out.append("")
            continue

        if kind == "tariff":
            # 区分以外（節通則など）に出る tariff はそのまま太字で
            emit_blank()
            out.append(f"**{txt}**")
            out.append("")
            continue

        if kind.startswith("item-"):
            head, _, label = kind.partition("|")
            level = head[len("item-") :]
            indent = ""
            if level == "top":
                marker = "1. "
                body = txt
            elif level == "note":
                # 原文に明示された「注N」のみ表示。自動採番はしない
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
            for n, sl in enumerate(sub_lines):
                if n == 0:
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
    "title: 診療報酬の算定方法 別表第一 医科診療報酬点数表 抜粋（第1章 第1部 初・再診料）\n"
    "version: {version}\n"
    "source_pdf: {pdf}\n"
    "source_org: 厚生労働省\n"
    "source_url: https://www.mhlw.go.jp/\n"
    "license: 政府著作物（著作権法第13条により著作権の対象外）\n"
    "scope: 第1章 第1部 初・再診料 のみ抜粋（デモ用）\n"
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
