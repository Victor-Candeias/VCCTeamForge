#!/usr/bin/env bash
# Regenera requirements.txt (dependências de runtime fixadas) a partir de pyproject.toml.
set -euo pipefail

cd "$(dirname "$0")/.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp" build ./*.egg-info' EXIT

python3 -m venv "$tmp/venv"
"$tmp/venv/bin/pip" install --quiet .
{
  echo "# Gerado por scripts/lock-requirements.sh — não editar à mão"
  "$tmp/venv/bin/pip" freeze --exclude-editable | grep -v '^vccteamforge-api' | sort -f
} > requirements.txt
echo "requirements.txt atualizado"
