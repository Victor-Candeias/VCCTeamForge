#!/usr/bin/env bash
# Deploy local (sem root nem Nginx) do backend + frontend para /opt/vccteamforge,
# geridos como serviços systemd do utilizador. Executar como utilizador normal:
#   deployment/scripts/deploy-local.sh
#
# Passos: copia o código, atualiza o venv e o node_modules (só se os locks mudaram),
# compila o frontend, aplica migrations e seeds e reinicia a API e o frontend,
# esperando que ambos fiquem prontos. A API escuta apenas em 127.0.0.1; o frontend
# (vite preview) escuta em 0.0.0.0 e faz proxy de /api para a API.
#
# Variáveis opcionais:
#   VCCTF_DEPLOY_ROOT     diretoria de destino               (/opt/vccteamforge)
#   VCCTF_API_PORT        porta da API em 127.0.0.1          (5100)
#   VCCTF_WEB_PORT        porta do frontend em 0.0.0.0       (5175)
#   VCCTF_ALLOWED_HOSTS   nomes extra aceites pelo frontend  (nome da máquina)
set -euo pipefail

DEPLOY_ROOT="${VCCTF_DEPLOY_ROOT:-/opt/vccteamforge}"
API_PORT="${VCCTF_API_PORT:-5100}"
WEB_PORT="${VCCTF_WEB_PORT:-5175}"
ALLOWED_HOSTS="${VCCTF_ALLOWED_HOSTS:-$(hostname),$(hostname).local,$(hostname -f 2>/dev/null || hostname)}"
READY_TIMEOUT_SECONDS=60

API_SERVICE=vccteamforge-api.service
WEB_SERVICE=vccteamforge-web.service
SNAPSHOT_UNIT=vccteamforge-report-snapshots
BACKUP_UNIT=vccteamforge-backup
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

REPO_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
ENV_FILE="$DEPLOY_ROOT/config/api.env"
STATE_DIR="$DEPLOY_ROOT/.deploy-state"

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }

if [[ "$(id -u)" -eq 0 ]]; then
    die "executar como utilizador normal (os serviços são systemd --user); para root usar deploy.sh."
fi
for cmd in python3 node npm rsync curl systemctl sha256sum; do
    command -v "$cmd" >/dev/null || die "comando em falta: $cmd"
done
python3 -c 'import sys, venv; sys.exit(sys.version_info < (3, 11))' \
    || die "é necessário Python >= 3.11 com o módulo venv (python3-venv)."
systemctl --user show-environment >/dev/null 2>&1 \
    || die "systemd --user indisponível nesta sessão (definir XDG_RUNTIME_DIR ou iniciar sessão com login)."
[[ -d "$DEPLOY_ROOT" && -w "$DEPLOY_ROOT" ]] \
    || die "$DEPLOY_ROOT tem de existir e ter permissão de escrita (ex.: sudo install -d -o $(id -un) $DEPLOY_ROOT)."

mkdir -p "$DEPLOY_ROOT"/{backend,database,frontend,config,data/attachments,backups} \
    "$STATE_DIR" "$UNIT_DIR"
chmod 0700 "$DEPLOY_ROOT/config" "$DEPLOY_ROOT/data" "$DEPLOY_ROOT/backups"

# Executa o comando se o hash dos ficheiros indicados mudou desde a última execução com sucesso.
run_if_changed() {
    local name="$1" marker; shift
    local -a files=()
    while [[ "$1" != "--" ]]; do files+=("$1"); shift; done
    shift
    marker="$(cat "${files[@]}" | sha256sum | cut -d' ' -f1)"
    if [[ -f "$STATE_DIR/$name" && "$(cat "$STATE_DIR/$name")" == "$marker" ]]; then
        echo "$name sem alterações."
        return 0
    fi
    "$@"
    echo "$marker" >"$STATE_DIR/$name"
}

# Substitui (ou acrescenta) uma linha KEY=... no ficheiro de configuração.
set_env_line() {
    local line="$1" key="${1%%=*}" tmp
    tmp="$(mktemp "$ENV_FILE.XXXXXX")"
    grep -v "^${key}=" "$ENV_FILE" >"$tmp" || true
    printf '%s\n' "$line" >>"$tmp"
    chmod 0600 "$tmp"
    mv "$tmp" "$ENV_FILE"
}

log "A copiar código para $DEPLOY_ROOT"
sync_dir() { rsync -a --delete --exclude '__pycache__/' --exclude '*.pyc' "$@"; }
sync_dir --exclude '.venv/' --exclude '.env' --exclude '.env.*' --exclude 'tests/' \
    --exclude '.pytest_cache/' --exclude '.ruff_cache/' --exclude 'var/' --exclude '*.egg-info/' \
    "$REPO_ROOT/backend/" "$DEPLOY_ROOT/backend/"
sync_dir "$REPO_ROOT/database/" "$DEPLOY_ROOT/database/"
# node_modules e dist são geridos aqui (excluídos também do --delete).
sync_dir --exclude 'node_modules/' --exclude 'dist/' --exclude 'dist.new/' --exclude 'dist.old/' \
    --exclude '.env' --exclude '.env.*' --exclude '*.tsbuildinfo' \
    "$REPO_ROOT/frontend/" "$DEPLOY_ROOT/frontend/"

log "Configuração ($ENV_FILE)"
if [[ ! -f "$ENV_FILE" ]]; then
    install -m 0600 "$REPO_ROOT/deployment/env/api.env.example" "$ENV_FILE"
    set_env_line "APP_HOST=127.0.0.1"
    set_env_line "APP_PORT=$API_PORT"
    set_env_line "ATTACHMENTS_PATH=$DEPLOY_ROOT/data/attachments"
    set_env_line "DATABASE_DIR=$DEPLOY_ROOT/database"
    # O frontend é servido em HTTP: sem isto o browser não envia o cookie de sessão.
    set_env_line "COOKIE_SECURE=false"
    if [[ -f "$REPO_ROOT/.env" ]]; then
        while IFS= read -r line; do
            set_env_line "$line"
        done < <(grep -E '^MONGODB_[A-Z_]+=' "$REPO_ROOT/.env" || true)
    fi
    echo "Criado $ENV_FILE (credenciais MongoDB copiadas de $REPO_ROOT/.env, se existir)."
else
    echo "A manter $ENV_FILE existente."
fi
# Também para configurações criadas antes de existirem backups.
grep -q '^BACKUP_PATH=' "$ENV_FILE" || set_env_line "BACKUP_PATH=$DEPLOY_ROOT/backups"
grep -q '^MONGODB_PASSWORD=ALTERAR$' "$ENV_FILE" \
    && die "definir as credenciais MongoDB em $ENV_FILE e voltar a executar."
# A porta efetiva da API é a do ficheiro (pode ter sido alterada à mão).
API_PORT="$(sed -n 's/^APP_PORT=//p' "$ENV_FILE" | tail -n1)"
API_PORT="${API_PORT:-5000}"
API_READY_URL="http://127.0.0.1:$API_PORT/api/health/ready"
WEB_URL="http://127.0.0.1:$WEB_PORT"

log "Backend: dependências"
[[ -x "$DEPLOY_ROOT/venv/bin/python" ]] || python3 -m venv "$DEPLOY_ROOT/venv"
run_if_changed backend-requirements "$DEPLOY_ROOT/backend/requirements.txt" -- \
    "$DEPLOY_ROOT/venv/bin/pip" install --quiet --disable-pip-version-check \
    -r "$DEPLOY_ROOT/backend/requirements.txt"

log "Frontend: dependências e build"
cd "$DEPLOY_ROOT/frontend"
[[ -d node_modules ]] || rm -f "$STATE_DIR/frontend-lock"
run_if_changed frontend-lock package-lock.json -- npm ci --no-audit --no-fund
# Compila para dist.new e só troca no fim: um build falhado não estraga a versão publicada.
rm -rf dist.new dist.old
node_modules/.bin/tsc -b
node_modules/.bin/vite build --outDir dist.new --emptyOutDir
[[ -f dist.new/index.html ]] || die "build do frontend sem index.html."
[[ -d dist ]] && mv dist dist.old
mv dist.new dist
rm -rf dist.old

log "Migrations e seeds"
manage() {
    (cd "$DEPLOY_ROOT/backend" && VCCTF_ENV_FILE="$ENV_FILE" "$DEPLOY_ROOT/venv/bin/python" -m app.cli "$@")
}
manage migrate
manage seed

log "Serviços systemd do utilizador"
cat >"$UNIT_DIR/$API_SERVICE" <<EOF
# Gerado por deployment/scripts/deploy-local.sh — não editar (é reescrito em cada deploy).
[Unit]
Description=VCCTeamForge API (deploy local em $DEPLOY_ROOT)
After=network-online.target

[Service]
Type=exec
WorkingDirectory=$DEPLOY_ROOT/backend
Environment=VCCTF_ENV_FILE=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
ExecStart=$DEPLOY_ROOT/venv/bin/python -m app
Restart=on-failure
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=default.target
EOF

cat >"$UNIT_DIR/$WEB_SERVICE" <<EOF
# Gerado por deployment/scripts/deploy-local.sh — não editar (é reescrito em cada deploy).
[Unit]
Description=VCCTeamForge frontend (vite preview em 0.0.0.0:$WEB_PORT)
After=network-online.target $API_SERVICE
Wants=$API_SERVICE

[Service]
Type=exec
WorkingDirectory=$DEPLOY_ROOT/frontend
Environment=VITE_DEV_API_TARGET=http://127.0.0.1:$API_PORT
Environment=VITE_PREVIEW_ALLOWED_HOSTS=$ALLOWED_HOSTS
ExecStart=$(command -v node) $DEPLOY_ROOT/frontend/node_modules/vite/bin/vite.js preview --host 0.0.0.0 --port $WEB_PORT --strictPort
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

cat >"$UNIT_DIR/$SNAPSHOT_UNIT.service" <<EOF
# Gerado por deployment/scripts/deploy-local.sh — não editar (é reescrito em cada deploy).
[Unit]
Description=VCCTeamForge snapshots diários de relatório

[Service]
Type=oneshot
WorkingDirectory=$DEPLOY_ROOT/backend
Environment=VCCTF_ENV_FILE=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
ExecStart=$DEPLOY_ROOT/venv/bin/python -m app.cli report-snapshots
EOF

cat >"$UNIT_DIR/$SNAPSHOT_UNIT.timer" <<EOF
# Gerado por deployment/scripts/deploy-local.sh — não editar (é reescrito em cada deploy).
[Unit]
Description=VCCTeamForge snapshots diários de relatório (timer)

[Timer]
OnCalendar=*-*-* 23:50:00 UTC
Persistent=true
RandomizedDelaySec=5min

[Install]
WantedBy=timers.target
EOF

cat >"$UNIT_DIR/$BACKUP_UNIT.service" <<EOF
# Gerado por deployment/scripts/deploy-local.sh — não editar (é reescrito em cada deploy).
[Unit]
Description=VCCTeamForge backup diário (BD e anexos)

[Service]
Type=oneshot
WorkingDirectory=$DEPLOY_ROOT/backend
Environment=VCCTF_ENV_FILE=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
ExecStart=$DEPLOY_ROOT/venv/bin/python -m app.cli backup
UMask=0077
Nice=10
EOF

cat >"$UNIT_DIR/$BACKUP_UNIT.timer" <<EOF
# Gerado por deployment/scripts/deploy-local.sh — não editar (é reescrito em cada deploy).
[Unit]
Description=VCCTeamForge backup diário (timer)

[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true
RandomizedDelaySec=10min

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --quiet "$API_SERVICE" "$WEB_SERVICE"
systemctl --user enable --now --quiet "$SNAPSHOT_UNIT.timer" "$BACKUP_UNIT.timer"

wait_for() {
    local url="$1" service="$2" deadline=$((SECONDS + READY_TIMEOUT_SECONDS))
    until curl -fsS --max-time 5 "$url" >/dev/null 2>&1; do
        if ((SECONDS >= deadline)); then
            echo "$service não ficou pronto em ${READY_TIMEOUT_SECONDS}s ($url)." >&2
            systemctl --user --no-pager status "$service" >&2 || true
            journalctl --user --no-pager -n 50 -u "$service" >&2 || true
            exit 1
        fi
        sleep 2
    done
}

log "A reiniciar $API_SERVICE"
systemctl --user restart "$API_SERVICE"
wait_for "$API_READY_URL" "$API_SERVICE"

log "A reiniciar $WEB_SERVICE"
systemctl --user restart "$WEB_SERVICE"
wait_for "$WEB_URL/" "$WEB_SERVICE"
wait_for "$WEB_URL/api/health/ready" "$WEB_SERVICE"

# Sem linger os serviços do utilizador param no logout e não arrancam no boot.
if [[ "$(loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null)" != "yes" ]]; then
    loginctl enable-linger "$(id -un)" >/dev/null 2>&1 \
        || echo "AVISO: para os serviços arrancarem no boot e sobreviverem ao logout: sudo loginctl enable-linger $(id -un)"
fi

log "Deploy concluído"
echo "API:      $(curl -fsS --max-time 5 "$API_READY_URL")"
echo "Frontend: acessível em:"
for ip in $(hostname -I); do
    [[ "$ip" == *:* ]] && ip="[$ip]"
    echo "  http://$ip:$WEB_PORT/"
done
echo "Logs:     journalctl --user -u $API_SERVICE -u $WEB_SERVICE -f"
