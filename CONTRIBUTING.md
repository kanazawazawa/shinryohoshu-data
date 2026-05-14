# コントリビューションガイド

## 改定内容の修正・追加

自動抽出は不完全なので、原典 PDF と突合した上で **PR で修正** してください。

1. 該当する `data/<ver>/items/<CODE>.yaml` を直接編集
2. `_meta.human_reviewed: true` を立てる
3. 編集後に検証を実行:
   ```bash
   uv run python scripts/validate.py
   ```
4. PR を作成（変更理由と原典 PDF のページ番号を本文に記載）

`raw_text` フィールドは原文保持用なので **原則編集不可**。
構造化フィールド（`points` `notes` `additions` 等）の補正に集中してください。

## スクリプト改修

`scripts/` 配下の改修も歓迎。
正規表現で頑張る方針で書かれているので、誤抽出パターンを issue で報告いただけると助かります。

## 新しい改定版の追加

1. `sources/` に PDF を配置
2. `scripts/build_all.py` の `VERSIONS` に `("rN", "ファイル名.pdf")` を追加
3. `uv run python scripts/build_all.py` を実行
4. 生成された `data/rN/` を commit
