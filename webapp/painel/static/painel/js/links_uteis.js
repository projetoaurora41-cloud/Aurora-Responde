/** Busca client-side na página Links Úteis (normaliza acentos). */
(function () {
  "use strict";

  function normalizar(s) {
    return String(s || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();
  }

  var input = document.getElementById("links-busca-input");
  var emptyEl = document.getElementById("links-empty");
  if (!input || !emptyEl) return;

  var categorias = Array.prototype.slice.call(
    document.querySelectorAll("[data-categoria]")
  );

  function filtrar() {
    var q = normalizar(input.value.trim());
    var algumaVisivel = false;

    categorias.forEach(function (sec) {
      var itens = Array.prototype.slice.call(
        sec.querySelectorAll("[data-recurso]")
      );
      var visiveis = 0;

      itens.forEach(function (item) {
        var texto = normalizar(item.getAttribute("data-search") || "");
        var match = !q || texto.indexOf(q) !== -1;
        item.hidden = !match;
        if (match) visiveis += 1;
      });

      sec.hidden = visiveis === 0;
      if (visiveis > 0) algumaVisivel = true;
    });

    if (!algumaVisivel && q) {
      emptyEl.hidden = false;
      emptyEl.textContent =
        'Nenhum link encontrado para "' + input.value.trim() + '".';
    } else {
      emptyEl.hidden = true;
      emptyEl.textContent = "";
    }
  }

  input.addEventListener("input", filtrar);
})();
