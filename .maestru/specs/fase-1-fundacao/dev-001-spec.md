---
maestru: "0.4"
type: work-spec
id: dev-001-spec
title: "DEV-001 - Backend modular Python/FastAPI"
template: implementation-plan-v1
work-item: fase-1-fundacao/DEV-001
owner: developer
created: 2026-10-20
---

# DEV-001 - Backend modular Python/FastAPI

## Overview

Cria a base do backend (monólito modular FastAPI) definida no README §2 e §7, com camadas Routers → Services → Domain → Repositories (PyMongo) e Schemas Pydantic (DTOs). Serve de fundação para todos os restantes work-items (DEV-001).

## Implementation

### Phase 1: Estrutura e dependências

#### Step 1.1: Projeto Python

| Action | File | Details |
|--------|------|---------|
| Create | `backend/pyproject.toml` | Metadados, dependências com limites, configuração pytest e ruff |
| Create | `backend/requirements.txt` | Dependências de runtime fixadas (lock) |
| Create | `backend/requirements-dev.txt` | Dependências de teste/lint |

#### Step 1.2: Camadas da aplicação

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/{api,services,domain,repositories,schemas,core}/` | Pacotes vazios com docstring de responsabilidade |
| Create | `backend/app/main.py` | `create_app()` + instância `app`; router `/api` |
| Create | `backend/app/api/router.py` | Agregador de routers |
| Create | `backend/app/api/routes/health.py` | `GET /api/health` mínimo |
| Create | `backend/app/__main__.py` | Arranque com Uvicorn (`python -m app`) |

### Phase 2: Testes

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_app.py` | Smoke test de `create_app()` e `/api/health` |
| Run | `pytest`, `ruff check` | Validação |

- [x] `pytest` passa
- [x] `ruff check` sem erros

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/pyproject.toml` | Create | Projeto Python |
| `backend/requirements.txt` | Create | Dependências fixadas |
| `backend/requirements-dev.txt` | Create | Dependências de desenvolvimento |
| `backend/app/**` | Create | Estrutura modular |
| `backend/tests/**` | Create | Testes |
| `backend/README.md` | Create | Instruções de desenvolvimento |
