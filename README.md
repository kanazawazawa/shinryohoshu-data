# shinryohoshu-data

厚生労働省告示「診療報酬の算定方法」（点数表本表）を、電子カルテ・レセコン等のベンダーが
**機械可読な形で利用できる YAML データセット** に変換し、改定差分を
**GitHub のファイル History でそのまま追える** ように構造化したリポジトリ。

🌐 **公開サイト（人間向け閲覧ビュー）: <https://kanazawazawa.github.io/shinryohoshu-data/>**
（MkDocs Material による R6 / R8 / 改定差分の全文検索付きビュー。`main` への push で自動更新）

> ⚠️ **本リポジトリのデータは未レビューの自動抽出結果です。**
> 法的・実務的に唯一正しい情報は厚生労働省告示の原典 PDF です。
> 算定実装に使う場合は必ず原典との突合を行ってください。

> 📌 **本リポジトリは個人的なテスト・デモ目的の公開です。**
> Issue / Pull Request は受け付けていません（応答・取り込みは行いません）。
> 診療報酬制度や告示内容に関するご意見・改善提案は、所管省庁等の正規の窓口へお願いします。

---

## ディレクトリ構成

```
sources/                 原典 PDF（告示そのまま）
data/
  latest/                ← 現行版（R8 = 令和8年度）。改定のたびにここを上書き
    raw/                 T3: 章節単位プレーンテキスト（lossless, .gitignore）
    index.yaml           T1: 全区分の索引
    items/<XX>/<CODE>.yaml T2: 区分ごと詳細（raw_text 同梱）
  archive/
    r6/                  ← 旧版スナップショット（令和6年度）。同構成
docs/                    自動生成 Markdown（.gitignore）
  diff/r6-r8/            R6→R8 構造差分サマリ
schema/                  JSON Schema (Draft 2020-12)
scripts/                 抽出・検証・差分パイプライン
```

`data/**/raw/` と `docs/` は生成物のため `.gitignore`。
利用側は `data/latest/index.yaml` と `data/latest/items/<XX>/<CODE>.yaml` を読めば足ります。

---

## 3 層モデル

| 層 | ファイル | 目的 | 損失 |
|---|---|---|---|
| **T3** | `data/<ver>/raw/*.txt` | PDF→正規化テキスト（章節単位） | ゼロ（`_manifest.yaml` に SHA-256 と文字数） |
| **T1** | `data/<ver>/index.yaml` | 全区分の一覧 | 構造化のため一部欠落あり |
| **T2** | `data/<ver>/items/<XX>/<CODE>.yaml` | 区分ごと（注・加算等） + **必ず原文 `raw_text` 同梱** | `raw_text` で原文保持 |

> `<XX>` はコード先頭 2 文字（例: `K6/K637-2.yaml`）。GitHub の 1 ディレクトリ 1000 ファイル上限を回避するためのシャーディング。

---

## 改定差分（R6 → R8）を見たい

| 目的 | 推奨手段 |
|---|---|
| **1 区分の改定履歴を見る** | GitHub 上で [`data/latest/items/A0/A001.yaml`](data/latest/items/A0/A001.yaml) を開き **History** ボタン。R6→R8 の 2 commit で差分が表示される |
| **構造化サマリ**（変化があった区分だけ要点抽出） | [`docs/diff/r6-r8/`](docs/diff/r6-r8/) を参照（自動生成 Markdown） |
| **旧版（R6）を丸ごと参照** | [`data/archive/r6/`](data/archive/r6/) または `git checkout v-r6` |
| **任意 2 ファイル比較** | `git diff v-r6 v-r8 -- data/latest/items/<XX>/<CODE>.yaml` |

仕掛け: `main` ブランチは「R6 を `data/latest/` に投入」→「R8 で `data/latest/` を上書き
＋ R6 を `data/archive/r6/` にコピー」という 2 commit の直列履歴を持っており、
`data/latest/<CODE>.yaml` は **同一パス上で R6→R8 と modify されている** ため
GitHub の per-file History / Blame がそのまま改定差分ビューになります。

サマリ統計 (R6 → R8): 削除 37 / 新設 50 / 構造変化 205 件。

---

## 使い方（再生成）

```bash
uv sync

# 最新版だけビルド（高速。日常の検証用）
PYTHONIOENCODING=utf-8 uv run python scripts/build_all.py

# 履歴ごと再構築（R6 commit → R8 commit を作り直す。リリース時のみ）
PYTHONIOENCODING=utf-8 uv run python scripts/build_history.py
```

`build_all.py` は `data/latest/` のみ生成（既定では R8）。
`build_history.py` は R6/R8 を順に build → commit → tag (`v-r6`, `v-r8`) します。

**詳細な再現手順・Copilot 介入工程・既知の落とし穴は [REPRODUCE.md](REPRODUCE.md) を参照。**

---

## ライセンス

[LICENSE](LICENSE) を参照（原典告示は著作権法第13条により権利の対象外、スクリプトは MIT）。
