# 診療報酬点数表データセット

厚生労働省告示「診療報酬の算定方法」（点数表本表）を **機械可読な YAML データセット** に変換し、
改定差分を **GitHub の per-file History** でそのまま追えるように構造化した
[`kanazawazawa/shinryohoshu-data`](https://github.com/kanazawazawa/shinryohoshu-data)
リポジトリの閲覧用ビューです。

!!! warning "本データは未レビューの自動抽出結果です"
    法的・実務的に唯一正しい情報は厚生労働省告示の原典 PDF です。
    算定実装に使う場合は必ず原典との突合を行ってください。

!!! info "Issue / Pull Request は受け付けていません"
    本リポジトリは個人的なテスト・デモ目的の公開です。
    診療報酬制度や告示内容に関するご意見・改善提案は、所管省庁等の正規の窓口へお願いします。

## 閲覧する

<div class="grid cards" markdown>

-   :material-file-document-multiple: **[令和8年度版 (R8) 区分一覧](r8/index.md)**

    現行版。全 2,240 区分を章・部・節別に一覧表示します。

-   :material-history: **[令和6年度版 (R6) 区分一覧](r6/index.md)**

    旧版。全 2,227 区分。

-   :material-compare-horizontal: **[R6 → R8 改定差分](diff/r6-r8/README.md)**

    削除 37 / 新設 50 / 構造変化 205 件の構造化サマリ。

</div>

## データの構造

このサイトに表示しているのはレンダリング済み Markdown ですが、**機械処理用には YAML を直接読んで** ください。

| 層 | パス | 内容 |
|---|---|---|
| **T1** | `data/latest/index.yaml` | 全区分の索引 |
| **T2** | `data/latest/items/<XX>/<CODE>.yaml` | 区分ごとの詳細（注・加算・原文 `raw_text` 同梱） |
| **T3** | `data/latest/raw/*.txt` | PDF を正規化したプレーンテキスト（`.gitignore`、再生成可能） |

`<XX>` はコード先頭 2 文字（例: `K6/K637-2.yaml`）。
旧版は `data/archive/<ver>/items/<XX>/<CODE>.yaml` に同構成で配置されています。

詳細は [README](https://github.com/kanazawazawa/shinryohoshu-data#readme) /
[REPRODUCE.md](https://github.com/kanazawazawa/shinryohoshu-data/blob/main/REPRODUCE.md) /
[JSON Schema](https://github.com/kanazawazawa/shinryohoshu-data/tree/main/schema) を参照してください。

## 1 区分の改定履歴を見るには

GitHub 上で対象ファイル（例:
[`data/latest/items/A0/A001.yaml`](https://github.com/kanazawazawa/shinryohoshu-data/blob/main/data/latest/items/A0/A001.yaml)）
を開き、**History** ボタンを押してください。R6→R8 の 2 commit で差分が表示されます。
