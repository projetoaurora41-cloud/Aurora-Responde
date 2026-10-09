/* Aurora — dashboard rendering driven by /api/dashboard/<key>/ */
(function () {
  "use strict";

  // Paleta gov.br (azul, laranja, vermelho, amarelo, verde + apoio).
  const PALETTE = [
    "#1351b4", "#e8710a", "#d32f2f", "#e5a50a", "#168821",
    "#0c326f", "#155bcb", "#a9760a", "#b91c1c", "#0d7a3a",
    "#5c6a7a", "#8a5a00"
  ];

  function color(i) { return PALETTE[i % PALETTE.length]; }

  function buildUrl(key) {
    const base = window.AURORA.apiUrl.replace("KEY", encodeURIComponent(key));
    const qs = window.AURORA.filterParams || "";
    return qs ? base + "?" + qs : base;
  }

  function fillTable(key, rows) {
    const table = document.getElementById("table-" + key);
    if (!table || !rows || !rows.length) return;
    const cols = Object.keys(rows[0]);
    table.querySelector("thead").innerHTML =
      "<tr>" + cols.map(c => "<th>" + c + "</th>").join("") + "</tr>";
    table.querySelector("tbody").innerHTML = rows
      .map(r => "<tr>" + cols.map(c => "<td>" + (r[c] ?? "") + "</td>").join("") + "</tr>")
      .join("");
  }

  function makeBarOrLine(canvas, payload, type) {
    const data = payload.data;
    const datasets = (data.datasets || []).map((ds, i) => ({
      label: ds.label,
      data: ds.data,
      backgroundColor: color(i) + (type === "line" ? "33" : "cc"),
      borderColor: color(i),
      borderWidth: 1.5,
      tension: 0.3,
      fill: type === "line"
    }));
    return new Chart(canvas, {
      type: type === "line" ? "line" : "bar",
      data: { labels: data.labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: { y: { beginAtZero: true } }
      }
    });
  }

  function makeStacked(canvas, payload) {
    const data = payload.data;
    const datasets = (data.datasets || []).map((ds, i) => ({
      label: ds.label,
      data: ds.data,
      backgroundColor: color(i) + "cc",
      borderColor: color(i),
      borderWidth: 1
    }));
    return new Chart(canvas, {
      type: "bar",
      data: { labels: data.labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { stacked: true },
          y: { stacked: true, beginAtZero: true }
        }
      }
    });
  }

  function makePyramid(canvas, payload) {
    const data = payload.data;
    return new Chart(canvas, {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: data.datasets.map((ds, i) => ({
          label: ds.label,
          data: ds.data,
          backgroundColor: color(i) + "cc",
          borderColor: color(i),
          borderWidth: 1
        }))
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: {
            ticks: { callback: v => Math.abs(v) },
            beginAtZero: true,
            stacked: true
          },
          y: { stacked: true }
        }
      }
    });
  }

  function makeMulti(canvas, payload, key) {
    // Chooses the largest sub-block to plot; renders the rest inside the table.
    const data = payload.data;
    const blocks = Object.entries(data).filter(([, v]) => v && v.labels && v.data);
    if (!blocks.length) return null;
    blocks.sort((a, b) => (b[1].data.reduce((s, x) => s + (x || 0), 0)) - (a[1].data.reduce((s, x) => s + (x || 0), 0)));
    const [primaryKey, primary] = blocks[0];
    const chart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: primary.labels,
        datasets: [{
          label: primaryKey,
          data: primary.data,
          backgroundColor: PALETTE.map((_, i) => color(i) + "cc"),
          borderColor: PALETTE.map((_, i) => color(i)),
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      }
    });
    // Combine all blocks into a single rows table
    const rows = [];
    for (const [name, block] of blocks) {
      block.labels.forEach((lbl, i) => {
        rows.push({ bloco: name, categoria: lbl, total: block.data[i] });
      });
    }
    fillTable(key, rows);
    return chart;
  }

  async function loadDashboard(meta) {
    const canvas = document.getElementById("chart-" + meta.key);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let payload;
    try {
      const resp = await fetch(buildUrl(meta.key), { headers: { Accept: "application/json" } });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      payload = await resp.json();
    } catch (e) {
      ctx.font = "13px sans-serif";
      ctx.fillStyle = "#64748b";
      ctx.fillText("Falha ao carregar dashboard: " + e.message, 10, 20);
      return;
    }
    const type = (payload.chart || meta.chart || "bar").toLowerCase();
    if (payload.period) {
      const card = canvas.closest(".card-dashboard");
      const periodEl = card && card.querySelector("[data-period]");
      if (periodEl) periodEl.textContent = payload.period;
    }
    if (type === "stacked") {
      makeStacked(canvas, payload);
    } else if (type === "pyramid") {
      makePyramid(canvas, payload);
    } else if (type === "multi") {
      makeMulti(canvas, payload, meta.key);
      return;
    } else if (type === "line") {
      makeBarOrLine(canvas, payload, "line");
    } else {
      makeBarOrLine(canvas, payload, "bar");
    }
    fillTable(meta.key, payload.data && payload.data.rows);
  }

  /* ---------------- Filter sidebar ---------------- */

  function setOptions(select, values, { placeholder, currentValue, formatter } = {}) {
    if (!select) return;
    const fmt = formatter || (v => v);
    const opts = [];
    if (placeholder !== undefined) {
      opts.push(`<option value="">${placeholder}</option>`);
    }
    for (const v of values) {
      opts.push(`<option value="${v}">${fmt(v)}</option>`);
    }
    select.innerHTML = opts.join("");
    if (currentValue) {
      select.value = currentValue;
      // If the requested value isn't in the new option list, fall back to "".
      if (select.value !== currentValue) select.value = "";
    }
  }

  function updateActiveCount() {
    const form = document.getElementById("filter-form");
    const badge = document.getElementById("filter-active-count");
    if (!form || !badge) return;
    let active = 0;
    for (const el of form.elements) {
      if (!el.name) continue;
      if (el.type === "checkbox" && el.checked) active += 1;
      else if (el.type !== "checkbox" && el.value) active += 1;
    }
    badge.textContent = active + (active === 1 ? " ativo" : " ativos");
    badge.className = "badge " + (active ? "bg-primary" : "bg-secondary");
  }

  /** Monta o texto do período a partir dos filtros ou dos anos da base. */
  function formatPeriodLabel(anoInicio, anoFim, availableYears) {
    const ai = (anoInicio || "").trim();
    const af = (anoFim || "").trim();
    if (ai && af) {
      return ai === af ? `Período: ${ai}` : `Período: ${ai}–${af}`;
    }
    if (ai) return `Período: a partir de ${ai}`;
    if (af) return `Período: até ${af}`;

    const years = (availableYears || [])
      .map(String)
      .filter((y) => /^\d{4}$/.test(y))
      .sort();
    if (!years.length) return "Período: não disponível";
    const min = years[0];
    const max = years[years.length - 1];
    return min === max ? `Período: ${min}` : `Período: ${min}–${max}`;
  }

  function updatePeriodLabels(availableYears) {
    const form = document.getElementById("filter-form");
    const ai = form
      ? (document.getElementById("f_ano_inicio")?.value || form.dataset.currentAnoInicio || "")
      : "";
    const af = form
      ? (document.getElementById("f_ano_fim")?.value || form.dataset.currentAnoFim || "")
      : "";
    const text = formatPeriodLabel(ai, af, availableYears);
    document.querySelectorAll("[data-period]").forEach((el) => {
      el.textContent = text;
    });
  }

  async function setupFilters() {
    const form = document.getElementById("filter-form");
    if (!form || !window.AURORA.filterOptionsUrl) {
      updatePeriodLabels([]);
      return;
    }

    const ufSelect = document.getElementById("f_uf");
    const mnSelect = document.getElementById("f_municipio");
    const aiSelect = document.getElementById("f_ano_inicio");
    const afSelect = document.getElementById("f_ano_fim");
    const mnHint = document.getElementById("f_municipio_hint");

    const currentUf = form.dataset.currentUf || "";
    const currentMn = form.dataset.currentMunicipio || "";
    const currentAi = form.dataset.currentAnoInicio || "";
    const currentAf = form.dataset.currentAnoFim || "";

    let opts = { ufs: [], municipios_por_uf: {}, anos: [] };
    try {
      const resp = await fetch(window.AURORA.filterOptionsUrl, { headers: { Accept: "application/json" } });
      if (resp.ok) opts = await resp.json();
    } catch (e) {
      console.warn("Falha ao carregar opções de filtro", e);
    }

    // Render UF select with friendly labels ("SE — Sergipe") when ufs_meta
    // is provided; fall back to the bare list otherwise.
    if (Array.isArray(opts.ufs_meta) && opts.ufs_meta.length) {
      const html = ['<option value="">Todas</option>'];
      for (const u of opts.ufs_meta) {
        const sel = u.sigla === currentUf ? " selected" : "";
        html.push(`<option value="${u.sigla}"${sel}>${u.label}</option>`);
      }
      ufSelect.innerHTML = html.join("");
    } else {
      setOptions(ufSelect, opts.ufs, { placeholder: "Todas", currentValue: currentUf });
    }
    setOptions(aiSelect, opts.anos, { placeholder: "—", currentValue: currentAi });
    setOptions(afSelect, opts.anos, { placeholder: "—", currentValue: currentAf });

    function refreshMunicipios() {
      const uf = ufSelect.value;
      if (!uf) {
        mnSelect.innerHTML = '<option value="">Selecione uma UF primeiro</option>';
        mnSelect.disabled = true;
        if (mnHint) mnHint.textContent = "Lista filtrada conforme a UF.";
        return;
      }
      const items = opts.municipios_por_uf[uf] || [];
      // Backwards-compat: filter_options now returns {codigo, nome, label}
      // objects, but tolerate the old plain-string list.
      const normalized = items.map((m) =>
        typeof m === "string" ? { codigo: m, label: m } : m
      );
      const placeholder = normalized.length
        ? `Todos (${normalized.length})`
        : "Sem dados para esta UF";
      const opts_html = ['<option value="">' + placeholder + '</option>'];
      for (const m of normalized) {
        const sel = m.codigo === currentMn ? " selected" : "";
        opts_html.push(`<option value="${m.codigo}"${sel}>${m.label}</option>`);
      }
      mnSelect.innerHTML = opts_html.join("");
      mnSelect.disabled = !normalized.length;
      if (mnHint) {
        mnHint.textContent = normalized.length
          ? `${normalized.length} município(s) com notificações nesta UF.`
          : "Nenhum município encontrado para esta UF nos dados atuais.";
      }
    }

    refreshMunicipios();
    ufSelect.addEventListener("change", refreshMunicipios);

    form.addEventListener("change", updateActiveCount);
    updateActiveCount();
    updatePeriodLabels(opts.anos || []);
  }

  async function init() {
    await setupFilters();
    if (!window.AURORA || !Array.isArray(window.AURORA.dashboards)) return;
    window.AURORA.dashboards.forEach(loadDashboard);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
