---
maestru: "0.4"
type: work-spec
id: dev-007-spec
title: "DEV-007 Spec"
template: implementation-plan-v1
work-item: fase-1-fundacao/DEV-007
owner: developer
created: 2026-10-20
---

# DEV-007 - Configurar Nginx e serviço systemd

## Overview

Deployment local conforme README §8: Nginx serve o frontend estático e encaminha `/api/` para a API em `127.0.0.1:5000`, executada por `VCCTeamForge-api.service` com utilizador de sistema dedicado e hardening systemd. Inclui variantes HTTP/HTTPS, cabeçalhos de segurança, exemplo de configuração de produção e scripts de instalação, deploy e manutenção. A API passa a recusar arrancar se `VCCTF_ENV_FILE` apontar para um ficheiro inexistente.

## Implementation

### Phase 1: systemd

| Action | File | Details |
|--------|------|---------|
| Create | `deployment/systemd/VCCTeamForge-api.service` | Utilizador `vccteamforge`, `VCCTF_ENV_FILE=/etc/VCCTeamForge/api.env`, `StateDirectory`, `MemoryMax=512M`, `ProtectSystem=strict`, filtro de syscalls, `MemoryDenyWriteExecute` |
| Modify | `backend/app/core/config.py` | `VCCTF_ENV_FILE` explícito tem de existir |

### Phase 2: Nginx

| Action | File | Details |
|--------|------|---------|
| Create | `deployment/nginx/vccteamforge.conf` | HTTP: upstream keepalive, `limit_req`, `log_format` com `$request_id` |
| Create | `deployment/nginx/vccteamforge-https.conf` | Redirect 80→443, TLS 1.2/1.3, HTTP/2, HSTS opcional |
| Create | `deployment/nginx/vccteamforge-locations.conf` | `/api/` (X-Forwarded-For substituído, X-Request-ID), `/api/docs` só loopback, `/assets/` imutável, `index.html` sem cache, fallback SPA, bloqueio de dotfiles |
| Create | `deployment/nginx/vccteamforge-security-headers.conf` | CSP sem inline scripts, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` |

### Phase 3: Scripts e configuração

| Action | File | Details |
|--------|------|---------|
| Create | `deployment/env/api.env.example` | Produção: JSON logs, caminhos absolutos, notas `COOKIE_SECURE` |
| Create | `deployment/scripts/install.sh` | Utilizador, diretorias, unit, site Nginx, wrapper (idempotente) |
| Create | `deployment/scripts/build-frontend.sh` | `npm ci && npm run build` |
| Create | `deployment/scripts/deploy.sh` | rsync, venv, compileall, migrate/seed, restart, espera readiness, publicação frontend, reload Nginx |
| Create | `deployment/scripts/vccteamforge-manage` | `python -m app.cli` como `vccteamforge` com o env de produção |
| Create | `deployment/README.md` | Procedimento completo e operação |

### Validação

- `shellcheck` e `bash -n` em todos os scripts; `systemd-analyze verify` e `systemd-analyze security --offline` (exposição 1.2).
- API executada com o hardening da unidade (`systemd-run --user`, incl. `MemoryDenyWriteExecute` e `SystemCallFilter`), 1 e 2 workers: readiness, login Argon2 e `/users/me` OK.
- Nginx 1.26.3 (pacote Debian extraído): `nginx -t` nas duas variantes e teste funcional HTTPS — redirect, fallback SPA, cache, cabeçalhos, propagação de `X-Request-ID`, `X-Forwarded-For` forjado ignorado, login via proxy.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `deployment/**` | Create | Unidade, Nginx, scripts, documentação |
| `backend/app/core/config.py` | Modify | Falha com `VCCTF_ENV_FILE` inexistente |
| `backend/tests/test_config.py` | Modify | Teste do caso acima |
| `README.md`, `backend/README.md` | Modify | Referências ao deployment |
