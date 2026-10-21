#!/usr/bin/env bash
# Preparação única do servidor para o VCCTeamForge (executar como root a partir do repositório).
#   sudo deployment/scripts/install.sh [--https]
# Idempotente: não sobrescreve /etc/VCCTeamForge/api.env existente.
set -euo pipefail

APP_ROOT=/opt/VCCTeamForge
CONFIG_DIR=/etc/VCCTeamForge
WEB_ROOT=/var/www/VCCTeamForge
STATE_DIR=/var/lib/VCCTeamForge
BACKUP_DIR=/var/backups/VCCTeamForge
SERVICE_USER=vccteamforge
SERVICE_NAME=VCCTeamForge-api.service
SNAPSHOT_UNIT=VCCTeamForge-report-snapshots
BACKUP_UNIT=VCCTeamForge-backup

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

site_conf="$DEPLOY_DIR/nginx/vccteamforge.conf"
case "${1:-}" in
    "") ;;
    --https) site_conf="$DEPLOY_DIR/nginx/vccteamforge-https.conf" ;;
    *) echo "Uso: $0 [--https]" >&2; exit 2 ;;
esac

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Executar como root." >&2
    exit 1
fi

for cmd in python3 nginx systemctl rsync runuser curl; do
    command -v "$cmd" >/dev/null || { echo "Comando em falta: $cmd" >&2; exit 1; }
done
python3 -c 'import sys, venv; sys.exit(sys.version_info < (3, 11))' \
    || { echo "É necessário Python >= 3.11 com o módulo venv (python3-venv)." >&2; exit 1; }

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --user-group --home-dir /nonexistent --no-create-home \
        --shell /usr/sbin/nologin "$SERVICE_USER"
    echo "Criado utilizador de sistema $SERVICE_USER"
fi

install -d -o root -g root -m 0755 "$APP_ROOT" "$WEB_ROOT"
install -d -o root -g "$SERVICE_USER" -m 0750 "$CONFIG_DIR"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$STATE_DIR" "$STATE_DIR/attachments" \
    "$BACKUP_DIR"

if [[ ! -e "$CONFIG_DIR/api.env" ]]; then
    install -o root -g "$SERVICE_USER" -m 0640 "$DEPLOY_DIR/env/api.env.example" "$CONFIG_DIR/api.env"
    echo "ATENÇÃO: editar $CONFIG_DIR/api.env (credenciais MongoDB, COOKIE_SECURE) antes do deploy."
fi

for unit in "$SERVICE_NAME" "$SNAPSHOT_UNIT.service" "$SNAPSHOT_UNIT.timer" \
    "$BACKUP_UNIT.service" "$BACKUP_UNIT.timer"; do
    install -o root -g root -m 0644 "$DEPLOY_DIR/systemd/$unit" "/etc/systemd/system/$unit"
done
install -o root -g root -m 0755 "$DEPLOY_DIR/scripts/vccteamforge-manage" /usr/local/sbin/vccteamforge-manage

install -d -m 0755 /etc/nginx/snippets /etc/nginx/sites-available /etc/nginx/sites-enabled
install -o root -g root -m 0644 "$DEPLOY_DIR/nginx/vccteamforge-security-headers.conf" \
    /etc/nginx/snippets/vccteamforge-security-headers.conf
install -o root -g root -m 0644 "$DEPLOY_DIR/nginx/vccteamforge-locations.conf" \
    /etc/nginx/snippets/vccteamforge-locations.conf
install -o root -g root -m 0644 "$site_conf" /etc/nginx/sites-available/vccteamforge
ln -sfn /etc/nginx/sites-available/vccteamforge /etc/nginx/sites-enabled/vccteamforge

# O site por omissão do Debian também reclama default_server na porta 80.
if [[ -L /etc/nginx/sites-enabled/default ]]; then
    rm /etc/nginx/sites-enabled/default
    echo "Desativado o site Nginx 'default'."
fi

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl enable --now "$SNAPSHOT_UNIT.timer" "$BACKUP_UNIT.timer"
nginx -t

echo "Instalação concluída. Próximos passos: editar $CONFIG_DIR/api.env e executar deploy.sh."
