/** Busca client-side na página Perguntas Frequentes (normaliza acentos). */
(function () {
  "use strict";

  function normalizar(s) {
    return String(s || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();
  }

  var input = document.getElementById("faq-busca-input");
  var emptyEl = document.getElementById("faq-empty");
  if (!input || !emptyEl) return;

  var eixos = Array.prototype.slice.call(
    document.querySelectorAll("[data-eixo]")
  );

  function filtrar() {
    var q = normalizar(input.value.trim());
    var algumaVisivel = false;

    eixos.forEach(function (sec) {
      var itens = Array.prototype.slice.call(
        sec.querySelectorAll("[data-faq-item]")
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
        'Nenhuma pergunta encontrada para "' + input.value.trim() + '".';
    } else {
      emptyEl.hidden = true;
      emptyEl.textContent = "";
    }
  }

  input.addEventListener("input", filtrar);
})();
