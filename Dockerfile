# =============================================================================
# Aurora Responde — imagem da aplicação (webapp Django + núcleo src/)
#
# Fork leve: SEM PyTorch, SEM modelos HuggingFace. O único LLM é o Jurema-7B,
# que roda no serviço `ollama` (ver docker-compose.yml). A imagem só carrega o
# Django + o acesso SQL (psycopg/pandas).
# =============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=aurora.settings

# Dependências de sistema (build de wheels nativas + libpq + curl p/ healthcheck)
# NB: se este passo falhar com "Temporary failure resolving deb.debian.org", é
# DNS dos contêineres — o deploy.sh corrige (dns em /etc/docker/daemon.json).
# Acquire::Retries dá margem a hiccups transitórios de rede.
RUN apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Dependências do projeto (leves) + gunicorn (não está no requirements)
RUN pip install --upgrade pip
COPY requirements.txt ./
RUN pip install -r requirements.txt gunicorn

# 2) Código da aplicação (webapp/, src/, docs/, ...)
COPY . .

RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
# Modo padrão: runserver (serve estáticos em DEBUG, 1 processo p/ o singleton do modelo).
# Alternativas: "gunicorn" (produção) ou qualquer comando (ex.: manage.py ...).
CMD ["web"]
