"""パイプライン全実行: T3 → T1 → T2 → validate → render → diff

データレイアウト:
  data/latest/       現行版 (LATEST_VERSION) を再ビルド
  data/archive/<ver>/ 過去版のスナップショット (本スクリプトは触らない)

過去版を含む全体を git 履歴付きで作り直したい場合は scripts/build_history.py を使う。
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from common import LATEST_VERSION  # noqa: E402


STEPS = [
    ("T3 抽出: PDF → raw/", [sys.executable, str(SCRIPTS / "extract_raw.py"), "--version", LATEST_VERSION]),
    ("T1 抽出: raw → index.yaml", [sys.executable, str(SCRIPTS / "extract_index.py"), "--version", LATEST_VERSION]),
    ("T2 抽出: → items/*.yaml", [sys.executable, str(SCRIPTS / "extract_items.py"), "--version", LATEST_VERSION]),
    ("検証: schema + 損失検査", [sys.executable, str(SCRIPTS / "validate.py")]),
    ("Markdown 生成", [sys.executable, str(SCRIPTS / "render_md.py")]),
    ("改定差分", [sys.executable, str(SCRIPTS / "diff_revisions.py")]),
]


def main() -> int:
    print(f"[build_all] LATEST_VERSION = {LATEST_VERSION}")
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
