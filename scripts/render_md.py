"""data/<ver>/items/*.yaml + index.yaml → docs/<ver>/ に Markdown を生成する。

人間が GitHub UI で読めるビューを提供する。1ファイル1区分が大量になるので、
章節別の一覧 (toc.md) と区分ファイル (<code>.md) の二段構成。
"""
from __future__ import annotations
import sys
from pathlib import Path
from collections import defaultdict

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from common import version_dir  # noqa: E402


def render_item(item: dict) -> str:
    lines: list[str] = []
    pts = item.get("points")
    pts_str = f"{pts}点" if isinstance(pts, int) else (str(pts) if pts else "—")
    lines.append(f"# {item['code']} {item['name']} — {pts_str}")
    lines.append("")
    ch = item["chapter"]
    bits = [ch.get(k) for k in ("chapter", "part", "section", "subsection") if ch.get(k)]
    lines.append("> " + " / ".join(bits))
    lines.append("")
    src = item["source"]
    # raw/*.txt は .gitignore のため公開サイトからはリンクできない。ファイル名のみ表示
    lines.append(
        f"> 版: `{item['version']}` / 出典: [{src['pdf']}]({src['url']}) / "
        f"原文: `{src['raw_file']}`"
    )
    if item["_meta"].get("has_unparsed"):
        lines.append("")
        lines.append(
            "> ⚠️ **構造化未完了**: 加算等の機械抽出が一部失敗しています。"
            "原文セクションを参照してください。"
        )
    lines.append("")

    tiers = item.get("tiers") or []
    if tiers:
        lines.append("## 階層点数")
        lines.append("")
        flat = all(not (t.get("sub_tiers")) for t in tiers)
        if flat:
            lines.append("| # | 名称 | 点数 |")
            lines.append("|---|---|---|")
            for t in tiers:
                p = t.get("points")
                p_s = f"**{p}点**" if isinstance(p, int) else (str(p) if p else "—")
                lines.append(f"| {t['id']} | {t['name']} | {p_s} |")
        else:
            lines.append("| # | 区分 | 細目 | 点数 |")
            lines.append("|---|---|---|---|")
            for t in tiers:
                subs = t.get("sub_tiers") or []
                if not subs:
                    p = t.get("points")
                    p_s = f"**{p}点**" if isinstance(p, int) else (str(p) if p else "—")
                    lines.append(f"| {t['id']} | {t['name']} | — | {p_s} |")
                else:
                    for st in subs:
                        p = st.get("points")
                        p_s = f"**{p}点**" if isinstance(p, int) else (str(p) if p else "—")
                        lines.append(f"| {t['id']} | {t['name']} | {st['label']} {st['name']} | {p_s} |")
        lines.append("")

    notes = item.get("notes") or []
    if notes:
        lines.append("## 注一覧")
        lines.append("")
        lines.append("| 注 | 主な加算 |")
        lines.append("|---|---|")
        for n in notes:
            adds = n.get("additions") or []
            cell = "<br>".join(f"{a['name']} **{a['points']}点**" for a in adds) if adds else "—"
            lines.append(f"| {n['id']} | {cell} |")
        lines.append("")

        lines.append("## 注の本文（原文）")
        lines.append("")
        for n in notes:
            lines.append(f"### {n['id']}")
            lines.append("")
            lines.append("```")
            lines.append(n["text"].rstrip())
            lines.append("```")
            adds = n.get("additions") or []
            if adds:
                lines.append("")
                lines.append("**抽出された加算**:")
                for a in adds:
                    limit = f"（{a['limit']}）" if a.get("limit") else ""
                    lines.append(f"- {a['name']}: **{a['points']}点**{limit}")
            lines.append("")
    else:
        lines.append("## 原文")
        lines.append("")
        lines.append("```")
        lines.append((item.get("raw_text") or "").rstrip())
        lines.append("```")

    lines.append("---")
    lines.append("")
    lines.append("## 全文（PDFからの正規化済原文）")
    lines.append("")
    lines.append("```")
    lines.append((item.get("raw_text") or "").rstrip())
    lines.append("```")
    return "\n".join(lines).rstrip() + "\n"


def render_toc(ver: str, idx: dict) -> str:
    lines: list[str] = []
    lines.append(f"# 診療報酬点数表 区分一覧 ({ver})")
    lines.append("")
    src = idx["source"]
    lines.append(f"出典: [{src['pdf']}]({src['url']}) / 全 {len(idx['items'])} 区分")
    lines.append("")
    stats = idx.get("_stats") or {}
    if stats:
        lines.append("## 統計")
        lines.append("")
        lines.append(f"- 全区分: **{stats.get('total', '?')}**")
        lines.append(f"- うち削除告示: {stats.get('deleted', 0)}")
        lines.append(f"- うち点数未取得: {stats.get('without_points', 0)}")
        lines.append(f"- 抽出時に偽区分として除外した行数: {stats.get('rejected_lines', 0)}")
        if "structured_ok" in stats:
            lines.append(f"- 構造化成功 (注分解OK): **{stats['structured_ok']}** / 要レビュー: {stats.get('has_unparsed', '?')}")
        lines.append("")
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for it in idx["items"]:
        ch = it["chapter"]
        key = (ch.get("chapter", ""), ch.get("part", ""), ch.get("section", ""))
        grouped[key].append(it)
    last_chap = last_part = None
    for (chap, part, sect), items in grouped.items():
        if chap != last_chap:
            lines.append(f"## {chap}")
            last_chap = chap
            last_part = None
        if part and part != last_part:
            lines.append(f"### {part}")
            last_part = part
        if sect:
            lines.append(f"#### {sect}")
        lines.append("")
        lines.append("| 区分 | 名称 | 点数 |")
        lines.append("|---|---|---|")
        for it in items:
            pts = it.get("points")
            pts_s = f"{pts}点" if isinstance(pts, int) else (str(pts) if pts else "—")
            shard = it["code"][:2]
            lines.append(f"| [{it['code']}](items/{shard}/{it['code']}.md) | {it['name']} | {pts_s} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    for ver in ("r6", "r8"):
        ver_dir = version_dir(ver)
        idx_path = ver_dir / "index.yaml"
        if not idx_path.exists():
            continue
        idx = yaml.safe_load(idx_path.read_text(encoding="utf-8"))
        out_dir = ROOT / "docs" / ver
        items_out = out_dir / "items"
        items_out.mkdir(parents=True, exist_ok=True)
        # 既存削除（シャード前のフラット配置 + シャード後のサブディレクトリ両方）
        import shutil
        for child in items_out.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            elif child.suffix == ".md":
                child.unlink()
        for f in (ver_dir / "items").rglob("*.yaml"):
            item = yaml.safe_load(f.read_text(encoding="utf-8"))
            shard = item["code"][:2]
            shard_dir = items_out / shard
            shard_dir.mkdir(parents=True, exist_ok=True)
            (shard_dir / f"{item['code']}.md").write_text(
                render_item(item), encoding="utf-8"
            )
        # MkDocs ではディレクトリの入口は index.md。同居する README.md は削除
        (out_dir / "index.md").write_text(render_toc(ver, idx), encoding="utf-8")
        old_readme = out_dir / "README.md"
        if old_readme.exists():
            old_readme.unlink()
        # awesome-pages: サイドバーには index のみ表示（items は URL でアクセス可だが
        # 2200+ あるためサイドバーには出さず、index.md の章節 TOC から辿らせる）
        (out_dir / ".pages").write_text(
            "nav:\n  - index.md\n", encoding="utf-8"
        )
        print(f"[{ver}] wrote {len(idx['items'])} item md + index.md + .pages")

    # explore ページ用の軽量 JSON を R6 + R8 から生成
    # （ブラウザで全件読み込んでフィルタ + CSV ダウンロードする用途）
    import json

    def collect(ver: str) -> dict[str, dict]:
        d = version_dir(ver)
        idx_path = d / "index.yaml"
        if not idx_path.exists():
            return {}
        out: dict[str, dict] = {}
        for f in (d / "items").rglob("*.yaml"):
            it = yaml.safe_load(f.read_text(encoding="utf-8"))
            out[it["code"]] = it
        return out

    items_r8 = collect("r8")
    items_r6 = collect("r6")

    def diff_status(code: str) -> str:
        in_r6 = code in items_r6
        in_r8 = code in items_r8
        if in_r6 and not in_r8:
            return "deleted"  # R8 で削除
        if in_r8 and not in_r6:
            return "added"    # R8 で新設
        old, new = items_r6[code], items_r8[code]
        if (
            old.get("name") != new.get("name")
            or old.get("points") != new.get("points")
            or (old.get("raw_text") or "") != (new.get("raw_text") or "")
        ):
            return "changed"
        return "unchanged"

    def record(ver: str, it: dict) -> dict:
        ch = it.get("chapter") or {}
        shard = it["code"][:2]
        src = it.get("source") or {}
        return {
            "version": ver,
            "code": it["code"],
            "name": it.get("name") or "",
            "points": it.get("points"),
            "unit": it.get("unit") or "",
            "chapter": ch.get("chapter") or "",
            "part": ch.get("part") or "",
            "section": ch.get("section") or "",
            "subsection": ch.get("subsection") or "",
            "diff_status": diff_status(it["code"]),
            "notes_count": len(it.get("notes") or []),
            "tiers_count": len(it.get("tiers") or []),
            "raw_text": it.get("raw_text") or "",
            "source_pdf": src.get("pdf") or "",
            "source_url": src.get("url") or "",
            "page_url": f"../{ver}/items/{shard}/{it['code']}/",
        }

    records: list[dict] = []
    for code, it in items_r8.items():
        records.append(record("r8", it))
    for code, it in items_r6.items():
        records.append(record("r6", it))
    records.sort(key=lambda r: (r["code"], r["version"]))

    assets_dir = ROOT / "docs" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    out_json = assets_dir / "items.json"
    out_json.write_text(
        json.dumps(
            {"versions": ["r8", "r6"], "items": records},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print(
        f"[explore] wrote {len(records)} records "
        f"(r8={len(items_r8)} + r6={len(items_r6)}) to {out_json.relative_to(ROOT)}"
        f" [{out_json.stat().st_size / 1024:.0f} KB]"
    )


if __name__ == "__main__":
    main()
