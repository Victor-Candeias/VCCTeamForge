#!/usr/bin/env bash
# Compila o frontend (frontend/dist) para publicação pelo Nginx.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT/frontend"

npm ci --no-audit --no-fund
npm run build

echo "Frontend compilado em $REPO_ROOT/frontend/dist"
