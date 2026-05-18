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
  const fVersion = root.querySelector("#f-version");
  const fDiff = root.querySelector("#f-diff");
  const fFulltext = root.querySelector("#f-fulltext");
  const fReset = root.querySelector("#f-reset");
  const selectAll = root.querySelector("#select-all");
  const dlCsv = root.querySelector("#dl-csv");
  const dlTsv = root.querySelector("#dl-tsv");

  let DATA = [];
  let VIEW = [];
  const selected = new Set();
  const MAX_ROWS = 500;

  hitCount.textContent = "読み込み中...";
  try {
    const res = await fetch("../assets/items.json");
    const json = await res.json();
    DATA = json.items;
  } catch (e) {
    hitCount.textContent = "データ読み込みに失敗: " + e.message;
    return;
  }

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
    const qVer = fVersion.value;
    const qDiff = fDiff.value;
    const qFull = fFulltext.checked;

    VIEW = DATA.filter((r) => {
      if (qVer && r.version !== qVer) return false;
      if (qDiff && r.diff_status !== qDiff) return false;
      if (qCode && !r.code.toUpperCase().startsWith(qCode)) return false;
      if (qName) {
        const hay = qFull ? r.name + "\n" + r.raw_text : r.name;
        if (!hay.includes(qName)) return false;
      }
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

  const DIFF_LABEL = {
    added: { txt: "新設", cls: "diff-added" },
    deleted: { txt: "削除", cls: "diff-deleted" },
    changed: { txt: "変更", cls: "diff-changed" },
    unchanged: { txt: "—", cls: "diff-unchanged" },
  };

  function render() {
    const shown = VIEW.slice(0, MAX_ROWS);
    const truncated = VIEW.length > MAX_ROWS;
    hitCount.innerHTML =
      `<strong>${VIEW.length}</strong> 件ヒット` +
      (truncated ? `（表示は先頭 ${MAX_ROWS} 件・CSV は全件）` : "") +
      `／選択 <strong>${selected.size}</strong>`;

    const rows = shown
      .map((r) => {
        const key = `${r.version}|${r.code}`;
        const checked = selected.has(key) ? "checked" : "";
        const pts =
          r.points === null || r.points === undefined
            ? "—"
            : typeof r.points === "number"
            ? `${r.points}点`
            : r.points;
        const d = DIFF_LABEL[r.diff_status] || DIFF_LABEL.unchanged;
        return (
          `<tr>` +
          `<td><input type="checkbox" data-key="${key}" ${checked} class="row-check" /></td>` +
          `<td>${r.version.toUpperCase()}</td>` +
          `<td><span class="diff-badge ${d.cls}">${d.txt}</span></td>` +
          `<td><a href="${r.page_url}"><code>${r.code}</code></a></td>` +
          `<td>${escapeHtml(r.name)}</td>` +
          `<td class="num">${pts}</td>` +
          `<td>${escapeHtml(r.unit || "")}</td>` +
          `<td>${escapeHtml(r.chapter || "")}</td>` +
          `<td>${escapeHtml(r.part || "")}</td>` +
          `<td>${escapeHtml(r.section || "")}</td>` +
          `<td class="num">${r.notes_count}</td>` +
          `</tr>`
        );
      })
      .join("");
    tbody.innerHTML = rows;
    tbody.querySelectorAll(".row-check").forEach((cb) =>
      cb.addEventListener("change", (e) => {
        const k = e.target.dataset.key;
        if (e.target.checked) selected.add(k);
        else selected.delete(k);
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
    if (str.includes(sep) || str.includes('"') || str.includes("\n") || str.includes("\r")) {
      return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
  }

  function download(sep, ext, withBom) {
    const rows =
      selected.size > 0
        ? VIEW.filter((r) => selected.has(`${r.version}|${r.code}`))
        : VIEW;
    const headers = [
      "version",
      "code",
      "diff_status",
      "name",
      "points",
      "unit",
      "chapter",
      "part",
      "section",
      "subsection",
      "notes_count",
      "tiers_count",
      "source_pdf",
      "source_url",
      "page_url",
      "raw_text",
    ];
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
    a.download = `shinryohoshu-${ts}-${rows.length}rows.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  }

  [fCode, fName, fPmin, fPmax].forEach((el) =>
    el.addEventListener("input", applyFilters)
  );
  [fChapter, fPart, fVersion, fDiff].forEach((el) =>
    el.addEventListener("change", applyFilters)
  );
  fFulltext.addEventListener("change", applyFilters);
  fReset.addEventListener("click", () => {
    fCode.value = fName.value = fPmin.value = fPmax.value = "";
    fChapter.value = fPart.value = fVersion.value = fDiff.value = "";
    fFulltext.checked = false;
    selected.clear();
    selectAll.checked = false;
    applyFilters();
  });
  selectAll.addEventListener("change", (e) => {
    if (e.target.checked) {
      for (const r of VIEW) selected.add(`${r.version}|${r.code}`);
    } else {
      selected.clear();
    }
    render();
  });
  dlCsv.addEventListener("click", () => download(",", "csv", true));
  dlTsv.addEventListener("click", () => download("\t", "tsv", false));

  applyFilters();
})();
