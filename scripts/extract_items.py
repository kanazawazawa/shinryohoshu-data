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

# === 階層点数 (tier) 抽出用 ===
# トップレベル tier: "- 1 名前 530点" / "- １ 名前" 等。先頭は 1〜99
TIER_LINE_RE = re.compile(r"^-\s*([0-9０-９]{1,2})(?![0-9０-９])\s*(.*)$")
# サブ tier: 字下げ後に "- イ 名前 530点" のような片仮名見出し
SUBTIER_LINE_RE = re.compile(
    r"^[\u3000\s]+-\s*([イロハニホヘトチリヌルヲワカヨタレソツネナラム])\s*(.*)$"
)
# 末尾点数: "...名前 12,340点" / "...530点"
TRAILING_PTS_RE = re.compile(r"^(.*?)([\d０-９][\d０-９,，]*)[\s　]*点[\s　]*$")
# name 末尾の "（X につき）１AAAA" → tier 1 が name に埋まっているケース (A200 等)
NAME_HEADER_TIER_RE = re.compile(r"^(.*[）)])([1１])(.+)$")


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


def _parse_pts_from_tail(text: str, tier_id_hint: str | None = None) -> tuple[str, int | str | None]:
    """末尾の 'XXXX 530点' から (前文, 点数) を分離。点数なしなら (text, None)。

    PDF原文ではしばしば tier 番号が直前の名前末尾に重複表記される
    (例: '- ２総合入院体制加算２200点' → 名前=総合入院体制加算２, 点数=200)。
    tier_id_hint が与えられかつ pts 先頭桁がそれと一致し残桁が 1 以上ある場合、
    先頭桁を名前側へ戻す。
    """
    text = text.strip()
    m = TRAILING_PTS_RE.match(text)
    if not m:
        return text, None
    name_part = m.group(1).strip()
    pts_orig = m.group(2)
    pts_raw = zen2han_digits(pts_orig).replace(",", "").replace("，", "")
    if (
        tier_id_hint
        and len(pts_raw) > len(tier_id_hint)
        and pts_raw.startswith(tier_id_hint)
    ):
        # 元の全角/半角表記を保ちつつ tier-id 桁を name 側へ戻す
        name_part = (name_part + pts_orig[: len(tier_id_hint)]).strip()
        pts_raw = pts_raw[len(tier_id_hint):]
        pts_orig = pts_orig[len(tier_id_hint):]
    try:
        return name_part, int(pts_raw)
    except ValueError:
        return name_part, m.group(2)


def _split_name_for_header_tier(name: str) -> tuple[str, dict | None]:
    """name 末尾の '...（X につき）１AAAA' から tier 1 を取り出し、本体名と分離。

    例: '急性期総合体制加算（１日につき）１急性期総合体制加算１'
        → ('急性期総合体制加算（１日につき）', {id:'1', name:'急性期総合体制加算１'})
    マッチしなければ (name, None)。
    """
    m = NAME_HEADER_TIER_RE.match(name)
    if not m:
        return name, None
    base, _digit, sub = m.group(1), m.group(2), m.group(3)
    sub = sub.strip()
    if not sub:
        return name, None
    return base, {"id": "1", "name": sub}


def extract_tiers(block: str, header_tier: dict | None) -> list[dict]:
    """raw_text から tier (1〜N) と sub_tier (イ/ロ/ハ…) を抽出。

    - header_tier 指定時は tier 1 として先頭に置き、本文 '- N' の期待値は 2 から開始
    - 連番 (1, 2, 3...) でない場合はそこで打ち切る (誤検出防止)
    - '- 注' 行に到達したら終了
    """
    tiers: list[dict] = []
    expected = 1
    if header_tier:
        tiers.append(dict(header_tier))
        expected = 2
    current = tiers[-1] if tiers else None

    lines = block.split("\n")
    # 1 行目 (区分ヘッダ行) はスキップ
    body = lines[1:] if lines else []

    for ln in body:
        # 注以降は対象外
        if NOTE_PREFIX.match(ln):
            break
        # サブ tier 判定 (字下げあり)
        sm = SUBTIER_LINE_RE.match(ln)
        if sm and current is not None:
            sub_name, pts = _parse_pts_from_tail(sm.group(2))
            sub: dict = {"label": sm.group(1), "name": sub_name}
            if pts is not None:
                sub["points"] = pts
            current.setdefault("sub_tiers", []).append(sub)
            continue
        # トップレベル tier 判定
        m = TIER_LINE_RE.match(ln)
        if m:
            raw_num = zen2han_digits(m.group(1))
            exp_str = str(expected)
            # 連番期待値で先頭一致しなければ tier ではない (注の連番ITEM等)
            if not raw_num.startswith(exp_str):
                # 期待からずれた → 抽出終了 (それ以降は別物の可能性高)
                break
            taken = exp_str
            rest = raw_num[len(exp_str):] + m.group(2)
            tier_name, pts = _parse_pts_from_tail(rest, tier_id_hint=exp_str)
            if not tier_name:
                # 名前が空ならスキップ
                break
            current = {"id": exp_str, "name": tier_name}
            if pts is not None:
                current["points"] = pts
            tiers.append(current)
            expected += 1
            continue
        # それ以外の行は何もしない (text 継続行など)
    # 最低 2 件で初めて意味のある tier 構造とみなす
    if len(tiers) < 2:
        return []
    return tiers


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

    # tier 抽出: name 末尾に隠れた tier 1 を分離 → 本文から残り tier を抽出
    base_name, header_tier = _split_name_for_header_tier(name)
    tiers = extract_tiers(block, header_tier)
    # tier が取れたら名前は "1AAA" 部分を落とした base_name に置き換え
    out_name = base_name if tiers and header_tier else name

    # 所定点数が "1NNN" として誤吸収されている場合の補正:
    # 「…加算（１日につき）１…加算１260点」のような行で extract_index は
    # 末尾の "１260点" を 1260 として読んでしまう。tier 1 が header_tier として
    # 検出された場合、先頭桁 "1" は tier-id 表記なので剥がして tier 1 の points にする。
    raw_pts = idx_entry.get("points")
    out_points = raw_pts
    if tiers and header_tier and isinstance(raw_pts, int):
        s = str(raw_pts)
        if s.startswith("1") and len(s) > 1:
            real_pts = int(s[1:])
            # header_tier (= tiers[0]) を上書き: name に末尾「１」を付け足し、points 設定
            t1 = tiers[0]
            if not t1["name"].rstrip().endswith(("1", "１")):
                t1["name"] = t1["name"].rstrip() + "１"
            t1["points"] = real_pts
            out_points = None
            # index.yaml にも反映 (再書き出しで永続化)
            idx_entry["points"] = None
    # name もクリーン版に揃える (index.yaml と items/*.yaml で表示一致)
    if tiers and header_tier:
        idx_entry["name"] = base_name

    pdf, url = PDF_BY_VER[ver]
    item: dict = {
        "code": code,
        "name": out_name,
        "version": ver,
        "points": out_points,
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
    if tiers:
        # source の前に挿入したいので組み立て直し
        item = {
            "code": item["code"],
            "name": item["name"],
            "version": item["version"],
            "points": item["points"],
            "unit": item["unit"],
            "chapter": item["chapter"],
            "raw_text": item["raw_text"],
            "tiers": tiers,
            "notes": item["notes"],
            "source": item["source"],
            "_meta": item["_meta"],
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
        n_with_tiers = 0
        n_tier_pts_total = 0
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
            if item.get("tiers"):
                n_with_tiers += 1
                for t in item["tiers"]:
                    if "points" in t:
                        n_tier_pts_total += 1
                    for st in t.get("sub_tiers") or []:
                        if "points" in st:
                            n_tier_pts_total += 1
        # 統計を index.yaml にフィードバック
        stats = idx.get("_stats") or {}
        stats["structured_ok"] = len(targets_idx) - n_unparsed
        stats["has_unparsed"] = n_unparsed
        stats["notes_extracted"] = n_notes_total
        stats["with_additions"] = n_with_additions
        stats["with_tiers"] = n_with_tiers
        stats["tier_points_total"] = n_tier_pts_total
        idx["_stats"] = stats
        (ROOT / "data" / ver / "index.yaml").write_text(
            yaml.safe_dump(idx, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print(
            f"[{ver}] wrote {len(targets_idx)} items "
            f"(structured_ok={stats['structured_ok']}, has_unparsed={n_unparsed}, "
            f"notes={n_notes_total}, with_additions={n_with_additions}, "
            f"with_tiers={n_with_tiers}, tier_points={n_tier_pts_total})"
        )


if __name__ == "__main__":
    main()
