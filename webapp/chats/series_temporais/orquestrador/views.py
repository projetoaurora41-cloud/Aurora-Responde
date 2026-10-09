from __future__ import annotations

import html
import os

from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from guardrails.limites import verificar_limite
from guardrails.pipeline import processar_entrada, processar_saida

# Versão leve (Aurora Responde): sem forecasting (torch/Chronos). O seletor de
# modelos de série não existe mais; mantém-se um REGISTRY vazio só para compat.
try:
    from src.series_models import REGISTRY
except Exception:
    REGISTRY = {}

from . import attachments
from .models import ChatAttachment, ChatMessage, ChatThread
from .orchestrator import DEFAULT_MODEL, _display_model, chat as run_chat, ping_ollama

# Versão interna do AURORA Responde (beta). Exibida como selo na UI e citada
# nos materiais. Bump a cada mudança relevante do assistente.
AURORA_RESPONDE_VERSION = os.getenv("AURORA_RESPONDE_VERSION", "0.1.0")

# Limite de tamanho da mensagem do usuário (anti-abuso; o chat é aberto).
# Default 2000 — encaminhamento 27 (frente de segurança). Override via env.
MAX_INPUT_CHARS = int(os.getenv("AURORA_MAX_INPUT_CHARS", "2000"))

_BLOQUEIO_ENTRADA_FALLBACK = (
    "Não posso processar essa mensagem. Reformule a pergunta dentro do escopo "
    "do Aurora (dados de violência, legislação relacionada ou funcionamento "
    "da plataforma)."
)
_BLOQUEIO_SAIDA_FALLBACK = (
    "A resposta foi bloqueada pelos filtros de segurança. Reformule a pergunta "
    "ou tente novamente."
)


# ---------------------------------------------------------------------------
# Escopo do dono da conversa: o "Aurora responde" é um chat ABERTO (sem login).
# Usuário logado → conversas por user. Anônimo → conversas por session_key.
# ---------------------------------------------------------------------------
def _ensure_session(request) -> str:
    if not request.session.session_key:
        request.session.save()
    # Chat único e anônimo: a conversa vale só enquanto o navegador está aberto.
    # Sem histórico na tela, reabrir o navegador começa uma conversa nova.
    if not request.user.is_authenticated:
        request.session.set_expiry(0)
    return request.session.session_key


def _rate_limit_key(request) -> str:
    if request.user.is_authenticated:
        return f"user:{request.user.pk}"
    return f"session:{_ensure_session(request)}"


def _rate_limit_response(pk: int, retry_after: int) -> HttpResponse:
    """HTTP 429 com Retry-After (contrato da frente de segurança)."""
    chat_url = reverse("chat:thread", kwargs={"pk": pk})
    msg = (
        f"Limite de mensagens atingido. Tente novamente em {retry_after} segundos."
    )
    body = (
        "<!DOCTYPE html><html lang='pt-br'><head><meta charset='utf-8'>"
        f"<title>Limite atingido</title></head><body>"
        f"<p>{html.escape(msg)}</p>"
        f"<p><a href='{html.escape(chat_url)}'>Voltar ao chat</a></p>"
        "</body></html>"
    )
    resp = HttpResponse(body, status=429, content_type="text/html; charset=utf-8")
    resp["Retry-After"] = str(retry_after)
    return resp


def _threads_for(request):
    if request.user.is_authenticated:
        return ChatThread.objects.filter(user=request.user)
    return ChatThread.objects.filter(user__isnull=True,
                                     session_key=_ensure_session(request))


def _owner_kwargs(request) -> dict:
    if request.user.is_authenticated:
        return {"user": request.user}
    return {"user": None, "session_key": _ensure_session(request)}


def _get_thread(request, pk: int) -> ChatThread:
    return get_object_or_404(_threads_for(request), pk=pk)


def thread_list(request):
    return render(request, "chat/thread_list.html", {
        "threads": _threads_for(request),
        "forecasters": REGISTRY,
        "default_model": DEFAULT_MODEL,
    })


def new_thread(request):
    forecaster = request.POST.get("forecaster") or "chronos2"
    model = request.POST.get("model") or DEFAULT_MODEL
    try:
        temperature = max(0.0, min(1.5, float(request.POST.get("temperature") or 0.2)))
    except (TypeError, ValueError):
        temperature = 0.2
    thread = ChatThread.objects.create(
        title="Nova conversa", forecaster=forecaster, model=model,
        temperature=temperature, **_owner_kwargs(request),
    )
    return redirect("chat:thread", pk=thread.pk)


def _render_chat(request, thread):
    """Renderiza a interface do chat único (estilo ChatGPT) para uma conversa.

    Passa a lista de conversas do visitante (logado OU anônimo por sessão) como
    `sidebar_chat_threads` — o context_processor só cobre usuários logados.
    """
    ok, status = ping_ollama()
    return render(request, "chat/aurora_home.html", {
        "thread": thread,
        "messages_list": thread.messages.all(),
        "ollama_ok": ok,
        "ollama_status": status,
        "max_input_chars": MAX_INPUT_CHARS,
        "max_attachments": attachments.MAX_ATTACHMENTS,
        "sidebar_chat_threads": _threads_for(request)[:40],
        "aurora_versao": AURORA_RESPONDE_VERSION,
    })


def aurora_home(request):
    """`/` — Aurora responde: chat único. Abre a conversa mais recente do
    visitante (logado ou anônimo) ou cria uma nova vazia, estilo ChatGPT/Claude."""
    thread = _threads_for(request).first()
    if thread is None:
        thread = ChatThread.objects.create(
            title="Nova conversa", model=DEFAULT_MODEL, **_owner_kwargs(request))
    return _render_chat(request, thread)


def thread(request, pk: int):
    return _render_chat(request, _get_thread(request, pk))


@require_POST
def send_message(request, pk: int):
    thread = _get_thread(request, pk)

    # Rate limit ANTES de persistir ou chamar o LLM (encaminhamento 25).
    limite = verificar_limite(_rate_limit_key(request))
    if not limite.ok:
        retry = limite.retry_after_seconds or 60
        return _rate_limit_response(pk, retry)

    text = (request.POST.get("message") or "").strip()

    # Limite de input: trunca mensagens gigantes (chat aberto → anti-abuso).
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]
        flash.warning(request, f"Mensagem muito longa — truncada em {MAX_INPUT_CHARS} caracteres.")

    files = request.FILES.getlist("files")[:attachments.MAX_ATTACHMENTS]
    if not text and not files:
        flash.error(request, "Mensagem vazia.")
        return redirect("chat:thread", pk=pk)

    # Forecaster fixo em Chronos-2: a escolha do modelo de série é automática
    # (sem seletor na UI). Mantém a temperatura padrão da thread.
    if thread.forecaster != "chronos2":
        thread.forecaster = "chronos2"

    # Anexos (PDF / imagem / texto): extrai o texto e guarda por conversa.
    novos_anexos: list[ChatAttachment] = []
    for f in files:
        if f.size > attachments.MAX_ATTACHMENT_BYTES:
            limite_mb = attachments.MAX_ATTACHMENT_BYTES // (1024 * 1024)
            flash.error(request, f"'{f.name}' excede o limite de {limite_mb} MB — ignorado.")
            continue
        try:
            kind, extracted = attachments.extract(f.name, f.read())
        except ValueError as exc:
            flash.error(request, f"'{f.name}': {exc}")
            continue
        novos_anexos.append(ChatAttachment.objects.create(
            thread=thread, name=f.name[:255], kind=kind,
            text=extracted, char_count=len(extracted)))

    # Bolha do usuário: mensagem mascarada (sem o bloco de anexos).
    if text:
        display_text = processar_entrada(text).texto_mascarado
    else:
        display_text = f"(enviou {len(novos_anexos)} anexo(s))"

    # Pipeline de entrada inclui anexos — o LLM só vê conteúdo já filtrado.
    texto_para_pipeline = display_text
    if novos_anexos:
        bloco_anexos = attachments.build_context(novos_anexos)
        texto_para_pipeline = (
            display_text
            + "\n\n=== ARQUIVOS ANEXADOS (use como contexto e cite pelo nome) ===\n"
            + bloco_anexos
        )
    entrada = processar_entrada(texto_para_pipeline)

    ChatMessage.objects.create(thread=thread, role="user", content=display_text)

    # Entrada bloqueada pelos guardrails (fora de escopo / PII / injeção):
    # responde com a mensagem de bloqueio e encerra o turno.
    if entrada.bloqueio or not entrada.ok:
        ChatMessage.objects.create(
            thread=thread, role="assistant",
            content=(entrada.mensagem_usuario or _BLOQUEIO_ENTRADA_FALLBACK),
        )
        if not thread.title or thread.title == "Nova conversa":
            thread.title = (text or display_text)[:80]
        thread.save()
        return redirect("chat:thread", pk=pk)

    # Histórico que o LLM vê (o system prompt é adicionado dentro de chat()).
    # Enviamos turnos LIMPOS user/assistant e PULAMOS as mensagens role="tool":
    # elas são persistidas com content="" (o dado real fica em tool_payload) e
    # SEM o assistant/tool_calls correspondente, então reenviá-las forma uma
    # sequência inválida que faz o modelo perder o vínculo com a resposta
    # anterior. A prosa final do assistant já carrega os números/tendências
    # necessários para responder perguntas de acompanhamento; se precisar de
    # dado novo, o orquestrador chama as ferramentas de novo neste turno.
    history: list[dict] = []
    for m in thread.messages.all():
        if m.role == "user":
            history.append({"role": "user", "content": m.content})
        elif m.role == "assistant" and (m.content or "").strip():
            history.append({"role": "assistant", "content": m.content})

    # Última mensagem do usuário: conteúdo já processado (com anexos se houver).
    if history and history[-1]["role"] == "user":
        history[-1] = {"role": "user", "content": entrada.texto_mascarado}

    result = run_chat(history, forecaster=thread.forecaster, model=thread.model,
                      temperature=thread.temperature)

    # Persist tool events (assistant messages with tool_calls + role=tool replies).
    for evt in result.tool_events:
        ChatMessage.objects.create(
            thread=thread, role="tool",
            content="", tool_name=evt.name,
            tool_payload={"args": evt.args, "result": evt.result},
            elapsed_seconds=evt.elapsed_seconds,
        )

    # Modelo de série vencedor (para badge nos detalhes; nunca na prosa).
    forecaster_used = ""
    for evt in result.tool_events:
        r = evt.result if isinstance(evt.result, dict) else {}
        w = r.get("winner") or (r.get("previsao_mensal") or {}).get("winner")
        if w:
            forecaster_used = _display_model(w)

    # Pipeline de saída antes de exibir.
    raw_out = result.final_text or result.error or "(sem resposta)"
    saida = processar_saida(raw_out)
    if saida.bloqueio or not saida.ok:
        final_content = saida.mensagem_usuario or _BLOQUEIO_SAIDA_FALLBACK
    else:
        final_content = saida.texto or raw_out

    ChatMessage.objects.create(
        thread=thread, role="assistant",
        content=final_content,
        elapsed_seconds=result.elapsed_seconds,
        tokens_prompt=result.prompt_tokens or None,
        tokens_completion=result.completion_tokens or None,
        forecaster_used=forecaster_used,
    )

    # Auto-title on the first user message of an empty thread.
    if not thread.title or thread.title == "Nova conversa":
        thread.title = (text or display_text)[:80]
    thread.save()

    if result.error:
        flash.error(request, f"Erro no orquestrador: {result.error}")

    return redirect("chat:thread", pk=pk)


@require_POST
def delete_thread(request, pk: int):
    thread = _get_thread(request, pk)
    thread.delete()
    return redirect("chat:list")


@login_required
def relatorio(request):
    """Lista todas as previsões feitas em todas as threads do usuário, com
    acurácia (WAPE) e modelo vencedor."""
    msgs = (ChatMessage.objects
            .filter(thread__user=request.user, role="tool")
            .filter(tool_name__in=["previsao_automatica", "relatorio_municipio"])
            .select_related("thread")
            .order_by("-created_at")[:200])

    rows = []
    for m in msgs:
        result = (m.tool_payload or {}).get("result", {})
        # previsao_automatica vs relatorio_municipio têm shapes diferentes
        if m.tool_name == "relatorio_municipio":
            inner = result.get("previsao_mensal", {})
            label = result.get("municipio", "—")
        else:
            inner = result
            f = result.get("filters_applied", {})
            label = ", ".join(f"{k}={v}" for k, v in f.items()) or "—"
        if inner.get("error") or inner.get("erro") or not inner.get("winner"):
            continue
        wape = inner.get("winner_metrics", {}).get("wape")
        rows.append({
            "message_id": m.pk,
            "thread_id": m.thread_id,
            "thread_title": m.thread.title,
            "when": m.created_at,
            "tool": m.tool_name,
            "subject": label,
            "winner": inner.get("winner"),
            "wape": wape,
            "horizon": inner.get("horizon"),
            "elapsed": m.elapsed_seconds,
            "n_points": inner.get("profile", {}).get("length"),
        })
    return render(request, "chat/relatorio.html", {"rows": rows})
