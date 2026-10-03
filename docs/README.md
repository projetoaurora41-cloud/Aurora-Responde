# `docs/`

Documentação detalhada por componente. Para começar do zero, leia
[../TUTORIAL.md](../TUTORIAL.md).

| Documento                                        | Sobre o que                                   |
|--------------------------------------------------|------------------------------------------------|
| [arquitetura.md](arquitetura.md)                 | Camadas, fluxo de dados, singleton do modelo. |
| [modelos_diagrama.md](modelos_diagrama.md)       | Diagrama alto nível: entrada → organização → saída dos modelos. |
| [modelos_por_pesquisador.md](modelos_por_pesquisador.md) | Modelos e projetos por pesquisador (Hernandison, Marcelo, Eduardo, Rafael). |
| [cli.md](cli.md)                                 | Referência completa de `python -m src.main`.   |
| [webapp.md](webapp.md)                           | Interface Django: URLs, modelos, services.     |
| [chat.md](chat.md)                               | Chat orquestrador + ferramentas + forecasters. |
| [semantic_layer.md](semantic_layer.md)           | Modelo `Notificacao` (~25 campos) + ETL.       |
| [benchmark_protocol.md](benchmark_protocol.md)   | Protocolo para escolher modelos por posição.   |
| [database.md](database.md)                       | Schema VIOLBR, padrão de query, helpers.       |
| [servidor.md](servidor.md)                       | Requisitos de servidor: vCPU, RAM, GPU/VRAM, disco. |
| [docker.md](docker.md)                           | Rodar em containers (Docker Compose): web + ollama + db. |
| [troubleshooting.md](troubleshooting.md)         | Erros comuns e como resolver.                  |
