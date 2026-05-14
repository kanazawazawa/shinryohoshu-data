"""共通の正規化処理。

旧 archive/old-md-pdf-conversion/scripts/normalize.py のロジックを移植。
PDF抽出由来の物理改行・ルビ・両端揃えスペースを除去し、段落構造を再構築する。
"""
from __future__ import annotations
import re

KANJI = "\u4E00-\u9FFF"
HIRA = "\u3040-\u309F"

PAGE_MARK = re.compile(r"<!-- page \d+ -->")
HIRAGANA_ONLY = re.compile(rf"^[{HIRA}]{{1,5}}$")

HEADING_PATTERNS = [
    re.compile(r"^第\s*\d+\s*[章部節款]"),
    re.compile(r"^[\uFF21-\uFF3A][\uFF10-\uFF19]{3}"),
    re.compile(r"^通則$"),
    re.compile(r"^別表"),
    re.compile(r"^［[^］]+］$"),
    re.compile(r"^区分$"),
]
ITEM_HEAD_SOFT = [
    re.compile(r"^注[\s\d１-９]"),
    re.compile(r"^注$"),
    re.compile(r"^[\d１-９]{1,3}\s"),
]
ITEM_HEAD_HARD = [
    re.compile(r"^[(（][\d１-９]{1,3}[)）]"),
    re.compile(
        r"^[イロハニホヘトチリヌルヲワカヨタレソツネナラムウヰノオクヤマケフコエテアサキユメミシヱヒモセス][\s　]"
    ),
]
ITEM_HEAD_PATTERNS = ITEM_HEAD_SOFT + ITEM_HEAD_HARD


def _match_any(line: str, pats) -> bool:
    s = line.strip()
    if not s:
        return False
    return any(p.match(s) for p in pats)


def _is_heading(line: str) -> bool:
    s = line.strip()
    if any(c in s for c in "、。（）"):
        return False
    return _match_any(line, HEADING_PATTERNS)


def _is_item_head(line: str) -> bool:
    return _match_any(line, ITEM_HEAD_PATTERNS)


def _is_hard_item(line: str) -> bool:
    return _match_any(line, ITEM_HEAD_HARD)


def _is_ruby(line: str, prev_text: str) -> bool:
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

    cleaned: list[str] = []
    for line in raw_lines:
        line = line.rstrip()
        line = re.sub(r" {2,}", " ", line)
        prev = cleaned[-1] if cleaned else ""
        if _is_ruby(line, prev):
            continue
        cleaned.append(line)

    out_lines: list[str] = []
    buf: list[str] = []
    pending_heading_continue = False

    def flush():
        if not buf:
            return
        joined = "".join(buf)
        joined = joined.strip("\n\r")
        if not joined.strip():
            buf.clear()
            return
        cjk = r"\u3000-\u303F\u3040-\u30FF\u4E00-\u9FFF\uFF00-\uFFEF"
        m = re.match(r"^( {0,4}- )(.*)$", joined, flags=re.DOTALL)
        if m:
            prefix, rest = m.group(1), m.group(2)
        else:
            prefix, rest = "", joined
        rest = re.sub(rf" +(?=[{cjk}])", "", rest)
        rest = re.sub(rf"(?<=[{cjk}]) +", "", rest)
        joined = prefix + rest
        joined = re.sub(r"。(?=[^\n」）)】])", "。\n", joined)
        out_lines.append(joined)
        buf.clear()

    for line in cleaned:
        s = line.strip()
        if not s:
            continue
        if pending_heading_continue:
            pending_heading_continue = False
            if (
                not _is_heading(line)
                and not _is_item_head(line)
                and not _is_hard_item(line)
                and len(s) <= 20
                and not any(c in s for c in "、。（）")
                and out_lines
            ):
                out_lines[-1] = out_lines[-1].rstrip() + s
                pending_heading_continue = True
                continue
        if _is_heading(line):
            flush()
            s = re.sub(r"(?<=[^\x00-\x7F]) +(?=[^\x00-\x7F])", "", s)
            out_lines.append(s)
            pending_heading_continue = True
            continue
        prev = buf[-1].rstrip() if buf else ""
        prev_ok = (
            not buf
            or prev.endswith("。")
            or bool(re.search(r"[0-9０-９]+点$", prev))
        )
        if _is_hard_item(line) or (_is_item_head(line) and prev_ok):
            flush()
            s = re.sub(
                r"^([\d１-９]{1,3}|[(（][\d１-９]{1,3}[)）]|注[\d１-９]?|"
                r"[イロハニホヘトチリヌルヲワカヨタレソツネナラム])[\s　]*",
                lambda m: m.group(1) + "\u3000",
                s,
            )
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


# 全角→半角の数字変換（点数比較・抽出用）
_ZEN2HAN = str.maketrans("０１２３４５６７８９", "0123456789")


def zen2han_digits(s: str) -> str:
    return s.translate(_ZEN2HAN)


def to_int_points(s: str) -> int | str | None:
    """'291点' / '２９１点' / '1,312点' を int 化。失敗時は文字列を返す。"""
    if s is None:
        return None
    s2 = zen2han_digits(s).strip()
    m = re.fullmatch(r"([0-9,]+)\s*点", s2)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            return s
    return s
