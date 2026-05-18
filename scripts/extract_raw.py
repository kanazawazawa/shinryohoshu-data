"""T3: PDF → 正規化テキスト + 章節別ファイル

出力:
  data/<ver>/raw/full.txt              全文（正規化済、データ損失検証の正本）
  data/<ver>/raw/<NN>-<NN>-<NN>.txt    章/部/節 単位に分割
  data/<ver>/raw/_manifest.yaml        loss検証用メタ（文字数・SHA）

依存: pymupdf, pyyaml
"""
from __future__ import annotations
import argparse
import hashlib
import re
import sys
from pathlib import Path

import fitz  # type: ignore
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from common import normalize, version_dir  # noqa: E402

VERSIONS = {
    "r6": ROOT / "sources" / "001251499.pdf",
    "r8": ROOT / "sources" / "001686842.pdf",
}

CHAP = re.compile(r"^第([\d１-９]+)章")
PART = re.compile(r"^第([\d１-９]+)部")
SECT = re.compile(r"^第([\d１-９]+)節")

_Z2H = str.maketrans("０１２３４５６７８９", "0123456789")


def zh(s: str) -> str:
    return s.translate(_Z2H)


def extract_full(pdf: Path) -> str:
    """PDFを単一テキストに連結し正規化する。"""
    doc = fitz.open(pdf)
    pages: list[str] = []
    for p in doc:
        pages.append(p.get_text())
    raw = "\n".join(pages)
    return normalize(raw)


def split_by_section(full: str) -> list[tuple[str, str]]:
    """正規化済テキストを 章/部/節 の単位で分割する。

    戻り値: [(filename, content), ...]
    ファイル名は ``<NN>-<NN>-<NN>-<safename>.txt`` 形式。
    """
    lines = full.split("\n")
    chap_no = part_no = sect_no = 0
    chap_name = part_name = sect_name = ""
    sections: list[tuple[str, list[str]]] = []
    current_buf: list[str] = []
    current_key: tuple[int, int, int] = (0, 0, 0)
    current_label = "00-00-00-front-matter"

    def flush():
        if current_buf:
            sections.append((current_label, list(current_buf)))

    for ln in lines:
        s = ln.strip()
        m = CHAP.match(s)
        if m:
            flush()
            chap_no = int(zh(m.group(1)))
            part_no = sect_no = 0
            chap_name = re.sub(r"^第[\d１-９]+章\s*", "", s)
            current_key = (chap_no, 0, 0)
            current_label = f"{chap_no:02d}-00-00-{_safe(chap_name)}"
            current_buf = [ln]
            continue
        m = PART.match(s)
        if m:
            flush()
            part_no = int(zh(m.group(1)))
            sect_no = 0
            part_name = re.sub(r"^第[\d１-９]+部\s*", "", s)
            current_key = (chap_no, part_no, 0)
            current_label = f"{chap_no:02d}-{part_no:02d}-00-{_safe(part_name)}"
            current_buf = [ln]
            continue
        m = SECT.match(s)
        if m:
            flush()
            sect_no = int(zh(m.group(1)))
            sect_name = re.sub(r"^第[\d１-９]+節\s*", "", s)
            current_key = (chap_no, part_no, sect_no)
            current_label = (
                f"{chap_no:02d}-{part_no:02d}-{sect_no:02d}-{_safe(sect_name)}"
            )
            current_buf = [ln]
            continue
        current_buf.append(ln)
    flush()
    return [(name, "\n".join(buf).rstrip() + "\n") for name, buf in sections]


_SAFE_RE = re.compile(r"[^\w\u3040-\u30FF\u4E00-\u9FFF・ー]+")


def _safe(s: str) -> str:
    s = _SAFE_RE.sub("-", s).strip("-")
    return s[:40] if s else "section"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=list(VERSIONS), help="r6 / r8 / 省略で全版")
    args = ap.parse_args()
    targets = [args.version] if args.version else list(VERSIONS)

    for ver in targets:
        pdf = VERSIONS[ver]
        out_dir = version_dir(ver) / "raw"
        out_dir.mkdir(parents=True, exist_ok=True)
        # 既存削除
        for f in out_dir.glob("*"):
            f.unlink()

        full = extract_full(pdf)
        (out_dir / "full.txt").write_text(full, encoding="utf-8")

        sections = split_by_section(full)
        manifest = {
            "version": ver,
            "source_pdf": pdf.name,
            "full_text_chars": len(full),
            "full_text_sha256": hashlib.sha256(full.encode("utf-8")).hexdigest(),
            "sections": [],
        }
        for name, content in sections:
            (out_dir / f"{name}.txt").write_text(content, encoding="utf-8")
            manifest["sections"].append(
                {"file": f"{name}.txt", "chars": len(content)}
            )
        # データ損失検証用: sections の合計 ≈ full.txt
        total_sect = sum(s["chars"] for s in manifest["sections"])
        manifest["sections_total_chars"] = total_sect
        manifest["delta_chars"] = len(full) - total_sect
        (out_dir / "_manifest.yaml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print(
            f"[{ver}] {pdf.name}: {len(full):>7} chars, "
            f"{len(sections)} sections (delta {manifest['delta_chars']})"
        )


if __name__ == "__main__":
    main()
