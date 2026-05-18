# 再現手順書 (REPRODUCE)

> このリポジトリは **Copilot (Claude) 支援で構築** した。
> 純粋なスクリプト実行で再現できる工程と、Copilot の判断・編集が必要な工程の両方を記録する。
>
> 検証日: 2026-05-15 / Win11 / Git Bash / Python 3.12 (uv) / PyMuPDF + PyYAML + jsonschema

---

## A. データだけ再生成したい人 (純粋自動)

PDF とスクリプトが揃っていれば **完全に冪等**。1 コマンドで全成果物を再生成できる。

```bash
git clone https://github.com/kanazawazawa/shinryohoshu-data.git
cd shinryohoshu-data
uv sync
PYTHONIOENCODING=utf-8 uv run python scripts/build_all.py
```

期待される出力 (2026-05 時点):

```
[r6] 2227 items (structured_ok=2227, has_unparsed=0, notes=1897, with_additions=260)
[r8] 2240 items (structured_ok=2240, has_unparsed=0, notes=2682, with_additions=276)
[OK] index.yaml ↔ items/ 完全一致
[OK] raw 文字数突合 (delta=0)
diff: removed=37 added=50 changed=205
```

再ビルド後 `git status` がクリーンであることが冪等性の証拠。

### 環境メモ
- Windows コンソールは `PYTHONIOENCODING=utf-8` 必須（cp932 だと print で死ぬ）。
- `uv` 前提。`pip` でも動くが lock されない。
- PDF は `sources/r6/001251499.pdf` (350pp) と `sources/r8/001686842.pdf` (400pp)。MHLW 告示の原典そのまま。

---

## B. ゼロから同種パイプラインを別の告示で組み直したい人 (Copilot 支援前提)

ここから先は **Copilot (or 同等の AI コーディングエージェント) との対話前提**。
人間だけだと PDF レイアウト由来のバグ修正に時間がかかる。

### B-1. リポ初期化 (人手)
```bash
mkdir my-koushi-data && cd $_
git init && uv init --lib
```
- `pyproject.toml` に `pymupdf`, `pyyaml`, `jsonschema` を追加
- `sources/<ver>/<file>.pdf` に原典 PDF を配置

### B-2. パイプライン雛形を Copilot に書かせる
Copilot へのプロンプト例:
> 「`sources/<ver>/<file>.pdf` を入力に、3 層 (T3 raw / T1 index / T2 items) のパイプラインを `scripts/` に作って。
> T3 は PyMuPDF で抽出 + 章節分割 + SHA-256 manifest。T1 は raw → 全区分 index.yaml。
> T2 は index + raw → 区分ごと yaml に注・加算を構造化。validate.py で JSON Schema + 文字数突合。」

雛形ができたら **build_all.py 実行 → エラーログを Copilot に渡して修正** のループ。

### B-3. 必ずハマる箇所 (このリポでも実際にハマった)

| # | 症状 | 根本原因 | 解決策 |
|---|---|---|---|
| 1 | 注分解が全く効かない | `NOTE_PREFIX` が全角空白 1 個以上を要求 | `[\u3000\s]*` (0 個 OK) に緩和 |
| 2 | `Ｄ２２５－３` 等の枝番後半角数字が落ちる | `CODE_RE` の rest が `[^\d]` 制限 | `.*?` に緩和 |
| 3 | 「削除」区分が `has_unparsed=true` | name=="削除" の特例なし | `detect_unparsed()` で削除は False を return |
| 4 | 「Ａ２１５ からＡ２１７まで削除」が 1 行で潰れる | 範囲表現を扱っていない | `RANGE_DELETE_RE` で展開 |
| 5 | unit が "回" ハードコード | 名前末尾の (○○につき) を見ていない | `detect_unit()` で動的判別 (回/日/一連) |
| 6 | TOC 部分の偽コード混入 | 助詞始まり名・名前なし点数なし | `_is_valid_code_line()` で除外 |
| 7 | R6/R8 yaml diff がノイズだらけ | dumper の quote style が呼び出しごとに違う | `common.py` で `str_representer` を `add_representer` し literal block (`|`) 統一 |
| 8 | GitHub Web UI で 1000 件超えのディレクトリが切り捨てられる | GitHub 仕様 (1 dir 1000 file 上限) | `data/<ver>/items/<XX>/<CODE>.yaml` と 2 文字プレフィックスでシャード (最大シャード 188件) |
| 9 | A200 等で `points: 1260` のような実在しない数値 | 行末 `…加算１260点` の `１` (tier-id) と `260` (points) が連結され、貪欲な `[\d０-９,，]+点` が両方吸う | `_parse_pts_from_tail(tier_id_hint=…)` で先頭桁が tier-id と一致する場合 1 桁剥がして name 側に戻す + `build_item` で header_tier 検出時に top-level points を補正 (idx_entry の name/points も同期) |
| 10 | `- ２総合入院体制加算２200点` で tier 2 の points が 2200 になる | 同上 (重複表記された tier 番号) | 同上 |

→ **これらは抽出元のレイアウトに固有なので、別の告示なら別のハマり方をする。** Copilot に「精度を上げて」と頼んで、stats (`without_points`, `rejected_lines`, `has_unparsed`) を見ながら反復改善する。

### B-4. リポ構造 (3 層 + latest/archive レイアウト)

このリポの設計上の判断:
- **`data/latest/`**: 現行版 (R8) を固定パスで提供。ベンダーはここを読めばよい
- **`data/archive/<ver>/`**: 旧版スナップショット (R6) を同構成で保持
- **同一パス上書きによる per-file 履歴**: `main` の 2 commit ([release] R6 → [release] R8) で `data/latest/items/<XX>/<CODE>.yaml` が R6→R8 と modify される → GitHub の File History / Blame がそのまま改定差分ビューになる
- **構造化 diff**: `docs/diff/r6-r8/` に per-code サマリ Markdown (自動生成、.gitignore)

---

## C. このリポで実際にやった Git 操作 (再現参考)

### C-1. main ブランチ: R6→R8 の 2 commit 直列史を作る
履歴は `scripts/build_history.py` が自動生成する。手動でやる場合の流れ:
```bash
git checkout --orphan main-new && git rm -rf .
git checkout main -- sources scripts schema README.md REPRODUCE.md LICENSE .gitignore
git add -A && git commit -m "[init] スクリプト・スキーマ・元 PDF 投入"

PYTHONIOENCODING=utf-8 uv run python scripts/build_history.py
# 内部で:
#   1. SHINRYO_LATEST_VERSION=r6 で build → data/latest/ に R6
#      commit "[release] R6 公開" + tag v-r6
#   2. data/latest → data/archive/r6/ にコピー
#   3. SHINRYO_LATEST_VERSION=r8 で build → data/latest/ を R8 で上書き
#      commit "[release] R8 公開" + tag v-r8

git branch -m main main-old && git branch -m main-new main
git push --force-with-lease origin main
git push origin v-r6 v-r8
```

### C-2. YAML スタイル統一 (diff ノイズ排除)
```python
# scripts/common.py 冒頭に追加
def _str_representer(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)
yaml.SafeDumper.add_representer(str, _str_representer)
```
→ `build_all.py` 再実行 → `[chore] YAML dumper を literal block スタイルに統一` でコミット。

### C-3. 1 区分の改定履歴を見る
```bash
# CLI: 同一パス上の R6→R8 改定が log -p で見える
git log -p data/latest/items/A0/A001.yaml

# CLI: tag 間の単一ファイル diff
git diff v-r6 v-r8 -- data/latest/items/A0/A001.yaml
```
GitHub 上では `data/latest/items/A0/A001.yaml` を開き **History** ボタン → 2 commit が並ぶ。

---

## D. Copilot を使う場合の依頼テンプレ

```
このリポは https://github.com/kanazawazawa/shinryohoshu-data の構造を踏襲したい。
- sources/<ver>/<pdf> から data/<ver>/{raw, index.yaml, items/<CODE>.yaml} を生成する 3 層パイプライン
- scripts/common.py に literal-block の str_representer を入れる (diff 安定化)
- build_all.py で T3→T1→T2→validate→render→diff まで一気通貫
- 完全冪等にすること (再ビルド後 git status クリーン)
- 現行版を data/latest/、旧版を data/archive/<ver>/ に置き、リリースごとに data/latest/ を上書きしつつ前版を archive にコピーする 2 commit 史にする
- 構造差分を docs/diff/<old>-<new>/ に出す
- リリース履歴は scripts/build_history.py で再現可能にする
```

`scripts/build_all.py` を毎回叩いて stats を見せながら反復させると早い。
