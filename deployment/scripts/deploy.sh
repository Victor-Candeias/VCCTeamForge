#!/usr/bin/env bash
# Publica a versão do repositório no servidor (executar como root a partir do repositório).
#   deployment/scripts/build-frontend.sh   # como utilizador normal, antes
#   sudo deployment/scripts/deploy.sh
# Passos: copia backend/database, atualiza o venv, aplica migrations e seeds,
# reinicia a API, espera pelo readiness, publica o frontend e recarrega o Nginx.
set -euo pipefail

APP_ROOT=/opt/VCCTeamForge
WEB_ROOT=/var/www/VCCTeamForge
SERVICE_NAME=VCCTeamForge-api.service
READY_URL=http://127.0.0.1:5000/api/health/ready
READY_TIMEOUT_SECONDS=60

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANAGE=/usr/local/sbin/vccteamforge-manage

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Executar como root." >&2
    exit 1
fi
if [[ ! -x "$MANAGE" || ! -f "/etc/systemd/system/$SERVICE_NAME" ]]; then
    echo "Servidor não preparado: executar primeiro deployment/scripts/install.sh." >&2
    exit 1
fi
if [[ ! -f "$REPO_ROOT/frontend/dist/index.html" ]]; then
    echo "frontend/dist em falta: executar deployment/scripts/build-frontend.sh." >&2
    exit 1
fi

sync_dir() {
    rsync -a --delete --chown=root:root --chmod=D755,F644 \
        --exclude '__pycache__/' --exclude '*.pyc' "$@"
}

echo "==> A copiar código"
sync_dir --exclude '.venv/' --exclude '.env' --exclude '.env.*' --exclude 'tests/' \
    --exclude '.pytest_cache/' --exclude '.ruff_cache/' --exclude 'var/' --exclude '*.egg-info/' \
    "$REPO_ROOT/backend/" "$APP_ROOT/backend/"
sync_dir "$REPO_ROOT/database/" "$APP_ROOT/database/"
sync_dir "$REPO_ROOT/deployment/" "$APP_ROOT/deployment/"
chmod 0755 "$APP_ROOT"/deployment/scripts/*

echo "==> A atualizar dependências"
if [[ ! -x "$APP_ROOT/venv/bin/python" ]]; then
    python3 -m venv "$APP_ROOT/venv"
fi
"$APP_ROOT/venv/bin/pip" install --quiet --disable-pip-version-check -r "$APP_ROOT/backend/requirements.txt"
# O código é só de leitura para o serviço: pré-compilar o bytecode.
"$APP_ROOT/venv/bin/python" -m compileall -q "$APP_ROOT/backend/app" "$APP_ROOT/database/migrations"

echo "==> Migrations e seeds"
"$MANAGE" migrate
"$MANAGE" seed

echo "==> A reiniciar $SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
deadline=$((SECONDS + READY_TIMEOUT_SECONDS))
until curl -fsS --max-time 5 "$READY_URL" >/dev/null 2>&1; do
    if ((SECONDS >= deadline)); then
        echo "A API não ficou pronta em ${READY_TIMEOUT_SECONDS}s." >&2
        systemctl --no-pager status "$SERVICE_NAME" >&2 || true
        journalctl --no-pager -n 50 -u "$SERVICE_NAME" >&2 || true
        exit 1
    fi
    sleep 2
done

echo "==> A publicar frontend"
# Assets primeiro e index.html no fim, para clientes nunca verem um index com assets em falta.
rsync -a --chown=root:root --chmod=D755,F644 --exclude 'index.html' \
    "$REPO_ROOT/frontend/dist/" "$WEB_ROOT/"
rsync -a --delete-after --chown=root:root --chmod=D755,F644 \
    "$REPO_ROOT/frontend/dist/" "$WEB_ROOT/"

nginx -t
systemctl reload nginx

echo "Deploy concluído: $(curl -fsS --max-time 5 "$READY_URL")"
