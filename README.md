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

## ドキュメンテーション構成

「**機械可読データ**」と「**人間向け閲覧ビュー**」を明確に分離しています。

### 使っているツール一覧

| ツール | 役割 | 種別 | 開発元 / ライセンス |
|---|---|---|---|
| **[MkDocs](https://www.mkdocs.org/)** | Markdown ファイル群を静的 HTML サイトに変換するビルダー | OSS（Python） | コミュニティ運営 / BSD-2-Clause |
| **[MkDocs Material](https://squidfunk.github.io/mkdocs-material/)** | MkDocs 用テーマ。デザイン・全文検索 UI・ダークモード等を提供 | OSS | Martin Donath 氏 (squidfunk) / MIT |
| **[awesome-pages plugin](https://github.com/lukasgeiter/mkdocs-awesome-pages-plugin)** | MkDocs プラグイン。`.pages` ファイルでナビ階層を宣言的に定義 | OSS | Lukas Geiter 氏 / MIT |
| **[PyMuPDF](https://pymupdf.readthedocs.io/)** | PDF からのテキスト抽出（`scripts/extract_raw.py` で使用） | OSS（Python） | Artifex Software / AGPL v3 |
| **[GitHub Actions](https://docs.github.com/actions)** | push をトリガーに自動でビルド・デプロイを走らせる CI/CD | **GitHub 公式**（public リポは無料） | GitHub Inc. |
| **[GitHub Pages](https://pages.github.com/)** | 生成された HTML を `https://<user>.github.io/<repo>/` で配信する静的ホスティング | **GitHub 公式**（public リポは無料） | GitHub Inc. |
| **`scripts/render_md.py`** | YAML → Markdown 変換（本リポ内のスクリプト） | 自作（このリポ） | MIT |

> **MkDocs 系は GitHub 公式ではなく OSS** です。Sphinx や Hugo, Docusaurus と同じ「静的サイトジェネレータ」の一つで、Markdown 中心・Python ベース・設定がシンプルという特徴から採用しました。GitHub 側で公式に用意されているのは **「Actions（CI 実行環境）」と「Pages（配信先）」だけ** で、その間で何のジェネレータを使うかは利用者の自由です。

### この選択は妥当か？（私見ベースの簡易評価）

> ⚠️ 以下は本リポ作者の個人的見解であり、公式な推奨ではありません。

**他の主な選択肢との比較**:

| ジェネレータ | 主な採用例 | 本リポでの適合度 |
|---|---|---|
| **MkDocs + Material**（採用） | FastAPI, Pydantic, Home Assistant, Material for MkDocs 自身, AWS の一部 SDK ドキュメント | ◎ Markdown のみで完結、検索が標準装備、設定が短い |
| **[Jekyll](https://jekyllrb.com/)** | GitHub Pages の**既定**ジェネレータ。GitHub Docs、多くの OSS プロジェクト | ○ GitHub Pages とゼロ設定で繋がる強み。ただし全文検索や階層ナビは弱め |
| **[Sphinx](https://www.sphinx-doc.org/)** | Python 公式ドキュメント, NumPy, Linux Kernel, Read the Docs | △ reStructuredText 主体で学習コストあり。API リファレンスに強いが本リポは静的データ集 |
| **[Hugo](https://gohugo.io/)** | Kubernetes ドキュメント, Let's Encrypt | ○ 高速。ただし Go テンプレートの学習コストあり |
| **[Docusaurus](https://docusaurus.io/)** | React 公式, Babel, Redux | △ React/Node 必須でこのリポの Python パイプラインと相性悪い |
| **[Quarto](https://quarto.org/)** | 学術文書・データサイエンス系 | △ 表現力高いが本リポはコード実行を含まない |

**MkDocs Material の現在地（2026 時点の体感）**:

- 「Markdown だけで書きたい・**全文検索 UI が標準で欲しい**・OSS のドキュメントサイト」用途では **デファクトに近い** 立ち位置
- GitHub の Star 数で言うと MkDocs Material は 2 万超、awesome-pages は数百程度（プラグインとしては標準的）
- 商用サポート版（Insiders）もあるが、本リポで使っているのは無料の OSS 版のみ

**公的機関での採用観点**:

- **政府系 OSS ドキュメントでも採用例あり**: 例えば英国政府の [GOV.UK Design System](https://design-system.service.gov.uk/) は独自実装だが、[CFPB（米消費者金融保護局）の公開リポ](https://github.com/cfpb) などで MkDocs/Jekyll 系の利用が見られます
- 日本の公的機関では Jekyll/Hugo が比較的多い印象（**デジタル庁の一部公開資料は Hugo**）
- **保守性の観点**: MkDocs Material は Material 単独で**ナビ・検索・テーマが完結**するため、複数プラグインを継ぎ接ぎする必要がなく、**長期保守する公的機関にとっても扱いやすい**部類
- **GitHub Pages とは独立**: 仮に将来 Pages から別ホスティング（Azure Static Web Apps, Cloudflare Pages 等）に移す場合も、`site/` の生成物をそのままアップロードするだけで移行可能。**ロックインが弱い**のは利点

**この構成の弱点**:

- 日本語の形態素解析検索は標準では弱い（lunr の char N-gram 頼り）。本リポは区分コード（半角英数字）が主キーなので影響は小さいが、本文中の漢字検索精度を上げたい場合は [Pagefind](https://pagefind.app/) に差し替える余地あり
- awesome-pages プラグインは個人メンテで、止まると `.pages` ベースの自動ナビが使えなくなる。ただし数百行の Python なのでフォーク継続は容易

### データの流れ

```
┌─────────────────────────┐
│ sources/*.pdf  (原典告示) │
└──────────┬──────────────┘
           │  extract_raw.py / extract_index.py / extract_items.py
           ▼
┌─────────────────────────────────────────────┐  ← Git 管理（一次データ）
│ data/latest/  data/archive/<ver>/           │
│   raw/*.txt (.gitignore) / index.yaml       │
│   items/<XX>/<CODE>.yaml                    │
└──────────┬──────────────────────────────────┘
           │  diff_revisions.py
           ▼
┌─────────────────────────────────────────────┐  ← Git 管理（要点ハイライト）
│ docs/diff/r6-r8/*.md                        │
└─────────────────────────────────────────────┘

           │  render_md.py (CI でのみ実行)
           ▼
┌─────────────────────────────────────────────┐  ← .gitignore（生成物）
│ docs/r6/  docs/r8/  ~4500 md                │
└──────────┬──────────────────────────────────┘
           │  mkdocs build (CI、MkDocs Material + awesome-pages)
           ▼
┌─────────────────────────────────────────────┐  ← GitHub Pages（人間向け）
│ https://kanazawazawa.github.io/shinryohoshu-data/ │
└─────────────────────────────────────────────┘
```

### 「何を Git に入れて、何を入れないか」の方針

| 種別 | 場所 | Git 管理 | 理由 |
|---|---|:---:|---|
| 原典 PDF | `sources/` | ✅ | 一次資料。再取得は手動 |
| 一次データ (YAML) | `data/latest/`, `data/archive/` | ✅ | **このリポジトリの本体**。per-file History が改定差分ビュー |
| 改定差分サマリ | `docs/diff/r6-r8/` | ✅ | 件数が少なく（数百行）、人間が一次窓口として参照する要点 |
| 章節別プレーンテキスト | `data/**/raw/` | ❌ | PDF から完全再生成可能。リポを膨らませない |
| 区分ごと Markdown | `docs/r6/`, `docs/r8/` | ❌ | **YAML から自動生成される派生物**。4500 ファイルあり、render_md.py を直すたびに全 md が変わってレビューがノイズだらけになる |
| MkDocs ビルド成果物 | `site/` | ❌ | HTML。GitHub Pages が CI でホスティング |

**原則**: Git には **「人間が直接書いた・または手作業で要点を抽出したもの」と「一次データ」だけ** 入れる。
スクリプトで決定論的に再生成できる派生物は `.gitignore` し、CI で都度ビルドする。

### 利用者の経路

| 利用者 | 入口 | 取得形式 |
|---|---|---|
| **ベンダー実装者**（電カル・レセコン） | `data/latest/items/**/*.yaml` を直接読む | 機械可読 YAML |
| **改定影響を調べたい人** | [Pages の改定差分ページ](https://kanazawazawa.github.io/shinryohoshu-data/diff/r6-r8/) または [`docs/diff/r6-r8/`](docs/diff/r6-r8/) | 人間可読 Markdown |
| **個別区分を読みたい人** | [Pages](https://kanazawazawa.github.io/shinryohoshu-data/) で全文検索 → 区分ページ | 整形済み HTML |
| **特定区分の改定履歴を見たい人** | GitHub で `data/latest/items/<XX>/<CODE>.yaml` → History | YAML diff |

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

### Pages サイトをローカルで確認する

```bash
uv sync --extra docs
PYTHONIOENCODING=utf-8 uv run python scripts/render_md.py  # docs/r6/ docs/r8/ を生成
uv run mkdocs serve                                         # http://localhost:8000
```

`main` への push で `.github/workflows/docs.yml` が同じ手順を実行し、
GitHub Pages へ自動デプロイされます。`docs/r*/` と `site/` はコミットしません。

**詳細な再現手順・Copilot 介入工程・既知の落とし穴は [REPRODUCE.md](REPRODUCE.md) を参照。**

---

## ライセンス

[LICENSE](LICENSE) を参照（原典告示は著作権法第13条により権利の対象外、スクリプトは MIT）。
