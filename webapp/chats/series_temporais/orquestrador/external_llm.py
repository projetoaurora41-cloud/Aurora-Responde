"""Cliente HTTP pra LLMs externos cadastrados via UI (`ExternalModel`).

Expõe `ExternalLLMClient` cuja interface mimica `ollama.Client.chat()`
pra minimizar mudança no `orchestrator.chat()`. Suporta dois protocolos:

* **openai_chat** (default): cobre OpenAI, OpenRouter, LiteLLM, Groq,
  Together, Mistral, DeepSeek e qualquer outro proxy compatível com
  `POST /v1/chat/completions`.
* **anthropic_messages**: API nativa Anthropic em `/v1/messages`.

Resposta normalizada pra ter `msg.content` (str) e `msg.tool_calls`
(lista de dicts com `.function.name` e `.function.arguments`).

`ollama_native` (protocolo) é tratado em outro caminho — cai pro
`ollama.Client(host=em.endpoint)` direto no `_pick_client()`.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass
class _ExtToolFunction:
    name: str
    arguments: dict


@dataclass
class _ExtToolCall:
    function: _ExtToolFunction


@dataclass
class _ExtMessage:
    role: str = "assistant"
    content: str = ""
    tool_calls: list[_ExtToolCall] = field(default_factory=list)


@dataclass
class _ExtResponse:
    """Compatível com `ollama.ChatResponse` (`.message` é o que importa)."""
    message: _ExtMessage


class ExternalLLMClient:
    """Cliente HTTP que fala protocolos OpenAI-compatible / Anthropic."""

    def __init__(self, *, url: str, api_key: str = "", protocol: str = "openai_chat",
                 model_id: str = "", headers: dict | None = None,
                 timeout: float = 60.0) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key.strip()
        self.protocol = (protocol or "openai_chat").lower()
        self.model_id = model_id
        self.extra_headers = dict(headers or {})
        self.timeout = float(timeout)

    # ------------------------------------------------------------------
    # Interface compatível com ollama.Client.chat
    # ------------------------------------------------------------------
    def chat(self, *, model: str, messages: list[dict],
             tools: list[dict] | None = None, options: dict | None = None,
             think: bool = False) -> _ExtResponse:
        """`model` recebido é ignorado em favor de `self.model_id`."""
        if self.protocol == "anthropic_messages":
            return self._chat_anthropic(messages, tools, options)
        return self._chat_openai(messages, tools, options)

    # ------------------------------------------------------------------
    # OpenAI Chat Completions (default)
    # ------------------------------------------------------------------
    def _chat_openai(self, messages: list[dict], tools: list[dict] | None,
                     options: dict | None) -> _ExtResponse:
        body = {
            "model": self.model_id,
            "messages": _normalize_messages_openai(messages),
            "temperature": float((options or {}).get("temperature", 0.2)),
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        url = self.url if self.url.endswith("/chat/completions") else \
              f"{self.url}/v1/chat/completions"
        data = self._post_json(url, body)
        choice = (data.get("choices") or [{}])[0]
        m = choice.get("message") or {}
        content = m.get("content") or ""
        raw_calls = m.get("tool_calls") or []
        tool_calls = []
        for tc in raw_calls:
            fn = tc.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, str):
                try: args = json.loads(args)
                except Exception: args = {}
            tool_calls.append(_ExtToolCall(
                function=_ExtToolFunction(name=fn.get("name", ""),
                                          arguments=args or {})))
        return _ExtResponse(message=_ExtMessage(content=content,
                                                  tool_calls=tool_calls))

    # ------------------------------------------------------------------
    # Anthropic Messages
    # ------------------------------------------------------------------
    def _chat_anthropic(self, messages: list[dict], tools: list[dict] | None,
                        options: dict | None) -> _ExtResponse:
        # Anthropic separa system do array de messages
        sys_parts, msgs = [], []
        for m in messages:
            if m.get("role") == "system":
                sys_parts.append(m.get("content", ""))
            else:
                msgs.append({"role": m["role"], "content": m.get("content", "")})

        body = {
            "model": self.model_id,
            "messages": msgs,
            "max_tokens": 2048,
            "temperature": float((options or {}).get("temperature", 0.2)),
        }
        if sys_parts:
            body["system"] = "\n\n".join(sys_parts)
        if tools:
            # Anthropic usa um schema próprio — converte do formato OpenAI
            body["tools"] = [_openai_tool_to_anthropic(t) for t in tools]

        url = self.url if self.url.endswith("/messages") else f"{self.url}/v1/messages"
        data = self._post_json(url, body, anthropic=True)

        # Resposta vem como array de "content blocks"
        content_text, tool_calls = "", []
        for block in (data.get("content") or []):
            if block.get("type") == "text":
                content_text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(_ExtToolCall(function=_ExtToolFunction(
                    name=block.get("name", ""),
                    arguments=block.get("input") or {})))
        return _ExtResponse(message=_ExtMessage(content=content_text,
                                                  tool_calls=tool_calls))

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------
    def _post_json(self, url: str, body: dict, *, anthropic: bool = False) -> dict:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if anthropic:
            if self.api_key:
                headers["x-api-key"] = self.api_key
            headers.setdefault("anthropic-version", "2023-06-01")
        else:
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Anthropic e OpenAI mandam o erro JSON real no body — captura
            # pra mostrar o motivo (ex: "model not found", "invalid api key").
            try:
                body_bytes = exc.read() or b""
                body_text = body_bytes.decode("utf-8", errors="replace")[:500]
                # Tenta extrair só a mensagem se for JSON
                try:
                    j = json.loads(body_text)
                    err = j.get("error", {})
                    detail = err.get("message") or err.get("type") or body_text
                    body_text = detail[:300]
                except Exception:
                    pass
            except Exception:
                body_text = ""
            raise RuntimeError(
                f"HTTP {exc.code} {exc.reason} · {body_text}".strip(" ·")
            ) from exc


def _normalize_messages_openai(messages: list[dict]) -> list[dict]:
    """Converte mensagens do dialeto Ollama pro OpenAI (são quase iguais)."""
    out = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "tool":
            # Ollama: {role:'tool', name:'x', content:'...'}
            # OpenAI: {role:'tool', tool_call_id:'...', content:'...'}
            out.append({"role": "tool",
                         "tool_call_id": m.get("tool_call_id") or m.get("name", ""),
                         "content": content if isinstance(content, str)
                                   else json.dumps(content, ensure_ascii=False)})
        else:
            out.append({"role": role, "content": content})
    return out


def _openai_tool_to_anthropic(tool: dict) -> dict:
    fn = tool.get("function") or {}
    return {
        "name": fn.get("name", ""),
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
    }
