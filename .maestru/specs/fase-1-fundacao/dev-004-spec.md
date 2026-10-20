---
maestru: "0.4"
type: work-spec
id: dev-004-spec
title: "DEV-004 - Acesso MongoDB 4.4 com PyMongo"
template: implementation-plan-v1
work-item: fase-1-fundacao/DEV-004
owner: developer
created: 2026-10-20
---

# DEV-004 - Acesso MongoDB 4.4 com PyMongo

## Overview

Liga a API ao MongoDB 4.4 existente (restrição obrigatória do README §1) com PyMongo síncrono, valida a versão do servidor e cobre com testes de integração as funcionalidades de que a aplicação depende (DEV-004).

## Implementation

### Phase 1: Driver e ligação

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/pyproject.toml` | `pymongo>=4.19,<4.20` (4.18+ exige servidor ≥ 4.4) |
| Create | `backend/app/repositories/mongo.py` | `create_client` (tz_aware, pool, timeouts, credenciais), `check_server_compatibility`, `ping`, `get_database` |
| Create | `backend/app/repositories/base.py` | `MongoRepository` base |
| Create | `backend/app/repositories/counters.py` | Sequências atómicas com `$inc` + upsert |
| Modify | `backend/app/main.py` | Lifespan: cria cliente por worker, verifica versão, fecha no fim; cliente injetável |
| Modify | `backend/app/api/deps.py` | Dependência `get_db` |

### Phase 2: Testes

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/conftest.py` | BD de teste descartável; skip/fail via `VCCTF_REQUIRE_MONGO` |
| Create | `backend/tests/test_mongo.py` | Unitários: versões, opções do cliente, arranque sem BD |
| Create | `backend/tests/test_mongo_compat.py` | Integração: versão, UTC/ObjectId, `$inc` concorrente, índices únicos/TTL/parciais, controlo otimista, `$facet`, updates com pipeline |

- [x] 24 testes passam contra MongoDB 4.4.29 real (instância temporária)
- [x] Sem servidor acessível os testes de integração são ignorados

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/pyproject.toml` | Modify | PyMongo |
| `backend/requirements.txt` | Modify | Lock |
| `backend/app/repositories/mongo.py` | Create | Cliente e compatibilidade |
| `backend/app/repositories/base.py` | Create | Base de repositórios |
| `backend/app/repositories/counters.py` | Create | Contadores atómicos |
| `backend/app/main.py` | Modify | Lifespan |
| `backend/app/api/deps.py` | Modify | `get_db` |
| `backend/tests/conftest.py` | Create | Fixtures |
| `backend/tests/test_mongo.py` | Create | Testes unitários |
| `backend/tests/test_mongo_compat.py` | Create | Testes de compatibilidade |
| `backend/README.md` | Modify | Documentação |
