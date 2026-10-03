# =============================================================================
# Bootstrap de deploy do Aurora no Windows (Docker Desktop).
#
# Copie ESTE arquivo (e o deploy.env) para a máquina e rode:
#
#     powershell -ExecutionPolicy Bypass -File deploy.ps1
#
# Ele instala o git/Docker Desktop (via winget, se faltarem), clona o repositório,
# garante o .env e sobe todos os recursos. Variáveis opcionais: $env:AURORA_REPO_URL,
# $env:AURORA_DIR, $env:AURORA_BRANCH. Repo PRIVADO -> PAT no HTTPS (ver deploy.env).
# =============================================================================
$ErrorActionPreference = "Stop"

function Log($m) { Write-Host "[deploy] $m" }

# Credenciais/parâmetros LOCAIS (arquivo não versionado — veja deploy.env.example).
if (Test-Path "deploy.env") {
  Log "carregando credenciais de ./deploy.env"
  Get-Content "deploy.env" | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
      [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
  }
}

$RepoUrl   = if ($env:AURORA_REPO_URL) { $env:AURORA_REPO_URL } else { "https://github.com/projetoaurora41-cloud/Projeto-Aurora.git" }
$TargetDir = if ($env:AURORA_DIR)      { $env:AURORA_DIR }      else { "Projeto-Aurora" }
$Branch    = if ($env:AURORA_BRANCH)   { $env:AURORA_BRANCH }   else { "main" }

# ---- 1) Dependências (git, Docker Desktop) via winget ----
function Ensure-Tool($cmd, $wingetId, $friendly) {
  if (Get-Command $cmd -ErrorAction SilentlyContinue) { return }
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Log "instalando $friendly via winget..."
    winget install -e --id $wingetId --accept-source-agreements --accept-package-agreements
  } else {
    throw "$friendly não instalado e winget indisponível. Instale manualmente e rode de novo."
  }
}

Ensure-Tool "git"    "Git.Git"              "git"
Ensure-Tool "docker" "Docker.DockerDesktop" "Docker Desktop"

# O daemon precisa estar rodando (abra o Docker Desktop ao menos uma vez).
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Docker instalado, mas o daemon não respondeu. Abra o Docker Desktop (e conclua o setup do WSL2), depois rode o deploy.ps1 de novo."
}

# ---- 2) Clona (ou atualiza) ----
if (-not (Test-Path "$TargetDir/.git")) {
  Log "clonando $RepoUrl (branch $Branch) em $TargetDir ..."
  git clone --branch $Branch $RepoUrl $TargetDir
} else {
  Log "repositório já existe; atualizando ($Branch)..."
  git -C $TargetDir fetch origin $Branch
  git -C $TargetDir checkout $Branch
  git -C $TargetDir pull --ff-only origin $Branch
}

Set-Location $TargetDir

# ---- 3) .env ----
if (-not (Test-Path ".env")) {
  if (Test-Path ".env.example") {
    Log ".env ausente — criando a partir de .env.example."
    Copy-Item ".env.example" ".env"
  } else {
    throw ".env ausente e sem .env.example."
  }
}
if (Select-String -Path ".env" -Pattern 'change-me|SEU_TOKEN_AQUI|^PGPASSWORD=$' -Quiet) {
  Write-Host "================================================================" -ForegroundColor Yellow
  Write-Host " ATENCAO: o .env ainda tem valores de EXEMPLO." -ForegroundColor Yellow
  Write-Host " Edite '$TargetDir\.env' com o banco EXTERNO (PGHOST/PGDATABASE/...)."
  Write-Host "     notepad .env"
  Write-Host " Depois rode o deploy.ps1 de novo."
  Write-Host "================================================================" -ForegroundColor Yellow
  exit 1
}

# ---- 4) Sobe todos os recursos ----
Log "subindo containers (build + provisiona modelos)..."
docker compose up --build -d

Log "pronto! App em http://localhost:8000"
docker compose ps
