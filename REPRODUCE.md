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
diff: removed=37 added=50 changed=212
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

→ **これらは抽出元のレイアウトに固有なので、別の告示なら別のハマり方をする。** Copilot に「精度を上げて」と頼んで、stats (`without_points`, `rejected_lines`, `has_unparsed`) を見ながら反復改善する。

### B-4. リポ構造 (3 層 + 並列バージョン + ハイブリッド履歴)

このリポの設計上の判断:
- **物理並列**: `data/r6/` と `data/r8/` を共存させベンダーが適用日で切り替え可能に
- **構造化 diff**: `docs/diff/r6-r8/` に per-code 差分を生成
- **履歴ベース diff (デモ用)**: `revisions` ブランチで `data/items/<CODE>.yaml` 単一パスに R6→R8 を上書きコミット → GitHub の Blame/History で改定が追える

---

## C. このリポで実際にやった Git 操作 (再現参考)

### C-1. main ブランチ: 並列構造の正史を整える
```bash
# 試行錯誤の commit を 3 commit に再構成
git rebase -i --root  # squash で
#   ab306d4 [feat] パイプライン基盤
#   d5407e6 [data] R6 全区分公開 (tag: r6-published)
#   2420186 [data] R8 全区分公開 (tag: r8-published)
git tag r6-published <r6-commit>
git tag r8-published <r8-commit>
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

### C-3. revisions ブランチ (履歴デモ用) 作成
```bash
git checkout --orphan revisions
git rm -rf .

# Step 1: R6 を data/items/ に flat 配置してコミット
git checkout main -- data/r6 README.md
mkdir -p data/items
cp -r data/r6/items/* data/items/
cp data/r6/index.yaml data/index.yaml
rm -rf data/r6
git add -A && git commit -m "[r6] 令和6年度 診療報酬点数表 (2227区分)"

# Step 2: R8 を同じパスに上書きコミット
rm -rf data/items data/index.yaml
git checkout main -- data/r8
mkdir -p data/items
cp -r data/r8/items/* data/items/
cp data/r8/index.yaml data/index.yaml
rm -rf data/r8
git add -A && git commit -m "[r8] 令和8年度 (2240区分) — R6からの改定"

git checkout main
```

これで `git log -p data/items/A001.yaml` や GitHub Blame で改定履歴が追える。

### C-4. push (履歴書き換え後の初回)
```bash
git push --force-with-lease origin main
git push origin revisions
git push origin --tags
```

---

## D. Copilot を使う場合の依頼テンプレ

```
このリポは https://github.com/kanazawazawa/shinryohoshu-data の構造を踏襲したい。
- sources/<ver>/<pdf> から data/<ver>/{raw, index.yaml, items/<CODE>.yaml} を生成する 3 層パイプライン
- scripts/common.py に literal-block の str_representer を入れる (diff 安定化)
- build_all.py で T3→T1→T2→validate→render→diff まで一気通貫
- 完全冪等にすること (再ビルド後 git status クリーン)
- R6/R8 のような並列バージョンを data/<ver>/ に共存させる
- 構造差分を docs/diff/<old>-<new>/ に出す
- 履歴デモ用に revisions orphan ブランチを別途作る
```

`scripts/build_all.py` を毎回叩いて stats を見せながら反復させると早い。
