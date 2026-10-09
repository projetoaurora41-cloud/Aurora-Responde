/* Aurora — Choropleth map of Brazil by UF (Leaflet). */
(function () {
  "use strict";

  const GEOJSON_URL =
    "https://cdn.jsdelivr.net/gh/codeforgermany/click_that_hood@main/public/data/brazil-states.geojson";

  // IBGE Malhas v3 — returns a GeoJSON FeatureCollection of all municipalities
  // of a state. `codarea` on each feature is the 7-digit IBGE code; SINAN
  // stores the same code without the check digit, so we trim to 6 digits.
  function municipiosGeoJsonUrl(sigla) {
    return (
      "https://servicodados.ibge.gov.br/api/v3/malhas/estados/" +
      encodeURIComponent(sigla) +
      "?formato=application/vnd.geo+json&qualidade=intermediaria&intrarregiao=municipio"
    );
  }

  // Map full state name (as used in the GeoJSON `name` property) → 2-letter sigla.
  const STATE_NAME_TO_SIGLA = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM",
    "Bahia": "BA", "Ceará": "CE", "Distrito Federal": "DF",
    "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA",
    "Mato Grosso": "MT", "Mato Grosso do Sul": "MS", "Minas Gerais": "MG",
    "Pará": "PA", "Paraíba": "PB", "Paraná": "PR", "Pernambuco": "PE",
    "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN",
    "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR",
    "Santa Catarina": "SC", "São Paulo": "SP", "Sergipe": "SE",
    "Tocantins": "TO"
  };

  // Numeric IBGE UF code → sigla (mirrors the server-side mapping).
  const UF_NUM_TO_SIGLA = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF"
  };

  // Color ramp (light → dark), used to bin per-state totals into a choropleth.
  const COLOR_RAMP = [
    "#fef2f2", "#fee2e2", "#fecaca", "#fca5a5", "#f87171",
    "#ef4444", "#dc2626", "#b91c1c", "#7f1d1d"
  ];

  function siglaFromUf(value) {
    if (!value) return "";
    const v = String(value).trim().toUpperCase();
    return UF_NUM_TO_SIGLA[v] || v;
  }

  function buildApiUrl(key) {
    const base = window.AURORA.apiUrl.replace("KEY", encodeURIComponent(key));
    const qs = window.AURORA.filterParams || "";
    return qs ? base + "?" + qs : base;
  }

  function buildBreaks(values) {
    // Quantile breaks across non-zero totals so a few outliers don't flatten
    // the colour scale into one bucket.
    const nonZero = values.filter(v => v > 0).sort((a, b) => a - b);
    if (!nonZero.length) return [0];
    const buckets = COLOR_RAMP.length - 1;
    const breaks = [];
    for (let i = 1; i <= buckets; i++) {
      const idx = Math.min(nonZero.length - 1, Math.floor((i / buckets) * nonZero.length) - 1);
      const v = nonZero[Math.max(0, idx)];
      if (!breaks.length || v > breaks[breaks.length - 1]) breaks.push(v);
    }
    return breaks;
  }

  function colorFor(value, breaks) {
    if (!value) return COLOR_RAMP[0];
    for (let i = 0; i < breaks.length; i++) {
      if (value <= breaks[i]) return COLOR_RAMP[i + 1] || COLOR_RAMP[COLOR_RAMP.length - 1];
    }
    return COLOR_RAMP[COLOR_RAMP.length - 1];
  }

  function styleForFeature(feature, totalsBySigla, breaks) {
    const sigla = STATE_NAME_TO_SIGLA[feature.properties.name] || "";
    const total = totalsBySigla[sigla] || 0;
    return {
      fillColor: colorFor(total, breaks),
      weight: 1,
      color: "#1e293b",
      opacity: 0.6,
      fillOpacity: total ? 0.85 : 0.35
    };
  }

  function fmt(n) {
    return (n || 0).toLocaleString("pt-BR");
  }

  // -------- Filter sidebar (mirrors dashboards.js, simplified). -------- //

  function setOptions(select, values, { placeholder, currentValue } = {}) {
    if (!select) return;
    const opts = [];
    if (placeholder !== undefined) opts.push(`<option value="">${placeholder}</option>`);
    for (const v of values) opts.push(`<option value="${v}">${v}</option>`);
    select.innerHTML = opts.join("");
    if (currentValue) {
      select.value = currentValue;
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

  async function setupFilters() {
    const form = document.getElementById("filter-form");
    if (!form || !window.AURORA.filterOptionsUrl) return;
    const ufSelect = document.getElementById("f_uf");
    const aiSelect = document.getElementById("f_ano_inicio");
    const afSelect = document.getElementById("f_ano_fim");
    const currentUf = form.dataset.currentUf || "";
    const currentAi = form.dataset.currentAnoInicio || "";
    const currentAf = form.dataset.currentAnoFim || "";

    let opts = { ufs: [], anos: [] };
    try {
      const resp = await fetch(window.AURORA.filterOptionsUrl, { headers: { Accept: "application/json" } });
      if (resp.ok) opts = await resp.json();
    } catch (e) {
      console.warn("Falha ao carregar opções de filtro", e);
    }

    if (Array.isArray(opts.ufs_meta) && opts.ufs_meta.length) {
      const html = ['<option value="">Todas</option>'];
      for (const u of opts.ufs_meta) {
        const sel = u.sigla === currentUf ? " selected" : "";
        html.push(`<option value="${u.sigla}"${sel}>${u.label}</option>`);
      }
      ufSelect.innerHTML = html.join("");
    } else {
      setOptions(ufSelect, opts.ufs || [], { placeholder: "Todas", currentValue: currentUf });
    }
    setOptions(aiSelect, opts.anos || [], { placeholder: "—", currentValue: currentAi });
    setOptions(afSelect, opts.anos || [], { placeholder: "—", currentValue: currentAf });

    form.addEventListener("change", updateActiveCount);
    updateActiveCount();
  }

  // -------- Map rendering -------- //

  async function fetchUfTotals() {
    const resp = await fetch(buildApiUrl("uf_map"), { headers: { Accept: "application/json" } });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const payload = await resp.json();
    const rows = (payload.data && payload.data.rows) || [];
    const totals = {};
    let grand = 0;
    for (const r of rows) {
      const sigla = siglaFromUf(r.uf);
      if (!sigla) continue;
      totals[sigla] = {
        sigla,
        total: r.total || 0,
        violencia_sexual: r.violencia_sexual || 0,
        trafico: r.trafico || 0,
        exploracao_sexual: r.exploracao_sexual || 0
      };
      grand += r.total || 0;
    }
    return { totals, grand };
  }

  async function fetchGeoJson() {
    const resp = await fetch(GEOJSON_URL);
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return resp.json();
  }

  function setProgress(pct, label) {
    const bar = document.getElementById("map-loading-bar");
    const lbl = document.getElementById("map-loading-label");
    if (bar) {
      const v = Math.max(0, Math.min(100, Math.round(pct)));
      bar.style.width = v + "%";
      bar.setAttribute("aria-valuenow", String(v));
    }
    if (lbl && label) lbl.textContent = label;
  }

  function showError(msg) {
    const el = document.getElementById("map-loading");
    const lbl = document.getElementById("map-loading-label");
    const bar = document.getElementById("map-loading-bar");
    if (lbl) lbl.textContent = msg;
    if (bar) {
      bar.classList.remove("progress-bar-animated", "progress-bar-striped", "bg-primary");
      bar.classList.add("bg-danger");
      bar.style.width = "100%";
    }
    if (el) el.style.color = "#b91c1c";
  }

  function hideLoading() {
    const el = document.getElementById("map-loading");
    if (el) el.remove();
  }

  function setDetailCard({ title, total, pctLabel, rows, hint, showBack }) {
    const card = document.getElementById("uf-detail-card");
    if (!card) return;
    card.hidden = false;
    document.getElementById("uf-detail-title").textContent = title;
    document.getElementById("uf-detail-total").textContent = fmt(total);
    document.getElementById("uf-detail-pct").textContent = pctLabel || "";
    document.getElementById("uf-detail-grid").innerHTML = rows
      .map(([l, v]) => `<div class="label">${l}</div><div class="value">${fmt(v)}</div>`)
      .join("");
    const hintEl = document.getElementById("uf-detail-hint");
    if (hintEl) {
      hintEl.textContent = hint || "";
      hintEl.hidden = !hint;
    }
    const backBtn = document.getElementById("btn-back-to-state");
    if (backBtn) backBtn.hidden = !showBack;
  }

  function showUfDetail(sigla, info, grand) {
    const data = info || { total: 0, violencia_sexual: 0, trafico: 0, exploracao_sexual: 0 };
    const pct = grand ? ((data.total / grand) * 100).toFixed(1) : "0.0";
    setDetailCard({
      title: "Detalhes — " + sigla,
      total: data.total,
      pctLabel: pct + "% do total nacional",
      rows: [
        ["Violência sexual", data.violencia_sexual],
        ["Tráfico", data.trafico],
        ["Exploração sexual", data.exploracao_sexual]
      ],
      hint: "Clique em um município para ver os detalhes locais.",
      showBack: false
    });
  }

  function showMunicipioDetail(name, sigla, data, ufTotal) {
    const total = (data && data.total) || 0;
    const pct = ufTotal ? ((total / ufTotal) * 100).toFixed(1) : "0.0";
    setDetailCard({
      title: `${name} (${sigla})`,
      total,
      pctLabel: pct + "% do total da UF",
      rows: [
        ["Violência sexual", (data && data.violencia_sexual) || 0],
        ["Tráfico", (data && data.trafico) || 0],
        ["Exploração sexual", (data && data.exploracao_sexual) || 0]
      ],
      hint: "",
      showBack: true
    });
  }

  function clearUfDetail() {
    const card = document.getElementById("uf-detail-card");
    if (card) card.hidden = true;
  }

  async function fetchMunicipiosTotals(sigla) {
    const base = window.AURORA.municipiosUrl.replace("UF", encodeURIComponent(sigla));
    const qs = window.AURORA.filterParams || "";
    const url = qs ? base + "?" + qs : base;
    const resp = await fetch(url, { headers: { Accept: "application/json" } });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return resp.json();
  }

  async function fetchMunicipiosGeoJson(sigla) {
    const resp = await fetch(municipiosGeoJsonUrl(sigla));
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return resp.json();
  }

  async function init() {
    setProgress(5, "Carregando filtros…");
    await setupFilters();
    setProgress(15, "Inicializando mapa…");

    if (typeof L === "undefined") {
      // Leaflet is loaded with `defer` from a CDN; if it failed, surface that.
      showError("Leaflet não pôde ser carregado. Verifique a conexão.");
      return;
    }

    const map = L.map("aurora-map", {
      zoomControl: true,
      scrollWheelZoom: true,
      worldCopyJump: false
    }).setView([-14.6, -53.0], 4);

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "© OpenStreetMap contributors"
    }).addTo(map);

    setProgress(30, "Buscando notificações por UF…");
    let totals = {};
    let grand = 0;
    let geo;
    try {
      const totalsP = fetchUfTotals().then(r => { setProgress(60, "Carregando contornos do Brasil…"); return r; });
      const geoP = fetchGeoJson().then(r => { setProgress(80, "Renderizando mapa…"); return r; });
      [{ totals, grand }, geo] = await Promise.all([totalsP, geoP]);
    } catch (e) {
      console.error(e);
      showError("Falha ao carregar dados do mapa: " + e.message);
      return;
    }

    const totalsBySigla = {};
    for (const [sigla, info] of Object.entries(totals)) totalsBySigla[sigla] = info.total;
    const breaks = buildBreaks(Object.values(totalsBySigla));

    const info = L.control({ position: "topright" });
    info.onAdd = function () {
      this._div = L.DomUtil.create("div", "map-info");
      this.update();
      return this._div;
    };
    info.update = function (props, total) {
      if (!props) {
        this._div.innerHTML = "<h6>Brasil</h6><div class='small text-muted'>Passe o mouse sobre um estado.</div>";
        return;
      }
      const sigla = STATE_NAME_TO_SIGLA[props.name] || "";
      const data = totals[sigla] || { total: 0, violencia_sexual: 0, trafico: 0, exploracao_sexual: 0 };
      const pct = grand ? ((data.total / grand) * 100).toFixed(1) : "0.0";
      this._div.innerHTML = `
        <h6>${props.name} (${sigla || "—"})</h6>
        <div class="uf-total">${fmt(data.total)} notificações</div>
        <div class="text-muted small mb-1">${pct}% do total nacional</div>
        <div class="uf-row"><span>Violência sexual</span><span>${fmt(data.violencia_sexual)}</span></div>
        <div class="uf-row"><span>Tráfico</span><span>${fmt(data.trafico)}</span></div>
        <div class="uf-row"><span>Exploração sexual</span><span>${fmt(data.exploracao_sexual)}</span></div>
      `;
    };
    info.addTo(map);

    let geoLayer;
    let muniLayer = null;       // currently rendered municipalities GeoJSON layer
    let muniData = null;        // { uf, total, municipios: { codigo: {...} } }

    function highlightFeature(e) {
      if (muniLayer) return;     // ignore state-hover while drilled into a state
      const layer = e.target;
      layer.setStyle({ weight: 2.5, color: "#0f172a", fillOpacity: 0.95 });
      layer.bringToFront();
      info.update(layer.feature.properties);
    }
    function resetHighlight(e) {
      if (muniLayer) return;
      geoLayer.resetStyle(e.target);
      info.update();
    }
    function zoomToFeature(e) {
      const layer = e.target;
      const sigla = STATE_NAME_TO_SIGLA[layer.feature.properties.name] || "";
      map.fitBounds(layer.getBounds(), { padding: [20, 20] });
      showUfDetail(sigla, totals[sigla], grand);
      if (sigla) enterStateMode(sigla, layer.getBounds());
    }

    async function enterStateMode(sigla, bounds) {
      removeMuniLayer();
      const hint = document.getElementById("uf-detail-hint");
      if (hint) {
        hint.textContent = "Carregando municípios...";
        hint.hidden = false;
      }
      let totalsResp, geoResp;
      try {
        [totalsResp, geoResp] = await Promise.all([
          fetchMunicipiosTotals(sigla),
          fetchMunicipiosGeoJson(sigla)
        ]);
      } catch (e) {
        console.error(e);
        if (hint) hint.textContent = "Falha ao carregar municípios: " + e.message;
        return;
      }
      muniData = totalsResp;

      const totalsByCode = {};
      const allTotals = [];
      for (const code in totalsResp.municipios) {
        const t = totalsResp.municipios[code].total;
        totalsByCode[code] = t;
        allTotals.push(t);
      }
      const muniBreaks = buildBreaks(allTotals);

      // Dim the Brazil layer so the muni boundaries pop visually.
      geoLayer.setStyle({ fillOpacity: 0.1, opacity: 0.3 });

      muniLayer = L.geoJSON(geoResp, {
        style: f => {
          // codarea is a string like "2800308" (7 digits); SINAN uses 6.
          const code6 = String(f.properties.codarea || "").slice(0, 6);
          const total = totalsByCode[code6] || 0;
          return {
            fillColor: colorFor(total, muniBreaks),
            weight: 0.6,
            color: "#0f172a",
            opacity: 0.7,
            fillOpacity: total ? 0.85 : 0.25
          };
        },
        onEachFeature: (feature, layer) => {
          const code6 = String(feature.properties.codarea || "").slice(0, 6);
          const data = totalsResp.municipios[code6];
          const name = (data && data.nome) || code6 || "Município";
          layer.bindTooltip(
            `<strong>${name}</strong><br>${fmt((data && data.total) || 0)} notificações`,
            { sticky: true }
          );
          layer.on({
            mouseover: (e) => {
              e.target.setStyle({ weight: 2, color: "#0f172a", fillOpacity: 0.95 });
              e.target.bringToFront();
              info.update({ name }, (data && data.total) || 0);
              info._div.innerHTML = `
                <h6>${name} (${sigla})</h6>
                <div class="uf-total">${fmt((data && data.total) || 0)} notificações</div>
                <div class="uf-row"><span>Violência sexual</span><span>${fmt((data && data.violencia_sexual) || 0)}</span></div>
                <div class="uf-row"><span>Tráfico</span><span>${fmt((data && data.trafico) || 0)}</span></div>
                <div class="uf-row"><span>Exploração sexual</span><span>${fmt((data && data.exploracao_sexual) || 0)}</span></div>
              `;
            },
            mouseout: (e) => muniLayer.resetStyle(e.target),
            click: (e) => {
              map.fitBounds(e.target.getBounds(), { padding: [20, 20] });
              showMunicipioDetail(name, sigla, data, totalsResp.total);
            }
          });
        }
      }).addTo(map);

      if (bounds) map.fitBounds(bounds, { padding: [20, 20] });
      if (hint) {
        hint.textContent = "Clique em um município para ver os detalhes locais.";
        hint.hidden = false;
      }
    }

    function removeMuniLayer() {
      if (muniLayer) {
        map.removeLayer(muniLayer);
        muniLayer = null;
        muniData = null;
        geoLayer.setStyle(f => styleForFeature(f, totalsBySigla, breaks));
      }
    }

    function exitStateMode() {
      removeMuniLayer();
      map.fitBounds(geoLayer.getBounds(), { padding: [10, 10] });
      clearUfDetail();
    }

    geoLayer = L.geoJSON(geo, {
      style: f => styleForFeature(f, totalsBySigla, breaks),
      onEachFeature: (feature, layer) => {
        const sigla = STATE_NAME_TO_SIGLA[feature.properties.name] || "";
        const data = totals[sigla] || { total: 0 };
        layer.bindTooltip(
          `<strong>${feature.properties.name}</strong><br>${fmt(data.total)} notificações`,
          { sticky: true }
        );
        layer.on({
          mouseover: highlightFeature,
          mouseout: resetHighlight,
          click: zoomToFeature
        });
      }
    }).addTo(map);

    map.fitBounds(geoLayer.getBounds(), { padding: [10, 10] });

    // Legend
    const legend = L.control({ position: "bottomright" });
    legend.onAdd = function () {
      const div = L.DomUtil.create("div", "map-legend");
      let html = "<strong>Notificações</strong><br>";
      const labels = [];
      labels.push(`<i style="background:${COLOR_RAMP[0]}"></i>Sem dados / 0`);
      let prev = 0;
      for (let i = 0; i < breaks.length; i++) {
        const bg = COLOR_RAMP[i + 1] || COLOR_RAMP[COLOR_RAMP.length - 1];
        const lo = i === 0 ? 1 : prev + 1;
        const hi = breaks[i];
        labels.push(`<i style="background:${bg}"></i>${fmt(lo)}–${fmt(hi)}`);
        prev = hi;
      }
      div.innerHTML = html + labels.join("<br>");
      return div;
    };
    legend.addTo(map);

    setProgress(100, "Pronto");
    document.getElementById("btn-reset-zoom").addEventListener("click", exitStateMode);
    document.getElementById("btn-clear-selection").addEventListener("click", exitStateMode);
    const backBtn = document.getElementById("btn-back-to-state");
    if (backBtn) {
      backBtn.addEventListener("click", () => {
        if (muniData && muniLayer) {
          map.fitBounds(muniLayer.getBounds(), { padding: [20, 20] });
          showUfDetail(muniData.uf, totals[muniData.uf], grand);
        }
      });
    }

    hideLoading();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
