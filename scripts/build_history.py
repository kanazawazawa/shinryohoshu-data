"""R6 → R8 を 2 commit に分けてゼロから git 履歴を再構築する。

前提:
  - クリーンなブランチ上で実行 (orphan 推奨)。実行前に作業ツリーは scripts/, schema/,
    sources/, README.md, REPRODUCE.md, LICENSE, .gitignore のみ commit 済みであること
  - sources/001251499.pdf (R6) と sources/001686842.pdf (R8) が存在すること

挙動:
  Step 1: SHINRYO_LATEST_VERSION=r6 で R6 を data/latest/ に build → commit
  Step 2: data/latest/ を data/archive/r6/ に複製
          SHINRYO_LATEST_VERSION=r8 で R8 を data/latest/ に build (上書き)
          docs/diff/r6-r8/ を生成 → commit

これにより同じパス data/latest/items/<XX>/<CODE>.yaml に 2 つの commit が積まれ、
GitHub の History/Blame で R6→R8 改定差分が直接読める。
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


# 古い版 → 新しい版 の順に並べる。新版を release するときは末尾に追加する。
RELEASES = [
    {"ver": "r6", "label": "令和6年度", "tag": "v-r6"},
    {"ver": "r8", "label": "令和8年度", "tag": "v-r8"},
]


def run(cmd: list[str], env: dict | None = None) -> None:
    print(f"$ {' '.join(cmd)}")
    e = os.environ.copy()
    if env:
        e.update(env)
    r = subprocess.run(cmd, cwd=str(ROOT), env=e)
    if r.returncode != 0:
        sys.exit(r.returncode)


def build_version(ver: str) -> None:
    env = {"SHINRYO_LATEST_VERSION": ver, "PYTHONIOENCODING": "utf-8"}
    run([sys.executable, str(SCRIPTS / "extract_raw.py"), "--version", ver], env)
    run([sys.executable, str(SCRIPTS / "extract_index.py"), "--version", ver], env)
    run([sys.executable, str(SCRIPTS / "extract_items.py"), "--version", ver], env)
    run([sys.executable, str(SCRIPTS / "validate.py")], env)


def main() -> int:
    data_dir = ROOT / "data"
    if data_dir.exists():
        print(f"[clean] removing existing {data_dir}")
        shutil.rmtree(data_dir)

    docs_diff = ROOT / "docs" / "diff"
    if docs_diff.exists():
        shutil.rmtree(docs_diff)

    archived: list[str] = []
    for i, rel in enumerate(RELEASES):
        ver = rel["ver"]
        is_last = i == len(RELEASES) - 1
        print(f"\n========== {ver} ({rel['label']}) build ==========")
        build_version(ver)

        # 最新版なら docs と diff を生成
        env = {"SHINRYO_LATEST_VERSION": ver, "PYTHONIOENCODING": "utf-8"}
        run([sys.executable, str(SCRIPTS / "render_md.py")], env)
        if archived:
            # 直前版 (= 一番新しい archived) との diff を生成
            run([sys.executable, str(SCRIPTS / "diff_revisions.py")], env)

        # git commit
        msg = f"[release] {ver.upper()} ({rel['label']}) 公開"
        if archived:
            prev = archived[-1]
            msg += f" — 前版({prev.upper()})は data/archive/{prev}/ に退避"
        run(["git", "add", "-A"])
        run(["git", "commit", "-m", msg])
        run(["git", "tag", rel["tag"]])

        if not is_last:
            # 次の release に向け data/latest を data/archive/<ver>/ にスナップショット。
            # data/latest 本体は次の build_version() が中身を上書きするので残しておく。
            latest = data_dir / "latest"
            archive = data_dir / "archive" / ver
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(latest, archive)
            archived.append(ver)

    print("\n[build_history] DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
