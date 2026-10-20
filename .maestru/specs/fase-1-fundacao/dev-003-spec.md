---
maestru: "0.4"
type: work-spec
id: dev-003-spec
title: "DEV-003 - Configuração por ambiente"
template: implementation-plan-v1
work-item: fase-1-fundacao/DEV-003
owner: developer
created: 2026-10-20
---

# DEV-003 - Configuração por ambiente

## Overview

Centraliza a configuração da API (README §8) num objeto `Settings` tipado (pydantic-settings), lido de variáveis de ambiente e de ficheiro `.env`, com regras mais estritas em produção (DEV-003).

## Implementation

### Phase 1: Settings

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/core/config.py` | `Settings`, `load_settings()`, `get_settings()` (cache); `VCCTF_ENV_FILE` |
| Modify | `backend/app/main.py` | `create_app(settings)`; `app.state.settings`; OpenAPI só se `API_DOCS_ENABLED` |
| Create | `backend/app/api/deps.py` | Dependência `get_app_settings` |
| Modify | `backend/app/__main__.py` | Host, porta, workers e proxy headers a partir das settings |
| Create | `backend/.env.example` | Modelo de configuração sem segredos |

Regras: env > `.env` > omissão; valores vazios ignorados; `MONGODB_AUTH_SOURCE` assume a BD; utilizador e password em conjunto; em produção credenciais obrigatórias, `ATTACHMENTS_PATH` absoluto e docs desativados por omissão.

### Phase 2: Testes

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_config.py` | Precedência, validações e docs por ambiente |

- [x] `pytest` e `ruff` passam
- [x] `APP_PORT` respeitado por `python -m app`

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/pyproject.toml` | Modify | Dependência pydantic-settings |
| `backend/requirements.txt` | Modify | Lock atualizado |
| `backend/app/core/config.py` | Create | Settings |
| `backend/app/api/deps.py` | Create | Injeção das settings |
| `backend/app/main.py` | Modify | Usa settings |
| `backend/app/__main__.py` | Modify | Usa settings |
| `backend/.env.example` | Create | Exemplo |
| `backend/tests/test_config.py` | Create | Testes |
| `backend/README.md` | Modify | Documentação das variáveis |
