"""r6 と r8 の構造的差分を Markdown で出力する。

出力: docs/diff/r6-r8/README.md (区分一覧の差分)
      docs/diff/r6-r8/<code>.md (区分ごと差分)

差分は次を検出:
- 新設区分 / 削除区分
- 所定点数変更
- 注の追加/削除/名称変更（rule-based のため title無し、idベース）
- 加算の追加/削除/点数変更
"""
from __future__ import annotations
import sys
from pathlib import Path

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from common import version_dir  # noqa: E402


def load_items(ver: str) -> dict[str, dict]:
    d = version_dir(ver) / "items"
    return {f.stem: yaml.safe_load(f.read_text(encoding="utf-8")) for f in d.rglob("*.yaml")}


def index_adds(note: dict) -> dict[str, dict]:
    return {a["name"]: a for a in (note.get("additions") or [])}


def diff_item(old: dict, new: dict) -> list[str]:
    out: list[str] = []
    if old.get("name") != new.get("name"):
        out.append(f"- 名称: 「{old.get('name')}」→「{new.get('name')}」")
    if old.get("points") != new.get("points"):
        out.append(f"- 所定点数: `{old.get('points')}` → `{new.get('points')}`")

    o_notes = {n["id"]: n for n in (old.get("notes") or [])}
    n_notes = {n["id"]: n for n in (new.get("notes") or [])}
    removed = sorted(set(o_notes) - set(n_notes))
    added = sorted(set(n_notes) - set(o_notes))
    common = sorted(set(o_notes) & set(n_notes))

    for nid in removed:
        out.append(f"- 注削除: {nid}")
    for nid in added:
        out.append(f"- 注新設: {nid}")
        for a in n_notes[nid].get("additions") or []:
            out.append(f"    - + 加算: {a['name']} {a['points']}点")
    for nid in common:
        oa, na = index_adds(o_notes[nid]), index_adds(n_notes[nid])
        for name in sorted(set(oa) - set(na)):
            out.append(f"- {nid} 加算削除: {name} ({oa[name]['points']}点)")
        for name in sorted(set(na) - set(oa)):
            out.append(f"- {nid} 加算新設: {name} ({na[name]['points']}点)")
        for name in sorted(set(oa) & set(na)):
            if oa[name]["points"] != na[name]["points"]:
                out.append(
                    f"- {nid} 加算点数変更: {name} "
                    f"{oa[name]['points']} → {na[name]['points']}"
                )
    return out


def main() -> None:
    old = load_items("r6")
    new = load_items("r8")
    out_dir = ROOT / "docs" / "diff" / "r6-r8"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("*.md"):
        f.unlink()

    removed = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    common = sorted(set(old) & set(new))

    summary: list[str] = ["# 診療報酬点数表 改定差分 (R6 → R8)", ""]
    summary.append(f"- 削除された区分: **{len(removed)}**")
    summary.append(f"- 新設された区分: **{len(added)}**")
    summary.append(f"- 既存区分: **{len(common)}**")
    summary.append("")

    if removed:
        summary.append("## 削除された区分")
        summary.append("")
        for c in removed:
            summary.append(f"- `{c}` {old[c]['name']}")
        summary.append("")
    if added:
        summary.append("## 新設された区分")
        summary.append("")
        for c in added:
            summary.append(f"- `{c}` {new[c]['name']}")
        summary.append("")

    changed_count = 0
    summary.append("## 変更のあった既存区分")
    summary.append("")
    summary.append("| 区分 | 名称 | 主な変更点 |")
    summary.append("|---|---|---|")
    for code in common:
        diffs = diff_item(old[code], new[code])
        if not diffs:
            continue
        changed_count += 1
        # 区分ごと詳細 md
        lines = [f"# {code} 改定差分 (R6 → R8)", ""]
        lines.append(f"- **R6 名称**: {old[code]['name']}  (点数: `{old[code].get('points')}`)")
        lines.append(f"- **R8 名称**: {new[code]['name']}  (点数: `{new[code].get('points')}`)")
        lines.append("")
        lines.append("## 構造差分")
        lines.append("")
        lines.extend(diffs)
        lines.append("")
        lines.append("## R6 原文")
        lines.append("")
        lines.append("```")
        lines.append((old[code].get("raw_text") or "").rstrip())
        lines.append("```")
        lines.append("")
        lines.append("## R8 原文")
        lines.append("")
        lines.append("```")
        lines.append((new[code].get("raw_text") or "").rstrip())
        lines.append("```")
        (out_dir / f"{code}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        first_diff = "; ".join(d.lstrip("- ") for d in diffs[:2])
        if len(diffs) > 2:
            first_diff += f" 他{len(diffs)-2}件"
        summary.append(
            f"| [{code}](./{code}.md) | {new[code]['name']} | {first_diff} |"
        )
    summary.append("")
    summary.insert(5, f"- 構造変化のあった既存区分: **{changed_count}**")
    (out_dir / "README.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(
        f"diff: removed={len(removed)} added={len(added)} "
        f"changed={changed_count} (out: {out_dir.relative_to(ROOT)})"
    )


if __name__ == "__main__":
    main()
