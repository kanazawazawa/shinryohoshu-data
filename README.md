# shinryohoshu-data

厚生労働省告示「診療報酬の算定方法」（点数表本表）を、電子カルテ・レセコン等のベンダーが
**機械可読な形で利用できる YAML データセット** に変換し、改定版を **並列に保持** して
構造差分を取れるようにすることを目的としたリポジトリ。

> ⚠️ **本リポジトリのデータは未レビューの自動抽出結果です。**
> 法的・実務的に唯一正しい情報は厚生労働省告示の原典 PDF です。
> 算定実装に使う場合は必ず原典との突合を行ってください。

---

## ディレクトリ構成

```
sources/                 原典 PDF（告示そのまま）
data/
  r6/                    令和6年度版（現行）
    raw/                 T3: 章節単位プレーンテキスト（lossless）
    index.yaml           T1: 全区分の索引（コード・名称・点数・章節）
    items/<XX>/<CODE>.yaml T2: 区分ごと詳細（raw_text 必須保持） ; <XX>=コード先頭2文字でシャード
  r8/                    令和8年度版（改定）  同構成
docs/                    自動生成 Markdown（人間閲覧用 / .gitignore）
  r6/items/<XX>/<CODE>.md
  r8/items/<XX>/<CODE>.md
  diff/r6-r8/            R6→R8 構造差分
schema/                  JSON Schema (Draft 2020-12)
scripts/                 抽出・検証・差分パイプライン
```

`data/**/raw/` と `docs/` は生成物のため `.gitignore`。
利用側は `data/<ver>/index.yaml` と `data/<ver>/items/<CODE>.yaml` を読めば足ります。

---

## 3 層モデル

| 層 | ファイル | 目的 | 損失 |
|---|---|---|---|
| **T3** | `data/<ver>/raw/*.txt` | PDF→正規化テキスト（章節単位） | ゼロ（章ごとの SHA-256 と文字数を `_manifest.yaml` に記録） |
| **T1** | `data/<ver>/index.yaml` | 全区分の一覧（コード・名称・点数・章節） | 構造化のため一部欠落あり |
| **T2** | `data/<ver>/items/<XX>/<CODE>.yaml` | 区分ごと（注・加算等） + **必ず原文 `raw_text` を同梱** | `raw_text` で原文保持 |

> `<XX>` はコード先頭 2 文字（例: `K6/K637-2.yaml`）。GitHub Web UI の 1 ディレクトリ 1000 ファイル上限を回避するためのシャーディング。

T1 / T2 は機械的抽出のため誤りを含み得るが、`raw_text` を必ず残すことで
**「自動抽出結果」と「原文」の両方を 1 ファイルで照合できる** 設計になっている。

---

## 並列バージョン保持

R6（現行）と R8（改定）は **両方とも `data/r6/` と `data/r8/` に共存**。
ベンダーは適用日に応じて参照ディレクトリを切り替えるだけで使える。

スナップショットを固定したい場合は Git タグ (`r6-published`, `r8-published`) を参照。

---

## 使い方（再生成）

```bash
uv sync
PYTHONIOENCODING=utf-8 uv run python scripts/build_all.py
```

下記が順に実行される:

1. `extract_raw.py` &nbsp; PDF → `data/<ver>/raw/`
2. `extract_index.py` &nbsp; raw → `data/<ver>/index.yaml`
3. `extract_items.py` &nbsp; index + raw → `data/<ver>/items/<CODE>.yaml`
4. `validate.py` &nbsp; JSON Schema 検証 + 索引↔個別ファイル整合 + 文字数突合
5. `render_md.py` &nbsp; YAML → `docs/<ver>/`
6. `diff_revisions.py` &nbsp; R6 vs R8 → `docs/diff/r6-r8/`

完全冪等です（再ビルド後 `git status` がクリーン）。
**詳細な再現手順・Copilot 介入工程・既知の落とし穴は [REPRODUCE.md](REPRODUCE.md) を参照。**

---

## ライセンス

[LICENSE](LICENSE) を参照（原典告示は著作権法第13条により権利の対象外、スクリプトは MIT）。
