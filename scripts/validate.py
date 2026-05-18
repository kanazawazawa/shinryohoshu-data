"""schema 検証 + データ損失検証を一括で行う。

- index.yaml が schema/index.schema.json に適合
- items/*.yaml が schema/item.schema.json に適合
- index.items の全 code が items/<code>.yaml に存在 (またはその逆)
- raw/<file>.txt の合計文字数 = full.txt の文字数 (manifest 内の delta_chars)
"""
from __future__ import annotations
import io
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from common import version_dir  # noqa: E402
INDEX_SCHEMA = json.loads((ROOT / "schema" / "index.schema.json").read_text(encoding="utf-8"))
ITEM_SCHEMA = json.loads((ROOT / "schema" / "item.schema.json").read_text(encoding="utf-8"))


def main() -> int:
    overall_ok = True
    for ver in ("r6", "r8"):
        ver_dir = version_dir(ver)
        if not ver_dir.exists():
            continue
        print(f"\n=== {ver} ===")
        # index
        idx_path = ver_dir / "index.yaml"
        idx_doc = yaml.safe_load(idx_path.read_text(encoding="utf-8"))
        errs = list(Draft202012Validator(INDEX_SCHEMA).iter_errors(idx_doc))
        if errs:
            overall_ok = False
            print(f"[NG] {idx_path.relative_to(ROOT)}")
            for e in errs[:10]:
                print(f"  - {'/'.join(map(str,e.absolute_path)) or '<root>'}: {e.message}")
        else:
            print(f"[OK] index.yaml ({len(idx_doc['items'])} items)")

        # items
        items_dir = ver_dir / "items"
        # シャード化対応: items/<LETTER>/<CODE>.yaml を再帰的に拾う
        item_files = sorted(items_dir.rglob("*.yaml"))
        item_validator = Draft202012Validator(ITEM_SCHEMA)
        bad = 0
        for f in item_files:
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
            errs = list(item_validator.iter_errors(doc))
            if errs:
                bad += 1
                if bad <= 5:
                    print(f"[NG] items/{f.name}")
                    for e in errs[:3]:
                        path = "/".join(map(str, e.absolute_path)) or "<root>"
                        print(f"     - {path}: {e.message}")
        if bad:
            overall_ok = False
            print(f"  → {bad}/{len(item_files)} items invalid")
        else:
            print(f"[OK] {len(item_files)} item files")

        # cross-check
        idx_codes = {it["code"] for it in idx_doc["items"]}
        file_codes = {f.stem for f in item_files}
        missing_files = idx_codes - file_codes
        extra_files = file_codes - idx_codes
        if missing_files:
            overall_ok = False
            print(f"[NG] index にあって items/ に無い: {len(missing_files)}件")
            for c in sorted(missing_files)[:5]:
                print(f"     - {c}")
        if extra_files:
            print(f"[WARN] items/ にあって index に無い: {len(extra_files)}件")
        if not missing_files and not extra_files:
            print("[OK] index ↔ items/ 完全一致")

        # raw データ損失検証
        manifest_path = ver_dir / "raw" / "_manifest.yaml"
        if manifest_path.exists():
            m = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            delta = m.get("delta_chars", 0)
            if abs(delta) > 0:
                print(f"[WARN] raw 文字数差: {delta} (full.txt と sections合計の差)")
            else:
                print(f"[OK] raw 文字数突合 ({m['full_text_chars']} chars)")

    print("\n結果:", "ALL OK" if overall_ok else "FAIL")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
