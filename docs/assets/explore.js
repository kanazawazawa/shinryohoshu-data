(async function () {
  const root = document.getElementById("explore-root");
  if (!root) return;

  const tbody = root.querySelector("#explore-table tbody");
  const hitCount = root.querySelector("#hit-count");
  const fCode = root.querySelector("#f-code");
  const fName = root.querySelector("#f-name");
  const fChapter = root.querySelector("#f-chapter");
  const fPart = root.querySelector("#f-part");
  const fPmin = root.querySelector("#f-pmin");
  const fPmax = root.querySelector("#f-pmax");
  const fReset = root.querySelector("#f-reset");
  const selectAll = root.querySelector("#select-all");
  const dlCsv = root.querySelector("#dl-csv");
  const dlTsv = root.querySelector("#dl-tsv");

  let DATA = [];
  let VIEW = [];
  const selected = new Set();
  const MAX_ROWS = 500; // 表示は最初の N 件 (CSV は全件出力)

  // データ読み込み
  try {
    const res = await fetch("../assets/items.json");
    const json = await res.json();
    DATA = json.items;
  } catch (e) {
    hitCount.textContent = "データ読み込みに失敗: " + e.message;
    return;
  }

  // プルダウン構築
  const chapters = [...new Set(DATA.map((r) => r.chapter).filter(Boolean))].sort();
  const parts = [...new Set(DATA.map((r) => r.part).filter(Boolean))].sort();
  for (const c of chapters) fChapter.add(new Option(c, c));
  for (const p of parts) fPart.add(new Option(p, p));

  function pointsAsNumber(p) {
    if (typeof p === "number") return p;
    if (typeof p === "string") {
      const m = p.match(/\d+/);
      if (m) return parseInt(m[0], 10);
    }
    return null;
  }

  function applyFilters() {
    const qCode = fCode.value.trim().toUpperCase();
    const qName = fName.value.trim();
    const qChap = fChapter.value;
    const qPart = fPart.value;
    const qPmin = fPmin.value !== "" ? parseInt(fPmin.value, 10) : null;
    const qPmax = fPmax.value !== "" ? parseInt(fPmax.value, 10) : null;

    VIEW = DATA.filter((r) => {
      if (qCode && !r.code.toUpperCase().startsWith(qCode)) return false;
      if (qName && !r.name.includes(qName)) return false;
      if (qChap && r.chapter !== qChap) return false;
      if (qPart && r.part !== qPart) return false;
      if (qPmin !== null || qPmax !== null) {
        const n = pointsAsNumber(r.points);
        if (n === null) return false;
        if (qPmin !== null && n < qPmin) return false;
        if (qPmax !== null && n > qPmax) return false;
      }
      return true;
    });
    render();
  }

  function render() {
    const shown = VIEW.slice(0, MAX_ROWS);
    const truncated = VIEW.length > MAX_ROWS;
    hitCount.innerHTML =
      `<strong>${VIEW.length}</strong> 件ヒット` +
      (truncated ? `（表示は先頭 ${MAX_ROWS} 件まで・CSV は全件）` : "") +
      `／選択 <strong>${selected.size}</strong> 件`;

    const rows = shown
      .map((r) => {
        const checked = selected.has(r.code) ? "checked" : "";
        const pts =
          r.points === null || r.points === undefined
            ? "—"
            : typeof r.points === "number"
            ? `${r.points}点`
            : r.points;
        return (
          `<tr>` +
          `<td><input type="checkbox" data-code="${r.code}" ${checked} class="row-check" /></td>` +
          `<td><a href="${r.url}"><code>${r.code}</code></a></td>` +
          `<td>${escapeHtml(r.name)}</td>` +
          `<td class="num">${pts}</td>` +
          `<td>${escapeHtml(r.unit || "")}</td>` +
          `<td>${escapeHtml(r.chapter || "")}</td>` +
          `<td>${escapeHtml(r.part || "")}</td>` +
          `<td>${escapeHtml(r.section || "")}</td>` +
          `</tr>`
        );
      })
      .join("");
    tbody.innerHTML = rows;
    tbody.querySelectorAll(".row-check").forEach((cb) =>
      cb.addEventListener("change", (e) => {
        const c = e.target.dataset.code;
        if (e.target.checked) selected.add(c);
        else selected.delete(c);
        hitCount.innerHTML = hitCount.innerHTML.replace(
          /選択 <strong>\d+<\/strong>/,
          `選択 <strong>${selected.size}</strong>`
        );
      })
    );
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function toCsvCell(s, sep) {
    const str = s === null || s === undefined ? "" : String(s);
    if (str.includes(sep) || str.includes('"') || str.includes("\n")) {
      return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
  }

  function download(sep, ext, withBom) {
    const rows = selected.size > 0 ? VIEW.filter((r) => selected.has(r.code)) : VIEW;
    const headers = ["code", "name", "points", "unit", "chapter", "part", "section", "url"];
    const lines = [headers.join(sep)];
    for (const r of rows) {
      lines.push(headers.map((h) => toCsvCell(r[h], sep)).join(sep));
    }
    const body = lines.join("\r\n");
    const blob = new Blob(
      withBom ? ["\uFEFF", body] : [body],
      { type: `text/${ext === "csv" ? "csv" : "tab-separated-values"};charset=utf-8` }
    );
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    const ts = new Date().toISOString().slice(0, 10);
    a.download = `shinryohoshu-r8-${ts}-${rows.length}rows.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  }

  // イベント
  [fCode, fName, fPmin, fPmax].forEach((el) =>
    el.addEventListener("input", applyFilters)
  );
  [fChapter, fPart].forEach((el) => el.addEventListener("change", applyFilters));
  fReset.addEventListener("click", () => {
    fCode.value = fName.value = fPmin.value = fPmax.value = "";
    fChapter.value = fPart.value = "";
    selected.clear();
    selectAll.checked = false;
    applyFilters();
  });
  selectAll.addEventListener("change", (e) => {
    if (e.target.checked) {
      for (const r of VIEW) selected.add(r.code);
    } else {
      selected.clear();
    }
    render();
  });
  dlCsv.addEventListener("click", () => download(",", "csv", true));
  dlTsv.addEventListener("click", () => download("\t", "tsv", false));

  applyFilters();
})();
