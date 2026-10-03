/* Funcionalidades universais de chat, compartilhadas por todos os chats do Aurora.
   Auto-detecta o layout (orquestrador/dados_sinam usam .msg; datas usam .chat-bubble)
   e adiciona: copiar resposta + exportar conversa (.md). Sem dependências. */
(function () {
    // ----------------------------------------------------------------- Prefs
    // Tema (claro/escuro) e modo debug/pensamento — globais, persistidos.
    const PREFS = {
        theme: localStorage.getItem("jur-theme") || "light",
        debug: localStorage.getItem("aurora-debug") === "1",
    };
    function applyTheme() {
        // body.light atende tanto app.css (.light) quanto juridico.css (.jur-body.light)
        document.body.classList.toggle("light", PREFS.theme === "light");
    }
    // force=true (clique no botão 🧠) abre/fecha TODOS os blocos conforme a
    // preferência. Sem force (no load), só abre quando o modo está ligado —
    // nunca fecha os blocos que o servidor já renderizou abertos (checkbox
    // "debug" do composer), senão o debug "ligado" nunca apareceria.
    function applyDebug(force) {
        document.body.classList.toggle("debug-on", PREFS.debug);
        document.querySelectorAll(".thread details, .chat-messages details")
            .forEach((d) => { if (force || PREFS.debug) d.open = PREFS.debug; });
    }
    applyTheme();  // cedo, para minimizar flash

    function addCopy(hostEl, getText) {
        if (!hostEl || hostEl.dataset.copyAttached) return;
        hostEl.dataset.copyAttached = "1";
        const btn = document.createElement("button");
        btn.className = "chat-copy-btn"; btn.type = "button"; btn.textContent = "Copiar";
        btn.addEventListener("click", () => {
            navigator.clipboard.writeText((getText() || "").trim());
            btn.textContent = "Copiado!";
            setTimeout(() => (btn.textContent = "Copiar"), 1500);
        });
        hostEl.appendChild(btn);
    }

    // Layout .msg (Séries Temporais, Dados SINAN)
    document.querySelectorAll(".msg.assistant .msg-content").forEach((el) =>
        addCopy(el, () => el.innerText.replace(/(Copiar|Copiado!)\s*$/, "")));
    // Layout .chat-bubble (Datas Comemorativas)
    document.querySelectorAll(".chat-bubble--assistant").forEach((b) => {
        const c = b.querySelector(".chat-bubble-content");
        if (c) addCopy(b, () => c.innerText);
    });

    // -------- Fileira de ícones de configuração (mesmo padrão do Jurídico) ----
    // Só nas telas de chat (shell .jur-shell), com as classes do juridico.css.
    function exportMd() {
        let md = "";
        document.querySelectorAll(".thread .msg").forEach((m) => {
            const role = m.classList.contains("user") ? "**Você**"
                : m.classList.contains("assistant") ? "**Assistente**" : "**Ferramenta**";
            const c = m.querySelector(".msg-content");
            if (c) md += role + ":\n\n" + c.innerText.replace(/(Copiar|Copiado!)\s*$/, "").trim() + "\n\n---\n\n";
        });
        document.querySelectorAll(".chat-messages .chat-bubble").forEach((m) => {
            const role = m.classList.contains("chat-bubble--user") ? "**Você**" : "**Assistente**";
            const c = m.querySelector(".chat-bubble-content");
            if (c) md += role + ":\n\n" + c.innerText.trim() + "\n\n---\n\n";
        });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
        a.download = "conversa.md"; a.click();
    }

    const bar = document.querySelector(".jur-shell .topbar-actions");
    if (bar) {
        function icon(html, title) {
            const b = document.createElement("button");
            b.type = "button"; b.className = "jur-icon-btn"; b.title = title; b.innerHTML = html;
            return b;
        }
        const dBtn = icon("🧠", "Pensamento / debug (SQL, ferramentas, RAG)");
        const syncDbg = () => dBtn.classList.toggle("active", PREFS.debug);
        dBtn.addEventListener("click", () => {
            PREFS.debug = !PREFS.debug;
            localStorage.setItem("aurora-debug", PREFS.debug ? "1" : "0"); applyDebug(true); syncDbg();
        });
        syncDbg();

        const tBtn = icon("🌓", "Alternar tema");
        tBtn.addEventListener("click", () => {
            PREFS.theme = PREFS.theme === "light" ? "dark" : "light";
            localStorage.setItem("jur-theme", PREFS.theme); applyTheme();
        });

        if (document.querySelector(".msg, .chat-bubble")) {
            const eBtn = icon("⬇", "Exportar conversa (.md)");
            eBtn.addEventListener("click", exportMd);
            bar.prepend(eBtn);
        }
        bar.prepend(tBtn);
        bar.prepend(dBtn);
    }

    applyDebug(false);

    // ---- Cronômetro em tempo real enquanto a IA processa (nos chats .msg) ----
    // Ao enviar, troca o botão por um contador que roda até a página recarregar
    // com a resposta. Dá feedback de "tempo real" no fluxo síncrono (POST/redirect).
    document.querySelectorAll("form.composer, form#composer, form#chat-form").forEach((form) => {
        form.addEventListener("submit", () => {
            const btn = form.querySelector('button[type="submit"]');
            if (!btn || btn.dataset.timing) return;
            btn.dataset.timing = "1";
            btn.disabled = true;
            const t0 = performance.now();
            const base = "⏳ Pensando";
            btn.textContent = base + " 0.0s";
            setInterval(() => {
                const s = ((performance.now() - t0) / 1000).toFixed(1);
                btn.textContent = base + " " + s + "s";
            }, 100);
        });
    });
})();
