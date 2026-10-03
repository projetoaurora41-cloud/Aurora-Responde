# `docs/`

Documentação detalhada do **Aurora Responde**. Para clonar e rodar do zero, veja
o [../README.md](../README.md) ou o [../TUTORIAL.md](../TUTORIAL.md).

| Documento | Sobre o que |
|-----------|-------------|
| [arquitetura.md](arquitetura.md) | Arquitetura só-Jurema (roteador determinístico + Jurema) + diagrama. |
| [chat.md](chat.md) | Como o chat funciona: roteador, ferramentas e geração com o Jurema. |
| [semantic_layer.md](semantic_layer.md) | Modelo `Notificacao` (~25 campos) + filtros geo/violência. |
| [database.md](database.md) | Schema do banco (VIOLBR / SIPIA-CT), padrão de query. |
| [webapp.md](webapp.md) | Interface Django: URLs, views, templates. |
| [docker.md](docker.md) | Rodar em containers (Docker Compose): web + ollama(Jurema). |
| [servidor.md](servidor.md) | Requisitos de servidor. |
| [troubleshooting.md](troubleshooting.md) | Erros comuns e como resolver. |
| [rag/](rag/) | Corpus do RAG interno: dicionário SINAM e descrição do produto. |

> Arquitetura: **um só LLM, o Jurema-7B**. Não há orquestrador Qwen3, forecasting
> (Chronos/ChatTime) nem embeddings.
