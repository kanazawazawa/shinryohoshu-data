"""normalized/*.txt を Markdown 化（見出しに #/##/... を付与）。

階層:
- 別表第N / ［目次］           → #
- 第N編                        → #
- 第N章                        → ##
- 第N部                        → ###
- 第N節 / 通則                 → ####
- 第N款                        → #####
- 区分 A000 ... (全角英大1+全角数字3) → ######

その他の本文行はそのまま出力。
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "normalized"
DST = ROOT / "md"
DST.mkdir(exist_ok=True)

RULES = [
    (re.compile(r"^別表第"), 1),
    (re.compile(r"^［[^］]+］$"), 1),
    (re.compile(r"^第[\d０-９]+編"), 1),
    (re.compile(r"^第[\d０-９]+章"), 2),
    (re.compile(r"^第[\d０-９]+部"), 3),
    (re.compile(r"^第[\d０-９]+節"), 4),
    (re.compile(r"^通則$"), 4),
    (re.compile(r"^第[\d０-９]+款"), 5),
    (re.compile(r"^[\uFF21-\uFF3A][\uFF10-\uFF19]{3}"), 6),
]


def heading_level(line: str) -> int | None:
    s = line.strip()
    if not s:
        return None
    if any(c in s for c in "、。（）"):
        return None
    for pat, lvl in RULES:
        if pat.match(s):
            return lvl
    return None


def to_md(text: str) -> str:
    out: list[str] = []
    for line in text.split("\n"):
        lvl = heading_level(line)
        if lvl is not None:
            if out and out[-1] != "":
                out.append("")
            out.append("#" * lvl + " " + line.strip())
            out.append("")
        else:
            out.append(line)
    md = "\n".join(out)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


for src in ("r6.txt", "r8.txt"):
    text = (SRC / src).read_text(encoding="utf-8")
    md = to_md(text)
    out = DST / src.replace(".txt", ".md")
    out.write_text(md, encoding="utf-8")
    print(f"{src} -> {out.name}: {len(text)} -> {len(md)}  lines: {text.count(chr(10))} -> {md.count(chr(10))}")
