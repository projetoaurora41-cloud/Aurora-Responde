#!/usr/bin/env bash
# =============================================================================
# Bootstrap COMPLETO de deploy do Aurora num servidor Linux (Ubuntu/Debian).
#
# Basta copiar ESTE arquivo (e o deploy.env) para o servidor e rodar:
#
#     bash deploy.sh
#
# Ele faz TUDO, nesta ordem:
#   1. instala git, curl e o Docker (se faltarem) e inicia o daemon;
#   2. clona (ou atualiza) o repositório privado;
#   3. garante o .env (a partir do .env.example);
#   4. sobe todos os recursos: build da app + Ollama + download dos modelos.
#
# Variáveis (podem vir de um arquivo ./deploy.env — veja deploy.env.example):
#   AURORA_REPO_URL  URL do repo (PAT no HTTPS se for privado):
#                    https://<TOKEN>@github.com/projetoaurora41-cloud/Aurora-Responde.git
#   AURORA_DIR       pasta destino do clone (padrão: Aurora-Responde)
#   AURORA_BRANCH    branch (padrão: main)
# =============================================================================
set -euo pipefail

log() { echo "[deploy] $*"; }

# Credenciais/parâmetros LOCAIS (arquivo não versionado — veja deploy.env.example).
# É onde vai a "key do GitHub" (AURORA_REPO_URL com o token). Carregado se existir.
if [ -f deploy.env ]; then
  log "carregando credenciais de ./deploy.env"
  set -a; . ./deploy.env; set +a
fi

REPO_URL="${AURORA_REPO_URL:-https://github.com/projetoaurora41-cloud/Aurora-Responde.git}"
TARGET_DIR="${AURORA_DIR:-Aurora-Responde}"
BRANCH="${AURORA_BRANCH:-main}"

# sudo só quando não for root
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

# ---------------------------------------------------------------------------
# 1) Dependências: git, curl e Docker
# ---------------------------------------------------------------------------
APT=""
command -v apt-get >/dev/null 2>&1 && APT="1"

_apt_install() {
  if [ -n "$APT" ]; then
    $SUDO apt-get update -y
    $SUDO apt-get install -y "$@"
  else
    log "ERRO: '$*' ausente e este script só instala via apt (Ubuntu/Debian)."
    log "      Instale manualmente e rode de novo."
    exit 1
  fi
}

command -v curl >/dev/null 2>&1 || { log "instalando curl..."; _apt_install curl ca-certificates; }
command -v git  >/dev/null 2>&1 || { log "instalando git...";  _apt_install git; }

# ---------------------------------------------------------------------------
# DNS do Docker — evita 'Temporary failure resolving deb.debian.org' no build.
#
# Em muitos VPS o /etc/resolv.conf do host aponta para 127.0.0.53 (stub do
# systemd-resolved), que os CONTÊINERES não alcançam — então o apt E o pip do
# build ficam sem DNS (o host resolve normalmente; só o contêiner não). A
# correção canônica é fixar servidores DNS no daemon do Docker.
#
# Esta rotina é AUTO-VERIFICÁVEL: testa se um contêiner resolve um nome; só age
# se falhar; reinicia o daemon (aplica o dns E recria a bridge/iptables); e
# re-testa. Se ainda falhar, para com diagnóstico (não gasta ~1000s num build
# que morreria). Desative com AURORA_SKIP_DNS_FIX=1; troque os servidores com
# AURORA_DOCKER_DNS="1.1.1.1 8.8.8.8".
# ---------------------------------------------------------------------------

# Um contêiner efêmero consegue resolver um nome externo? (o build depende disto)
_docker_dns_ok() {
  $DOCKER run --rm busybox nslookup deb.debian.org >/dev/null 2>&1
}

# Grava/atualiza "dns" em /etc/docker/daemon.json (merge preservando outras chaves).
_write_daemon_dns() {
  local daemon="$1" dns_servers="$2"
  local pybin; pybin="$(command -v python3 || true)"
  if [ -n "$pybin" ]; then
    # Caminho absoluto: 'sudo' zera o PATH (secure_path) e poderia não achar o python3.
    $SUDO env AURORA_DAEMON="$daemon" AURORA_DNS="$dns_servers" "$pybin" - <<'PY' || log "aviso: falha ao gravar daemon.json (seguindo)."
import json, os
path = os.environ["AURORA_DAEMON"]
servers = os.environ["AURORA_DNS"].split()
data, raw = {}, ""
if os.path.exists(path):
    try:
        raw = open(path).read().strip()
        data = json.loads(raw) if raw else {}
    except Exception:
        # JSON inválido: preserva o original como .bak e recomeça do zero.
        if raw:
            os.replace(path, path + ".bak")
        data = {}
data["dns"] = servers                 # sobrescreve p/ garantir servidores alcançáveis
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
  else
    # Sem python3: só cria se ainda não existir (não arrisca sobrescrever à mão).
    if $SUDO test -f "$daemon"; then
      log "aviso: python3 ausente e $daemon já existe — edite à mão: \"dns\":[\"8.8.8.8\",\"1.1.1.1\"]."
      return 0
    fi
    local arr="" s
    for s in $dns_servers; do arr="${arr}\"$s\", "; done
    arr="[${arr%, }]"
    $SUDO mkdir -p /etc/docker
    printf '{\n  "dns": %s\n}\n' "$arr" | $SUDO tee "$daemon" >/dev/null
  fi
}

# Reinicia o daemon e espera ele voltar (até ~30s). Retorna 0 se voltou.
_restart_docker() {
  if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl restart docker || $SUDO service docker restart || true
  else
    $SUDO service docker restart || true
  fi
  local i
  for i in $(seq 1 30); do
    $DOCKER info >/dev/null 2>&1 && return 0
    sleep 1
  done
  $DOCKER info >/dev/null 2>&1
}

ensure_docker_dns() {
  [ "${AURORA_SKIP_DNS_FIX:-0}" = "1" ] && { log "correção de DNS do Docker desativada (AURORA_SKIP_DNS_FIX=1)."; return 0; }

  local daemon="/etc/docker/daemon.json"
  local dns_servers="${AURORA_DOCKER_DNS:-8.8.8.8 1.1.1.1}"

  log "checando DNS dos contêineres (pode baixar a imagem 'busybox', ~4 MB)..."
  if _docker_dns_ok; then
    log "DNS dos contêineres OK — nada a corrigir."
    return 0
  fi

  log "DNS dos contêineres NÃO resolve — aplicando correção (dns=$dns_servers em $daemon)..."
  _write_daemon_dns "$daemon" "$dns_servers"
  log "reiniciando o daemon do Docker (aplica o DNS e recria a bridge/iptables)..."
  if ! _restart_docker; then
    log "ERRO: o Docker não voltou após o restart. Veja 'sudo journalctl -u docker -n 30'."
    exit 1
  fi

  if _docker_dns_ok; then
    log "DNS corrigido — contêineres resolvem nomes. Seguindo para o build."
    return 0
  fi

  # Ainda falhou: mostra diagnóstico e para (evita um build longo que morreria).
  log "================================================================"
  log " ERRO: o DNS dos contêineres ainda não resolve após a correção."
  log " Diagnóstico:"
  log "   $daemon:"
  $SUDO cat "$daemon" 2>/dev/null | sed 's/^/[deploy]     /' || true
  log "   host /etc/resolv.conf:"
  cat /etc/resolv.conf 2>/dev/null | sed 's/^/[deploy]     /' || true
  log "   host resolve deb.debian.org? $(getent hosts deb.debian.org >/dev/null 2>&1 && echo sim || echo NAO)"
  log "   host alcança 8.8.8.8?        $(ping -c1 -W2 8.8.8.8 >/dev/null 2>&1 && echo sim || echo NAO)"
  log " Causas prováveis: firewall bloqueando a porta 53 na saída da bridge do"
  log " Docker, ou o host sem internet. Ajuste e rode 'bash deploy.sh' de novo."
  log "================================================================"
  exit 1
}

if ! command -v docker >/dev/null 2>&1; then
  log "Docker não encontrado — instalando via get.docker.com (pode pedir a senha do sudo)..."
  curl -fsSL https://get.docker.com | $SUDO sh
fi

# Inicia e habilita o daemon (se houver systemd)
if command -v systemctl >/dev/null 2>&1; then
  $SUDO systemctl enable --now docker || true
fi

# Adiciona o usuário ao grupo docker (efetivo só no PRÓXIMO login)
if ! id -nG "${USER:-$(id -un)}" 2>/dev/null | grep -qw docker; then
  log "adicionando ${USER:-$(id -un)} ao grupo docker (efetivo no próximo login)"
  $SUDO usermod -aG docker "${USER:-$(id -un)}" || true
fi

# Define como chamar o docker NESTA sessão (com ou sem sudo — o grupo ainda não
# está ativo na sessão atual logo após o usermod).
if docker info >/dev/null 2>&1; then
  DOCKER="docker"
elif $SUDO docker info >/dev/null 2>&1; then
  DOCKER="$SUDO docker"
else
  log "ERRO: o daemon do Docker não respondeu mesmo após a instalação."
  log "----------------------- diagnóstico -----------------------"
  log "init (PID 1): $(ps -p 1 -o comm= 2>/dev/null || echo '?')"
  # Tenta iniciar de novo pelos dois caminhos (com/sem systemd) e mostra o log.
  $SUDO service docker start >/dev/null 2>&1 || true
  $SUDO systemctl status docker --no-pager 2>&1 | sed 's/^/[deploy]   /' | head -n 12 || true
  $SUDO journalctl -u docker --no-pager -n 20 2>&1 | sed 's/^/[deploy]   /' || true
  log "-----------------------------------------------------------"
  # Se o 'service docker start' resolveu, segue; senão, orienta e sai.
  if $SUDO docker info >/dev/null 2>&1; then
    DOCKER="$SUDO docker"
    log "recuperado via 'service docker start' — usando '$DOCKER'."
  else
    log "Causas comuns:"
    log "  • sem systemd (WSL/container LXC)  -> '$SUDO service docker start' ou 'sudo dockerd &'"
    log "  • dockerd falhou (iptables/cgroups) -> veja o log acima ou rode 'sudo dockerd --debug'"
    log "  • VPS OpenVZ/LXC restrito           -> Docker não roda; use um VPS KVM"
    exit 1
  fi
fi
log "docker: '$DOCKER'  |  $($DOCKER --version)"

# ---------------------------------------------------------------------------
# 2) Clona (ou atualiza) o repositório
# ---------------------------------------------------------------------------
if [ ! -d "$TARGET_DIR/.git" ]; then
  log "clonando $REPO_URL (branch $BRANCH) em $TARGET_DIR ..."
  git clone --branch "$BRANCH" "$REPO_URL" "$TARGET_DIR"
else
  log "repositório já existe; atualizando ($BRANCH)..."
  git -C "$TARGET_DIR" fetch origin "$BRANCH"
  git -C "$TARGET_DIR" checkout "$BRANCH"
  git -C "$TARGET_DIR" pull --ff-only origin "$BRANCH"
fi

cd "$TARGET_DIR"

# ---------------------------------------------------------------------------
# 3) Garante o .env (banco EXTERNO + chaves de API)
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
  [ -f .env.example ] || { log "ERRO: .env ausente e sem .env.example."; exit 1; }
  log ".env ausente — criando a partir de .env.example."
  cp .env.example .env
fi

# Se o .env ainda tem valores de EXEMPLO, para e avisa (evita subir com config errada).
if grep -qE 'change-me|SEU_TOKEN_AQUI|^PGPASSWORD=$' .env 2>/dev/null; then
  log "================================================================"
  log " ATENÇÃO: o arquivo .env ainda tem valores de EXEMPLO."
  log " Edite '$TARGET_DIR/.env' com os dados do seu banco EXTERNO:"
  log "     nano $TARGET_DIR/.env"
  log " Preencha: PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD (e chaves de API)."
  log " Depois rode 'bash deploy.sh' de novo."
  log "================================================================"
  exit 1
fi

# ---------------------------------------------------------------------------
# 4) Sobe todos os recursos (build da app + Ollama + download dos modelos)
# ---------------------------------------------------------------------------
# Garante DNS nos contêineres ANTES do build (senão o apt/pip falham sem rede).
ensure_docker_dns

log "subindo containers (build + provisiona o Jurema)..."
$DOCKER compose up --build -d

log "pronto! App em http://localhost:8000  (ou http://IP-DO-SERVIDOR:8000)"
log "acompanhe o download do Jurema: $DOCKER compose logs -f ollama-pull"
$DOCKER compose ps
