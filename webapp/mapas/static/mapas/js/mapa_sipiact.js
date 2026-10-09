/* Aurora — Mapa coroplético SIPIA-CT (país → estado, sem município). Leaflet. */
(function () {
  "use strict";

  const GEOJSON_URL =
    "https://cdn.jsdelivr.net/gh/codeforgermany/click_that_hood@main/public/data/brazil-states.geojson";

  const STATE_NAME_TO_SIGLA = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM", "Bahia": "BA",
    "Ceará": "CE", "Distrito Federal": "DF", "Espírito Santo": "ES", "Goiás": "GO",
    "Maranhão": "MA", "Mato Grosso": "MT", "Mato Grosso do Sul": "MS",
    "Minas Gerais": "MG", "Pará": "PA", "Paraíba": "PB", "Paraná": "PR",
    "Pernambuco": "PE", "Piauí": "PI", "Rio de Janeiro": "RJ",
    "Rio Grande do Norte": "RN", "Rio Grande do Sul": "RS", "Rondônia": "RO",
    "Roraima": "RR", "Santa Catarina": "SC", "São Paulo": "SP", "Sergipe": "SE",
    "Tocantins": "TO"
  };

  // Rampa vermelha (clara → escura) — igual ao mapa VIOLBR.
  const COLOR_RAMP = [
    "#fef2f2", "#fee2e2", "#fecaca", "#fca5a5", "#f87171",
    "#ef4444", "#dc2626", "#b91c1c", "#7f1d1d"
  ];
  const fmt = n => (n || 0).toLocaleString("pt-BR");

  function buildBreaks(values) {
    const nz = values.filter(v => v > 0).sort((a, b) => a - b);
    if (!nz.length) return [0];
    const buckets = COLOR_RAMP.length - 1, breaks = [];
    for (let i = 1; i <= buckets; i++) {
      const idx = Math.min(nz.length - 1, Math.floor((i / buckets) * nz.length) - 1);
      const v = nz[Math.max(0, idx)];
      if (!breaks.length || v > breaks[breaks.length - 1]) breaks.push(v);
    }
    return breaks;
  }
  function colorFor(v, breaks) {
    if (!v) return COLOR_RAMP[0];
    for (let i = 0; i < breaks.length; i++)
      if (v <= breaks[i]) return COLOR_RAMP[i + 1] || COLOR_RAMP[COLOR_RAMP.length - 1];
    return COLOR_RAMP[COLOR_RAMP.length - 1];
  }

  const setProgress = (p, l) => {
    const b = document.getElementById("map-loading-bar");
    const t = document.getElementById("map-loading-label");
    if (b) { const v = Math.max(0, Math.min(100, p)); b.style.width = v + "%"; b.setAttribute("aria-valuenow", String(Math.round(v))); }
    if (t && l) t.textContent = l;
  };
  const hideLoading = () => { const el = document.getElementById("map-loading"); if (el) el.remove(); };
  const showError = m => {
    const t = document.getElementById("map-loading-label");
    const b = document.getElementById("map-loading-bar");
    if (t) t.textContent = m;
    if (b) { b.classList.remove("bg-primary", "progress-bar-animated"); b.classList.add("bg-danger"); b.style.width = "100%"; }
  };

  let map, geo, geoLayer = null, totals = {}, grand = 0, breaks = [0], info;

  function styleState(f) {
    const s = STATE_NAME_TO_SIGLA[f.properties.name] || "";
    const t = totals[s] || 0;
    return { fillColor: colorFor(t, breaks), weight: 1, color: "#1e293b", opacity: .6, fillOpacity: t ? .85 : .35 };
  }

  function renderLayer() {
    if (geoLayer) { map.removeLayer(geoLayer); geoLayer = null; }
    geoLayer = L.geoJSON(geo, {
      style: styleState,
      onEachFeature: (f, layer) => {
        const s = STATE_NAME_TO_SIGLA[f.properties.name] || "";
        const t = totals[s] || 0;
        layer.bindTooltip(`<strong>${f.properties.name}</strong><br>${fmt(t)} registros`, { sticky: true });
        layer.on({
          mouseover: e => { e.target.setStyle({ weight: 2.5, color: "#0f172a", fillOpacity: .95 }); e.target.bringToFront(); info.update(f.properties); },
          mouseout: e => { geoLayer.resetStyle(e.target); info.update(); },
          click: () => {
            const pct = grand ? ((t / grand) * 100).toFixed(1) : "0.0";
            const card = document.getElementById("detail-card"); card.hidden = false;
            document.getElementById("detail-title").textContent = "Estado — " + (s || f.properties.name);
            document.getElementById("detail-total").textContent = fmt(t) + " registros";
            document.getElementById("detail-pct").textContent = pct + "% do total nacional";
          }
        });
      }
    }).addTo(map);
    updateLegend();
  }

  let legendCtrl = null;
  function updateLegend() {
    if (legendCtrl) map.removeControl(legendCtrl);
    legendCtrl = L.control({ position: "bottomright" });
    legendCtrl.onAdd = function () {
      const div = L.DomUtil.create("div", "map-legend");
      const labels = [`<i style="background:${COLOR_RAMP[0]}"></i>Sem dados / 0`];
      let prev = 0;
      for (let i = 0; i < breaks.length; i++) {
        const bg = COLOR_RAMP[i + 1] || COLOR_RAMP[COLOR_RAMP.length - 1];
        labels.push(`<i style="background:${bg}"></i>${fmt(i === 0 ? 1 : prev + 1)}–${fmt(breaks[i])}`);
        prev = breaks[i];
      }
      div.innerHTML = "<strong>Registros SIPIA-CT</strong><br>" + labels.join("<br>");
      return div;
    };
    legendCtrl.addTo(map);
  }

  async function refresh() {
    const indicador = document.getElementById("f_indicador").value;
    const ano = document.getElementById("f_ano").value;
    const note = document.getElementById("sipiact-note");
    if (note) note.textContent = "Carregando…";
    const url = window.MAPAS.ufUrl + "?indicador=" + encodeURIComponent(indicador) +
      (ano ? "&ano=" + encodeURIComponent(ano) : "");
    let payload;
    try {
      payload = await fetch(url, { headers: { Accept: "application/json" } }).then(r => r.json());
      if (payload.error) throw new Error(payload.error);
    } catch (e) { if (note) note.textContent = "Erro: " + e.message; return; }
    totals = payload.totals || {}; grand = payload.grand || 0;
    breaks = buildBreaks(Object.values(totals));
    renderLayer();
    if (note) note.textContent = `${Object.keys(totals).length} estados · ${fmt(grand)} registros no total.`;
    document.getElementById("detail-card").hidden = true;
  }

  async function init() {
    setProgress(10, "Carregando filtros…");
    let filtros = { indicadores: [], anos: [] };
    try { filtros = await fetch(window.MAPAS.filtrosUrl, { headers: { Accept: "application/json" } }).then(r => r.json()); }
    catch (e) { console.warn(e); }

    const indSel = document.getElementById("f_indicador");
    indSel.innerHTML = (filtros.indicadores || []).map(i => `<option value="${i}">${i}</option>`).join("");
    const anoSel = document.getElementById("f_ano");
    anoSel.innerHTML = '<option value="">Todos os anos</option>' +
      (filtros.anos || []).map(a => `<option value="${a}">${a}</option>`).join("");

    setProgress(35, "Inicializando mapa…");
    if (typeof L === "undefined") { showError("Leaflet não carregou."); return; }
    map = L.map("sipiact-map", { scrollWheelZoom: true }).setView([-14.6, -53.0], 4);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18, attribution: "© OpenStreetMap contributors"
    }).addTo(map);

    info = L.control({ position: "topright" });
    info.onAdd = function () { this._div = L.DomUtil.create("div", "map-info"); this.update(); return this._div; };
    info.update = function (props) {
      if (!props) { this._div.innerHTML = "<h6>Brasil</h6><div class='small text-muted'>Passe o mouse sobre um estado.</div>"; return; }
      const s = STATE_NAME_TO_SIGLA[props.name] || ""; const t = totals[s] || 0;
      const pct = grand ? ((t / grand) * 100).toFixed(1) : "0.0";
      this._div.innerHTML = `<h6>${props.name} (${s || "—"})</h6>
        <div class="uf-total">${fmt(t)} registros</div>
        <div class="small text-muted">${pct}% do total nacional</div>`;
    };
    info.addTo(map);

    setProgress(65, "Carregando contornos do Brasil…");
    try { geo = await fetch(GEOJSON_URL).then(r => r.json()); }
    catch (e) { showError("Falha ao carregar mapa: " + e.message); return; }

    await refresh();
    map.fitBounds(geoLayer.getBounds(), { padding: [10, 10] });
    indSel.addEventListener("change", refresh);
    anoSel.addEventListener("change", refresh);
    setProgress(100, "Pronto"); hideLoading();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
