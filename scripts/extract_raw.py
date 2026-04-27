"""PDF を素のテキストへ抽出する。正規化はしない。"""
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "raw"
OUT.mkdir(exist_ok=True)

TARGETS = {
    "001251499.pdf": "r6.txt",  # 令和6年
    "001686842.pdf": "r8.txt",  # 令和8年
}

for src, dst in TARGETS.items():
    doc = fitz.open(ROOT / src)
    parts = []
    for i, page in enumerate(doc):
        parts.append(f"\n\n<!-- page {i+1} -->\n")
        parts.append(page.get_text("text"))
    text = "".join(parts)
    (OUT / dst).write_text(text, encoding="utf-8")
    print(f"{src} -> raw/{dst}: pages={doc.page_count} chars={len(text)}")
