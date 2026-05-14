"""パイプライン全実行: T3 → T1 → T2 → validate → render → diff"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


STEPS = [
    ("T3 抽出: PDF → raw/", [sys.executable, str(SCRIPTS / "extract_raw.py")]),
    ("T1 抽出: raw → index.yaml", [sys.executable, str(SCRIPTS / "extract_index.py")]),
    ("T2 抽出: → items/*.yaml", [sys.executable, str(SCRIPTS / "extract_items.py")]),
    ("検証: schema + 損失検査", [sys.executable, str(SCRIPTS / "validate.py")]),
    ("Markdown 生成", [sys.executable, str(SCRIPTS / "render_md.py")]),
    ("改定差分", [sys.executable, str(SCRIPTS / "diff_revisions.py")]),
]


def main() -> int:
    for label, cmd in STEPS:
        print(f"\n────── {label} ──────")
        r = subprocess.run(cmd, cwd=str(ROOT))
        if r.returncode != 0:
            print(f"[FAIL] {label} (exit {r.returncode})")
            return r.returncode
    print("\n[ALL DONE]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
