# 区分を探す（フィルタ + CSV ダウンロード）

機械可読 YAML から抽出したデータを、**ブラウザ上で絞り込んで CSV / TSV としてダウンロード**できます。
サーバ側の処理は一切なく、すべてあなたのブラウザで完結します（追加サービス・課金なし）。

!!! tip "使い方"
    - **版**: R6 / R8 / 両方を切替（既定は両方表示）
    - **改定**: 「新設 / 削除 / 変更 / 変化なし」で絞り込み
    - **区分コード**: 前方一致（例: `A0` で `A000`〜`A099`）
    - **名称**: 部分一致。「**原文も検索**」をオンにすると `raw_text` 本文も対象になります
    - **章 / 部**: プルダウン、**点数**: 範囲（空欄で無制限）
    - **行のチェックで部分選択** → 選択行だけ CSV にできます（未選択時は絞り込み結果すべて）

!!! note "CSV に含まれる列"
    `version, code, diff_status, name, points, unit, chapter, part, section, subsection, notes_count, tiers_count, source_pdf, source_url, page_url, raw_text`

<div id="explore-root" markdown="0">
  <div class="explore-toolbar">
    <select id="f-version">
      <option value="">版: 両方</option>
      <option value="r8">R8 のみ</option>
      <option value="r6">R6 のみ</option>
    </select>
    <select id="f-diff">
      <option value="">改定: すべて</option>
      <option value="added">新設 (R8)</option>
      <option value="deleted">削除 (R8)</option>
      <option value="changed">変更</option>
      <option value="unchanged">変化なし</option>
    </select>
    <input type="text" id="f-code" placeholder="区分コード (前方一致)" />
    <input type="text" id="f-name" placeholder="名称 (部分一致)" />
    <label class="chk"><input type="checkbox" id="f-fulltext" /> 原文も検索</label>
    <select id="f-chapter"><option value="">章: すべて</option></select>
    <select id="f-part"><option value="">部: すべて</option></select>
    <input type="number" id="f-pmin" placeholder="点数 ≧" />
    <input type="number" id="f-pmax" placeholder="点数 ≦" />
    <button type="button" id="f-reset">リセット</button>
  </div>
  <div class="explore-status">
    <span id="hit-count">読み込み中...</span>
    <span class="spacer"></span>
    <label class="chk"><input type="checkbox" id="select-all" /> 全選択</label>
    <button type="button" id="dl-csv">CSV (UTF-8 BOM)</button>
    <button type="button" id="dl-tsv">TSV</button>
  </div>
  <div class="explore-table-wrap">
    <table id="explore-table">
      <thead>
        <tr>
          <th></th>
          <th>版</th>
          <th>改定</th>
          <th>区分</th>
          <th>名称</th>
          <th>点数</th>
          <th>単位</th>
          <th>章</th>
          <th>部</th>
          <th>節</th>
          <th>注数</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
</div>

<script src="../assets/explore.js" defer></script>
