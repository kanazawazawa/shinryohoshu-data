"""段落再構築型の正規化。

PDF からの抽出は折り返し位置の物理改行が混入し、ルビが本体漢字を分断するため、
- 構造行（章/部/節/款、区分番号、注、番号付き、イロハ番号）以外の連続行を
  1段落として連結する
- そのうえで句点「。」の後で改行（1文1行）する
- ルビ行（直前行末が漢字、ひらがな1-5字）は削除（連結時に消滅）
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "raw"
DST = ROOT / "normalized"
DST.mkdir(exist_ok=True)

KANJI = "\u4E00-\u9FFF"
HIRA = "\u3040-\u309F"

PAGE_MARK = re.compile(r"<!-- page \d+ -->")
HIRAGANA_ONLY = re.compile(rf"^[{HIRA}]{{1,5}}$")

# 単独行として保持する見出し（後続と連結しない）
HEADING_PATTERNS = [
    re.compile(r"^第\s*\d+\s*[章部節款]"),
    re.compile(r"^[\uFF21-\uFF3A][\uFF10-\uFF19]{3}"),  # 区分 A000
    re.compile(r"^通則$"),
    re.compile(r"^別表"),
    re.compile(r"^［[^］]+］$"),
    re.compile(r"^区分$"),
]
# 段落の先頭となる項目行（後続の通常行を連結する）
# SOFT: 前段落が「。」で終わる時のみ新段落（誤検出回避）
ITEM_HEAD_SOFT = [
    re.compile(r"^注[\s\d１-９]"),
    re.compile(r"^注$"),
    re.compile(r"^[\d１-９]{1,3}\s"),
]
# HARD: 無条件で新段落（イロハ・(1)系。本文中に出現しないため安全）
ITEM_HEAD_HARD = [
    re.compile(r"^[(（][\d１-９]{1,3}[)）]"),
    re.compile(r"^[イロハニホヘトチリヌルヲワカヨタレソツネナラムウヰノオクヤマケフコエテアサキユメミシヱヒモセス][\s　]"),
]
ITEM_HEAD_PATTERNS = ITEM_HEAD_SOFT + ITEM_HEAD_HARD


def match_any(line: str, pats) -> bool:
    s = line.strip()
    if not s:
        return False
    return any(p.match(s) for p in pats)


def is_heading(line: str) -> bool:
    s = line.strip()
    # 本文中の 第N節/部 等の参照を除外（句読点・括弧を含むものは見出しでない）
    if any(c in s for c in "、。（）"):
        return False
    return match_any(line, HEADING_PATTERNS)


def is_item_head(line: str) -> bool:
    return match_any(line, ITEM_HEAD_PATTERNS)


def is_hard_item(line: str) -> bool:
    return match_any(line, ITEM_HEAD_HARD)


def is_ruby(line: str, prev_text: str) -> bool:
    s = line.strip()
    if not HIRAGANA_ONLY.fullmatch(s):
        return False
    if not prev_text:
        return False
    return bool(re.search(rf"[{KANJI}]$", prev_text.rstrip()))


def normalize(text: str) -> str:
    text = PAGE_MARK.sub("", text)
    text = text.replace("\u3000", " ")
    raw_lines = text.split("\n")

    # Pass 1: ルビ除去
    cleaned: list[str] = []
    for line in raw_lines:
        line = line.rstrip()
        line = re.sub(r" {2,}", " ", line)
        prev = cleaned[-1] if cleaned else ""
        if is_ruby(line, prev):
            continue
        cleaned.append(line)

    # Pass 2: 段落連結
    out_lines: list[str] = []
    buf: list[str] = []
    pending_heading_continue = False

    def flush():
        if not buf:
            return
        joined = "".join(buf)
        # 先頭末尾の改行のみ除去（リストインデント保護のため空白は触らない）
        joined = joined.strip("\n\r")
        if not joined.strip():
            buf.clear()
            return
        # CJK拡張: ひらがな・カタカナ・漢字 + 全角句読点/括弧 + 全角英数字
        # （PDF両端揃え由来の半角スペースを可能な限り除去し diff ノイズを減らす）
        cjk = r"\u3000-\u303F\u3040-\u30FF\u4E00-\u9FFF\uFF00-\uFFEF"
        # 行頭の Markdown リストプレフィックス "- " / "  - " / "    - " は
        # 構造表現のため保護する。
        m = re.match(r"^( {0,4}- )(.*)$", joined, flags=re.DOTALL)
        if m:
            prefix, rest = m.group(1), m.group(2)
        else:
            prefix, rest = "", joined
        rest = re.sub(rf" +(?=[{cjk}])", "", rest)
        rest = re.sub(rf"(?<=[{cjk}]) +", "", rest)
        joined = prefix + rest
        # 句点で改行（1文1行）。長行を読点で更に分割する処理は行わない
        # （文章が逆に読みづらくなるため）。
        joined = re.sub(r"。(?=[^\n」）)】])", "。\n", joined)
        out_lines.append(joined)
        buf.clear()

    for line in cleaned:
        s = line.strip()
        if not s:
            # 空行は連結を阻害しない（PDF折り返し由来のノイズ空行を吸収）
            continue
        # 見出しの続き（ルビ除去で分断されたケース）を見出し行に追加
        if pending_heading_continue:
            pending_heading_continue = False
            if (
                not is_heading(line)
                and not is_item_head(line)
                and not is_hard_item(line)
                and len(s) <= 20
                and not any(c in s for c in "、。（）")
                and out_lines
            ):
                out_lines[-1] = out_lines[-1].rstrip() + s
                pending_heading_continue = True
                continue
        if is_heading(line):
            flush()
            # 見出しの先頭以外の半角スペースは除去（CJK隣接）
            s = re.sub(r"(?<=[^\x00-\x7F]) +(?=[^\x00-\x7F])", "", s)
            out_lines.append(s)
            pending_heading_continue = True
            continue
        # HARD item は無条件で新段落、SOFT item は前段落が「。」または
        # 「N点」で終わる時のみ（リスト項目末の点数表記の直後の数字項目を
        # 新段落として切り出すため）
        prev = buf[-1].rstrip() if buf else ""
        prev_ok = (
            not buf
            or prev.endswith("。")
            or bool(re.search(r"[0-9０-９]+点$", prev))
        )
        if is_hard_item(line) or (is_item_head(line) and prev_ok):
            flush()
            # 項目番号と本文の区切りを全角スペース1個に固定
            s = re.sub(
                r"^([\d１-９]{1,3}|[(（][\d１-９]{1,3}[)）]|注[\d１-９]?|[イロハニホヘトチリヌルヲワカヨタレソツネナラム])[\s　]*",
                lambda m: m.group(1) + "\u3000",
                s,
            )
            # 階層を表す Markdown リストプレフィックスを付与する
            #  注N / 算用数字N           → トップ        "- "
            #  (N) / （N）              → 1段下げ        "  - "
            #  イロハ...                 → 2段下げ        "    - "
            head = s.lstrip()
            if re.match(r"^[(（][\d１-９]{1,3}[)）]", head):
                prefix = "  - "
            elif re.match(r"^[イロハニホヘトチリヌルヲワカヨタレソツネナラム]\u3000", head):
                prefix = "    - "
            else:
                prefix = "- "
            s = prefix + s
            buf.append(s)
            continue
        buf.append(s)
    flush()

    text = "\n".join(out_lines)
    # 全テキストに対する最終クリーンアップ:
    # PDF抽出のスペースは情報量がなくむしろ R6/R8 間で位置が揺れて diff ノイズの
    # 主要因になる。本文中の半角・全角スペースは一律で除去する。
    # ただし Markdown リストプレフィックス "  - " は構造を表すため保護する。
    cleaned_lines: list[str] = []
    for ln in text.split("\n"):
        m = re.match(r"^( {0,4}- )(.*)$", ln)
        if m:
            prefix, rest = m.group(1), m.group(2)
            rest = re.sub(r"[ \t\u3000]+", "", rest)
            cleaned_lines.append(prefix + rest)
        else:
            cleaned_lines.append(re.sub(r"[ \t\u3000]+", "", ln))
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


for src in ("r6.txt", "r8.txt"):
    raw = (SRC / src).read_text(encoding="utf-8")
    norm = normalize(raw)
    (DST / src).write_text(norm, encoding="utf-8")
    print(f"{src}: {len(raw):>7} -> {len(norm):>7}  lines: {raw.count(chr(10)):>5} -> {norm.count(chr(10)):>5}")
