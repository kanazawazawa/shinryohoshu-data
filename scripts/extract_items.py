"""T2: index.yaml + raw/ → 各区分の構造化 YAML

各区分について、原文(raw_text) を必ず保持しつつ、
注の分割と加算 (X加算として N点) のルール抽出を試みる。
未パースな箇所があった場合は ``_meta.has_unparsed: true`` を付与する。
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
from common import to_int_points, zen2han_digits  # noqa: E402
from extract_index import (  # noqa: E402
    CODE_RE, normalize_code, PDF_BY_VER,
    CHAP_RE, PART_RE, SECT_RE, SUBSECT_RE, _is_heading_line,
)

VERSIONS = ["r6", "r8"]

# 注の見出し検出: "- 注N本文" / "- 注 本文" / "- 注１　本文" などを全部受ける
NOTE_PREFIX = re.compile(r"^-\s*注([\d１-９]*)[\u3000\s]*(.*)$")
# 注の連番 (- 2 本文 / - 2 本文)
ITEM_PREFIX = re.compile(r"^-\s*([\d１-９]+)[\u3000\s]*(.*)$")

# 加算抽出パターン: 「○○加算として、N点を所定点数に加算」 / 「として」が無いケースもある
ADD_PATTERNS = [
    re.compile(r"([^\s、。（）()]+加算)として[、,]?[^。]*?([\d０-９,，]+)[\s　]*点"),
    re.compile(r"([^\s、。（）()]+加算)\s*([\d０-９,，]+)[\s　]*点"),
]# 逆引き: 「N点を…加算する」末尾→直近の「○○加算」名を遡って拾う
REV_ADD_RE = re.compile(r"([\d０-９,，]+)[\s　]*点[^。]*?(?:を|として)[^。]*?加算")
NAME_BEFORE_ADD_RE = re.compile(r"([一-龠ァ-ヶーＡ-Ｚ々a-zA-Z\d０-９・]+加算)")# 算定上限の検出: 「月N回に限り」「年N回に限り」「N回に限り」「N回を限度」
LIMIT_PATTERN = re.compile(
    r"((?:月|週|年|一連|入院中)?[\d１-９]+回[^。]*?)(?:に限り|まで|を限度)"
)
# unit 推定: 「Ａ＿＿＿名称（１日につき）」「Ｂ＿＿＿名称（一連につき）」など
UNIT_RE = re.compile(r"[（(]\s*([^（）()]*?)につき\s*[）)]")


def slice_item_block(full_text: str, code: str, names_to_codes: dict[str, str]) -> str:
    """正規化済テキストから当該区分のブロック (区分行〜次の区分行直前) を切り出す。"""
    lines = full_text.split("\n")
    target_letter = "Ａ-Ｚ"  # 全角A-Z
    code_letter = code[0]
    code_num = code[1:]  # 例 "001-2"
    # 全角に戻す
    z_letter = chr(ord(code_letter) + 0xFEE0)
    # 数字部分: 001 のみ vs 001-2 を区別。
    base_num = code_num.split("-")[0]
    branch = code_num.split("-")[1] if "-" in code_num else None
    z_base = base_num.translate(str.maketrans("0123456789", "０１２３４５６７８９"))
    if branch:
        z_branch = branch.translate(str.maketrans("0123456789", "０１２３４５６７８９"))
        # 正規化後はスペースなしで連結されるため [\s　]? とする
        head_pat = re.compile(rf"^{z_letter}{z_base}[－ー\-]{z_branch}(?![\uFF10-\uFF19])")
    else:
        head_pat = re.compile(rf"^{z_letter}{z_base}(?![\uFF10-\uFF19－ー\-])")
    start = -1
    for i, ln in enumerate(lines):
        if head_pat.match(ln.strip()):
            start = i
            break
    if start < 0:
        return ""
    # 終わり: 次の区分行 または 章/部/節/款見出し行 または 「区分」/「通則」/「别表」
    end = len(lines)
    for j in range(start + 1, len(lines)):
        s = lines[j].strip()
        if CODE_RE.match(s):
            end = j
            break
        if s in ("区分", "通則") or s.startswith("別表"):
            end = j
            break
        for hpat in (CHAP_RE, PART_RE, SECT_RE, SUBSECT_RE):
            if hpat.match(s) and _is_heading_line(s):
                end = j
                break
        if end == j:
            break
    return "\n".join(lines[start:end]).rstrip() + "\n"


def split_notes(block: str) -> list[dict]:
    """ブロックから注の配列を抽出する。

    旧 normalize 出力では「- 注 本文」「- 1 本文」がトップレベル箇条書き。
    "- 注 本文" 直後の "- 1 本文", "- 2 本文"... が同じ「注」の連番として扱われる。
    本文中で次に出てくる "- 注" でリセット。
    """
    lines = block.split("\n")
    notes: list[dict] = []
    current_idx = 0
    current: dict | None = None
    saw_note_marker = False

    def emit(n):
        if n is not None:
            notes.append(n)

    for ln in lines:
        m = NOTE_PREFIX.match(ln)
        if m:
            saw_note_marker = True
            emit(current)
            num = m.group(1)
            current_idx = int(zen2han_digits(num)) if num else 1
            current = {"id": f"注{current_idx}", "text": m.group(2).strip()}
            continue
        m = ITEM_PREFIX.match(ln)
        if m and saw_note_marker:
            raw_num = zen2han_digits(m.group(1))
            rest = m.group(2)
            # 期待値: current_idx + 1 (連番)。貪欲に取った数字から先頭一致を切り出す
            expected = current_idx + 1
            exp_str = str(expected)
            if raw_num.startswith(exp_str):
                taken = exp_str
                rest = raw_num[len(exp_str):] + rest
            else:
                # 期待外: 最初の1桁だけ採用 (誤検出を避ける)
                taken = raw_num[0]
                rest = raw_num[1:] + rest
            emit(current)
            current_idx = int(taken)
            current = {"id": f"注{current_idx}", "text": rest.strip()}
            continue
        if current is not None:
            current["text"] += "\n" + ln
    emit(current)
    return notes


def extract_additions(text: str) -> list[dict]:
    found: dict[str, dict] = {}
    for pat in ADD_PATTERNS:
        for m in pat.finditer(text):
            name = m.group(1)
            pts_str = zen2han_digits(m.group(2)).replace(",", "").replace("，", "")
            try:
                pts: int | str = int(pts_str)
            except ValueError:
                pts = m.group(2)
            if name not in found:
                found[name] = {"name": name, "points": pts}
    # 逆引き: 文末「N点を加算する」から直前の「○○加算」名を拾う
    for m in REV_ADD_RE.finditer(text):
        # マッチ位置の前 80 文字に直近の加算名があるか
        start = max(0, m.start() - 80)
        ctx = text[start: m.start() + len(m.group(1)) + 4]
        names = NAME_BEFORE_ADD_RE.findall(ctx)
        if not names:
            continue
        name = names[-1]
        if name in found:
            continue
        pts_str = zen2han_digits(m.group(1)).replace(",", "").replace("，", "")
        try:
            pts = int(pts_str)
        except ValueError:
            pts = m.group(1)
        found[name] = {"name": name, "points": pts}
    # 制限の検出（粗い）
    lm = LIMIT_PATTERN.search(text)
    if lm and found:
        for v in found.values():
            v.setdefault("limit", lm.group(1))
    return list(found.values())


def detect_unparsed(notes: list[dict], block: str, name: str = "") -> bool:
    """注の分割が機能していない (= 構造化に失敗) と判断できる場合のみ True。

    加算抽出の漏れは別指標 (additions_extracted) で扱うのでここでは見ない。
    「削除」区分は notes が無くても正常とみなす。
    """
    if name == "削除":
        return False
    if not block.strip():
        return True
    # ブロック中に「- 注」表記があるのに notes が 1 件も取れていない
    if "- 注" in block and not notes:
        return True
    # notes が複数あるのに、最初の1件に全文の90%以上が詰まっている = 分割失敗
    if len(notes) >= 2:
        total_len = sum(len(n.get("text", "")) for n in notes)
        first_len = len(notes[0].get("text", ""))
        if total_len > 0 and first_len / total_len > 0.95:
            return True
    return False


def detect_unit(name: str, default: str = "回") -> str:
    """区分名から unit を推定。「（１日につき）」「（一連につき）」等。"""
    m = UNIT_RE.search(name)
    if not m:
        return default
    raw = m.group(1).strip()
    # 「１日」「１回」という番号付きは番号を落とす
    norm = re.sub(r"^[\d１-９]+", "", raw)
    return norm or raw or default


def build_item(ver: str, idx_entry: dict, full_text: str, names_to_codes: dict) -> dict:
    code = idx_entry["code"]
    name = idx_entry["name"]
    block = slice_item_block(full_text, code, names_to_codes)
    notes = split_notes(block)
    for n in notes:
        adds = extract_additions(n["text"])
        if adds:
            n["additions"] = adds
    has_unparsed = detect_unparsed(notes, block, name)
    unit = detect_unit(name)

    pdf, url = PDF_BY_VER[ver]
    item: dict = {
        "code": code,
        "name": name,
        "version": ver,
        "points": idx_entry.get("points"),
        "unit": unit,
        "chapter": idx_entry["chapter"],
        "raw_text": block,
        "notes": notes,
        "source": {
            "pdf": pdf,
            "url": url,
            "raw_file": idx_entry["raw_file"],
        },
        "_meta": {
            "generated_by": "rule-based",
            "human_reviewed": False,
            "has_unparsed": has_unparsed,
        },
    }
    return item


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=VERSIONS)
    ap.add_argument("--limit", type=int, help="先頭N件のみ")
    args = ap.parse_args()
    targets = [args.version] if args.version else VERSIONS

    for ver in targets:
        idx = yaml.safe_load(
            (ROOT / "data" / ver / "index.yaml").read_text(encoding="utf-8")
        )
        full_text = (ROOT / "data" / ver / "raw" / "full.txt").read_text(
            encoding="utf-8"
        )
        items_dir = ROOT / "data" / ver / "items"
        items_dir.mkdir(parents=True, exist_ok=True)
        # 既存削除 (シャード前のフラット配置 + シャード後のサブディレクトリ両方)
        import shutil
        for child in items_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            elif child.suffix == ".yaml":
                child.unlink()

        names_to_codes = {it["name"]: it["code"] for it in idx["items"]}
        targets_idx = idx["items"][: args.limit] if args.limit else idx["items"]
        n_unparsed = 0
        n_notes_total = 0
        n_with_additions = 0
        for entry in targets_idx:
            item = build_item(ver, entry, full_text, names_to_codes)
            # GitHub Web UI の 1000 件制限を回避するため、コードの先頭 2 文字 (章プレフィックス + 上位桁) でシャード
            shard = item['code'][:2]
            shard_dir = items_dir / shard
            shard_dir.mkdir(parents=True, exist_ok=True)
            out = shard_dir / f"{item['code']}.yaml"
            out.write_text(
                yaml.safe_dump(item, allow_unicode=True, sort_keys=False, width=120),
                encoding="utf-8",
            )
            if item["_meta"]["has_unparsed"]:
                n_unparsed += 1
            n_notes_total += len(item.get("notes") or [])
            if any(n.get("additions") for n in item.get("notes") or []):
                n_with_additions += 1
        # 統計を index.yaml にフィードバック
        stats = idx.get("_stats") or {}
        stats["structured_ok"] = len(targets_idx) - n_unparsed
        stats["has_unparsed"] = n_unparsed
        stats["notes_extracted"] = n_notes_total
        stats["with_additions"] = n_with_additions
        idx["_stats"] = stats
        (ROOT / "data" / ver / "index.yaml").write_text(
            yaml.safe_dump(idx, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print(
            f"[{ver}] wrote {len(targets_idx)} items "
            f"(structured_ok={stats['structured_ok']}, has_unparsed={n_unparsed}, "
            f"notes={n_notes_total}, with_additions={n_with_additions})"
        )


if __name__ == "__main__":
    main()
