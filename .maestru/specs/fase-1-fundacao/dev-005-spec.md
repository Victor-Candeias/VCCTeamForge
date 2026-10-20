---
maestru: "0.4"
type: work-spec
id: dev-005-spec
title: "DEV-005 Spec"
template: implementation-plan-v1
work-item: fase-1-fundacao/DEV-005
owner: developer
created: 2026-10-20
---

# DEV-005 - Migrations, seeds e índices idempotentes

## Overview

Provisionamento reprodutível do MongoDB 4.4 (README §5.5/§5.6): migrations versionadas, índices declarativos e dados iniciais. Tudo é idempotente e corre pela CLI (`python -m app.cli`), nunca por pedido HTTP. O comando `create-admin` passa para o DEV-006, porque depende do hashing de passwords.

## Implementation

### Phase 1: Definições em `database/`

| Action | File | Details |
|--------|------|---------|
| Create | `database/indexes/indexes.json` | Índices do README §5.5, mais `projects.memberIds`, `sessions` (tokenHash único, TTL expiresAt), `login_attempts` (TTL 24h) e `audit_logs` |
| Create | `database/migrations/0001_initial_collections.py` | Collections da fase 1, `sessions` e `login_attempts` |
| Create | `database/seed/settings.json` | `settings.global`: tipos, estados (provisórios até §14.7), prioridades e parâmetros Scrum |

### Phase 2: Runner e CLI

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/maintenance/indexes.py` | Valida todos os índices antes de criar; deteta conflitos de nome/opções; aceita índice equivalente com outro nome |
| Create | `backend/app/maintenance/migrations.py` | Descoberta `NNNN_nome.py`, registo em `schema_migrations` com checksum, lock com expiração em `maintenance_locks` |
| Create | `backend/app/maintenance/seeds.py` | Upsert `$setOnInsert` por `_id` |
| Create | `backend/app/cli.py` | `status`, `migrate [--dry-run]`, `seed`; código de saída 1 em erro |
| Modify | `backend/app/core/config.py` | `DATABASE_DIR` |

- [x] `migrate` e `seed` repetidos não alteram nada (testado contra MongoDB 4.4.29)
- [x] Falhas de migration não ficam registadas; conflitos de índices abortam sem efeitos parciais

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `database/indexes/indexes.json` | Create | Índices |
| `database/migrations/0001_initial_collections.py` | Create | Migration inicial |
| `database/seed/settings.json` | Create | Parâmetros globais |
| `backend/app/maintenance/*.py` | Create | Runner |
| `backend/app/cli.py` | Create | CLI |
| `backend/app/core/config.py` | Modify | `DATABASE_DIR` |
| `backend/tests/test_maintenance.py` | Create | Testes |
| `backend/README.md`, `backend/.env.example` | Modify | Documentação |
