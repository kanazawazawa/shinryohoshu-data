"""T1: 正規化済テキスト → 全区分インデックス YAML

入力: data/<ver>/raw/full.txt
出力: data/<ver>/index.yaml
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from common import to_int_points, zen2han_digits, version_dir  # noqa: E402

VERSIONS = ["r6", "r8"]

# 区分番号: Ａ０００ / Ｂ００１－２ 形式 (正規化後はスペースなし)
# 例: 「Ａ０００初診料291点」「Ｂ００１－２ニコチン依存症管理料(略)」「Ａ１０７削除」
CODE_RE = re.compile(
    r"^(?P<letter>[\uFF21-\uFF3A])(?P<digits>[\uFF10-\uFF19]{3})"
    r"(?:[－ー\-](?P<branch>[\uFF10-\uFF19]+))?"
    r"[\s　]*(?P<rest>.*?)[\s　]*(?P<pts>[\d０-９,，]+[\s　]*点)?\s*$"
)
POINTS_AT_END_RE = re.compile(r"([\d０-９,，]+)[\s　]*点\s*$")
CHAP_RE = re.compile(r"^第([\d１-９]+)章[\s　]*(.*)$")
PART_RE = re.compile(r"^第([\d１-９]+)部[\s　]*(.*)$")
SECT_RE = re.compile(r"^第([\d１-９]+)節[\s　]*(.*)$")
SUBSECT_RE = re.compile(r"^第([\d１-９]+)款[\s　]*(.*)$")
POINTS_RE = re.compile(r"^([\d０-９,，]+)[\s　]*点$")

# 区分行に複数の区分番号が含まれていないか（本文行の誤検出を防ぐ）
MULTI_CODE_RE = re.compile(
    r"[\uFF21-\uFF3A][\uFF10-\uFF19]{3}(?:[－ー\-][\uFF10-\uFF19]+)?"
)
# 「Ａ２１５ からＡ２１７まで削除」を検出
RANGE_DELETE_RE = re.compile(
    r"^(?P<a>[\uFF21-\uFF3A][\uFF10-\uFF19]{3})(?:から(?P<b>[\uFF21-\uFF3A][\uFF10-\uFF19]{3})まで)?\s*削除\s*$"
)
# 名称が助詞・接続詞で始まる = 本文行の誤検出
BAD_NAME_PREFIX = (
    "に", "を", "は", "が", "と", "の", "で", "へ", "及び", "又は", "若しくは",
    "から", "まで", "並びに", "または", "及", "或いは", "において", "について",
    "に係る", "に掲げ", "に規定", "として", "により", "による", "に対し",
)

# 章名の参照（本文中の「第１章」など）と見出しを区別: 句読点を含むなら本文
def _is_heading_line(s: str) -> bool:
    return not any(c in s for c in "、。（）")


def _is_valid_code_line(line: str, name: str, points, has_pts: bool) -> tuple[bool, str]:
    """区分行として妥当か判定する。NG なら理由文字列を返す。"""
    # 1行に複数の区分番号がある = 本文行に取り込まれた疑い
    codes = MULTI_CODE_RE.findall(line)
    if len(codes) >= 2:
        return False, f"multi-code:{len(codes)}"
    # 名称が助詞・接続詞で始まる = 本文の途中
    if name and name not in ("削除", "(名称取得失敗)"):
        for bp in BAD_NAME_PREFIX:
            if name.startswith(bp):
                return False, f"name-starts-with:{bp}"
    # 名称取得失敗 + 点数も無し + 削除でもない = ノイズ
    if name == "(名称取得失敗)" and not has_pts:
        return False, "no-name-no-points"
    # 名称が極端に長い (50字超) で末尾に点数も無い = 本文連結
    if name and len(name) > 50 and not has_pts:
        return False, f"name-too-long:{len(name)}"
    return True, ""


PDF_BY_VER = {
    "r6": ("001251499.pdf", "https://www.mhlw.go.jp/"),
    "r8": ("001686842.pdf", "https://www.mhlw.go.jp/"),
}


def _zhalpha(c: str) -> str:
    # Ａ-Ｚ → A-Z
    if "\uFF21" <= c <= "\uFF3A":
        return chr(ord(c) - 0xFEE0)
    return c


def normalize_code(letter: str, digits: str, branch: str | None) -> str:
    code = _zhalpha(letter) + digits.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if branch:
        code += "-" + branch.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return code


def find_raw_file(ver: str, chap: int, part: int, sect: int) -> str:
    """index と raw/ ファイルとの紐付け。実存ファイルを探索。"""
    raw_dir = version_dir(ver) / "raw"
    # 完全一致 (chap-part-sect)
    pat = f"{chap:02d}-{part:02d}-{sect:02d}-*.txt"
    hits = sorted(raw_dir.glob(pat))
    if hits:
        return f"raw/{hits[0].name}"
    # 部だけ
    pat = f"{chap:02d}-{part:02d}-00-*.txt"
    hits = sorted(raw_dir.glob(pat))
    if hits:
        return f"raw/{hits[0].name}"
    # 章だけ
    pat = f"{chap:02d}-00-00-*.txt"
    hits = sorted(raw_dir.glob(pat))
    if hits:
        return f"raw/{hits[0].name}"
    return "raw/full.txt"


def extract_index(ver: str) -> dict:
    full_path = version_dir(ver) / "raw" / "full.txt"
    text = full_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    chap = part = sect = subsect = 0
    chap_n = part_n = sect_n = subsect_n = ""
    items: list[dict] = []
    seen: set[str] = set()
    rejected: list[dict] = []

    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        m = CHAP_RE.match(ln)
        if m and _is_heading_line(ln):
            chap = int(zen2han_digits(m.group(1)))
            chap_n = m.group(2).strip()
            part = sect = subsect = 0
            part_n = sect_n = subsect_n = ""
            i += 1
            continue
        m = PART_RE.match(ln)
        if m and _is_heading_line(ln):
            part = int(zen2han_digits(m.group(1)))
            part_n = m.group(2).strip()
            sect = subsect = 0
            sect_n = subsect_n = ""
            i += 1
            continue
        m = SECT_RE.match(ln)
        if m and _is_heading_line(ln):
            sect = int(zen2han_digits(m.group(1)))
            sect_n = m.group(2).strip()
            subsect = 0
            subsect_n = ""
            i += 1
            continue
        m = SUBSECT_RE.match(ln)
        if m and _is_heading_line(ln):
            subsect = int(zen2han_digits(m.group(1)))
            subsect_n = m.group(2).strip()
            i += 1
            continue
        m = CODE_RE.match(ln)
        if m:
            code = normalize_code(m.group("letter"), m.group("digits"), m.group("branch"))
            rest = (m.group("rest") or "").strip()
            pts_str = (m.group("pts") or "").strip()
            # 「Ａ２１５ からＡ２１７まで削除」のような範囲削除を展開
            rd = RANGE_DELETE_RE.match(ln)
            if rd:
                a = rd.group("a")
                b = rd.group("b") or a
                a_code = normalize_code(a[0], a[1:], None)
                b_code = normalize_code(b[0], b[1:], None)
                # 同レターを前提
                if a_code[0] == b_code[0]:
                    a_n = int(a_code[1:])
                    b_n = int(b_code[1:])
                    range_codes = [
                        f"{a_code[0]}{n:03d}" for n in range(a_n, b_n + 1)
                    ]
                else:
                    range_codes = [a_code]
                for rc in range_codes:
                    if rc in seen:
                        continue
                    seen.add(rc)
                    chap_obj: dict[str, str] = {}
                    if chap:
                        chap_obj["chapter"] = f"第{chap}章 {chap_n}".strip()
                    if part:
                        chap_obj["part"] = f"第{part}部 {part_n}".strip()
                    if sect:
                        chap_obj["section"] = f"第{sect}節 {sect_n}".strip()
                    if subsect:
                        chap_obj["subsection"] = f"第{subsect}款 {subsect_n}".strip()
                    items.append({
                        "code": rc, "name": "削除", "points": None,
                        "chapter": chap_obj or {"chapter": "(unclassified)"},
                        "raw_file": find_raw_file(ver, chap, part, sect),
                    })
                i += 1
                continue
            # 「削除」のみの行: 名称扱い、点数 None
            if rest == "削除":
                name = "削除"
                points: int | str | None = None
            else:
                name = rest or "(名称取得失敗)"
                points = to_int_points(pts_str) if pts_str else None
            # 同一区分の重複検出（複数回出現する場合がある: 削除告知や別表参照）
            if code in seen:
                i += 1
                continue
            # 直後の行が「N点」だけなら所定点数として拾う (区分行に点数が無かった場合)
            if points is None:
                for look in range(i + 1, min(i + 4, len(lines))):
                    cand = lines[look].strip()
                    if not cand:
                        continue
                    pm = POINTS_RE.match(cand)
                    if pm:
                        points = to_int_points(cand)
                        break
                    if cand.startswith("注") or CODE_RE.match(cand):
                        break
                    if cand == "削除":
                        break
            # 妥当性チェック (B: 偽区分フィルタ)
            ok, reason = _is_valid_code_line(ln, name, points, bool(pts_str) or points is not None)
            if not ok:
                rejected.append({"code": code, "line": ln[:80], "reason": reason})
                i += 1
                continue
            seen.add(code)
            chap_obj = {}
            if chap:
                chap_obj["chapter"] = f"第{chap}章 {chap_n}".strip()
            if part:
                chap_obj["part"] = f"第{part}部 {part_n}".strip()
            if sect:
                chap_obj["section"] = f"第{sect}節 {sect_n}".strip()
            if subsect:
                chap_obj["subsection"] = f"第{subsect}款 {subsect_n}".strip()
            items.append(
                {
                    "code": code,
                    "name": name,
                    "points": points,
                    "chapter": chap_obj or {"chapter": "(unclassified)"},
                    "raw_file": find_raw_file(ver, chap, part, sect),
                }
            )
        i += 1

    pdf, url = PDF_BY_VER[ver]
    n_total = len(items)
    n_deleted = sum(1 for it in items if it["name"] == "削除")
    n_no_pts = sum(1 for it in items if it["points"] is None and it["name"] != "削除")
    return {
        "version": ver,
        "source": {"pdf": pdf, "url": url},
        "_stats": {
            "total": n_total,
            "deleted": n_deleted,
            "without_points": n_no_pts,
            "rejected_lines": len(rejected),
        },
        "items": items,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=VERSIONS)
    args = ap.parse_args()
    targets = [args.version] if args.version else VERSIONS
    for ver in targets:
        idx = extract_index(ver)
        out = version_dir(ver) / "index.yaml"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            yaml.safe_dump(idx, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print(f"[{ver}] {len(idx['items'])} items -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
