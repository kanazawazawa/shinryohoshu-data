# 診療報酬点数表 改定差分プロジェクト

厚生労働省告示「診療報酬の算定方法」（令和6年版・令和8年版）の本文を Markdown 化し、
Git の履歴・diff 機能で改定箇所を可視化することを目的としたリポジトリ。

## 構成

| パス | 内容 | Git 管理 |
|---|---|---|
| `001251499.pdf` | 令和6年告示 PDF（原典） | ✅ |
| `001686842.pdf` | 令和8年告示 PDF（原典） | ✅ |
| `scripts/extract_raw.py` | PDF → `raw/*.txt`（PyMuPDF 素抽出） | ✅ |
| `scripts/normalize.py` | `raw/*.txt` → `normalized/*.txt`（段落再構築） | ✅ |
| `scripts/markdownify.py` | `normalized/*.txt` → `md/*.md`（見出し化） | ✅ |
| `raw/` | 素抽出（再生成可） | ❌ |
| `normalized/` | 正規化済テキスト（再生成可） | ❌ |
| `md/shinryou.md` | 診療報酬点数表本文（マスターデータ、main=R8 / tag r6=R6） | ✅ |
| `md/r6.md` / `md/r8.md` | 並置表示用（再生成可） | ❌ |

## ブランチ / タグ運用

- `main` = 最新告示（令和8年版）
- タグ `r6` / `r8` で各時点を固定
- 改定差分は `git diff r6 r8 -- md/` で取得

## コミットメッセージ規約

[legalize-dev/legalize-es](https://github.com/legalize-dev/legalize-es) の規約を参考にした、
本リポジトリ向けの簡略版。

| プレフィクス | 用途 | 例 |
|---|---|---|
| `[bootstrap]` | 告示初版の取り込み | `[bootstrap] R6版 取り込み` |
| `[reform]` | 告示改定の取り込み | `[reform] R8版 への改定` |
| `[fix]` | 正規化/Markdown化ロジックの修正 | `[fix] ルビ判定: ひらがな単独行の閾値調整` |
| `[chore]` | リポジトリ整備・依存・無害な再生成 | `[chore] .gitignore: normalized/ 追加` |
| `[docs]` | README/メタデータ等の文書整備 | `[docs] frontmatter 追加` |

部分改定など対象範囲を明示したい場合は ` — ` 区切りで補足:

```
[reform] R8版 — 第２章特掲診療料 ほか
```

## 再生成手順

```bash
python scripts/extract_raw.py
python scripts/normalize.py
python scripts/markdownify.py
```

依存: Python 3.10+, PyMuPDF (`pip install pymupdf`)。

## 正規化ルール（diff 安定化のため統一）

- ルビ（直前行末が漢字、ひらがな1〜5字単独行）は除去
- PDF 折り返し由来の物理改行は段落として連結（句点「。」で改行 = 1文1行）
- CJK 文字に隣接する半角スペース（両端揃え由来）は除去
- 項目番号と本文の区切りは全角スペース1個に固定
- 見出し: 第N編/章/部/節/款、区分（A000形式）、通則、別表、［目次］
- 見出し階層: 編=#1 / 章=#2 / 部=#3 / 節・通則=#4 / 款=#5 / 区分=#6

## 出典 / ライセンス

- 厚生労働省告示「診療報酬の算定方法の一部を改正する件」
- 公開元: <https://www.mhlw.go.jp/>

告示本文は政府著作物であり、著作権法第13条により著作権の対象とならない。
リポジトリ側の正規化スクリプト等の扱いは [`LICENSE`](./LICENSE) を参照。
