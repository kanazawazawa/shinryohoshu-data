# 区分を探す（フィルタ + CSV ダウンロード）

機械可読 YAML から抽出したメタデータ（現行版 R8 / 全 2,240 区分）を、
**ブラウザ上で絞り込んで CSV / TSV としてダウンロード**できます。
サーバ側の処理は一切なく、すべてあなたのブラウザで完結します。

!!! tip "使い方"
    - **区分コード**: 前方一致（例: `A0` で `A000`〜`A099` をヒット）
    - **名称**: 部分一致（例: `ベースアップ` で外来・在宅・入院の3区分）
    - **章 / 部**: プルダウンで絞り込み
    - **点数**: 範囲指定（空欄なら無制限）
    - 結果テーブルの **チェックボックスで部分選択** → 選択行のみ CSV にすることもできます

<div id="explore-root" markdown="0">
  <div class="explore-toolbar">
    <input type="text" id="f-code" placeholder="区分コード (前方一致)" />
    <input type="text" id="f-name" placeholder="名称 (部分一致)" />
    <select id="f-chapter"><option value="">章: すべて</option></select>
    <select id="f-part"><option value="">部: すべて</option></select>
    <input type="number" id="f-pmin" placeholder="点数 ≧" />
    <input type="number" id="f-pmax" placeholder="点数 ≦" />
    <button type="button" id="f-reset">リセット</button>
  </div>
  <div class="explore-status">
    <span id="hit-count">読み込み中...</span>
    <span class="spacer"></span>
    <label><input type="checkbox" id="select-all" /> 全選択</label>
    <button type="button" id="dl-csv">CSV (UTF-8 BOM)</button>
    <button type="button" id="dl-tsv">TSV</button>
  </div>
  <div class="explore-table-wrap">
    <table id="explore-table">
      <thead>
        <tr>
          <th></th>
          <th>区分</th>
          <th>名称</th>
          <th>点数</th>
          <th>単位</th>
          <th>章</th>
          <th>部</th>
          <th>節</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
</div>

<script src="../assets/explore.js" defer></script>
