---
maestru: "0.4"
type: work-spec
id: dev-008-spec
title: "DEV-008 - Logging, erros e health checks"
template: implementation-plan-v1
work-item: fase-1-fundacao/DEV-008
owner: developer
created: 2026-10-20
---

# DEV-008 - Logging, erros e health checks

## Overview

Dá à API observabilidade e respostas de erro consistentes: logging estruturado com request id e rotação, erros RFC 7807 (README §6) e health checks de liveness/readiness para o systemd/Nginx e para a monitorização (README §10) (DEV-008).

## Implementation

### Phase 1: Logging

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/app/core/config.py` | `LOG_LEVEL`, `LOG_FORMAT`, `LOG_FILE`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`, `HEALTH_MIN_FREE_DISK_MB` |
| Create | `backend/app/core/logging.py` | `configure_logging` (dictConfig), `JsonFormatter`, `RequestIdFilter`, `RotatingFileHandler` opcional |
| Create | `backend/app/core/middleware.py` | Middleware ASGI: request id (`X-Request-ID`), log por pedido, 500 RFC 7807 em exceções não tratadas |
| Modify | `backend/app/__main__.py` | `log_config=None`, `access_log=False` |

### Phase 2: Erros RFC 7807

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/core/errors.py` | `AppError` e subclasses (401/403/404/409/422/429); handlers para HTTPException, validação (sem eco de input) e `ConnectionFailure` (503) |
| Create | `backend/app/schemas/base.py` | `ApiModel` (snake_case → camelCase) |

### Phase 3: Health checks

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/services/health.py` | Ping MongoDB com latência; espaço livre no disco dos anexos |
| Modify | `backend/app/api/routes/health.py` | `/health`, `/health/live`, `/health/ready` (503 se MongoDB falhar) |

- [x] 38 testes passam (incluindo MongoDB 4.4 real)
- [x] Logs JSON verificados com o servidor em execução

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/core/config.py` | Modify | Novas settings |
| `backend/app/core/logging.py` | Create | Logging |
| `backend/app/core/middleware.py` | Create | Request id e log de pedidos |
| `backend/app/core/errors.py` | Create | Problem details |
| `backend/app/schemas/base.py` | Create | Base de DTOs |
| `backend/app/schemas/health.py` | Modify | Schemas de readiness |
| `backend/app/services/health.py` | Create | Verificações |
| `backend/app/api/routes/health.py` | Modify | Endpoints |
| `backend/app/main.py` | Modify | Integração |
| `backend/app/__main__.py` | Modify | Uvicorn sem logging próprio |
| `backend/tests/test_errors.py` | Create | Testes de erros |
| `backend/tests/test_health.py` | Create | Testes de health |
| `backend/tests/test_logging.py` | Create | Testes de logging |
| `backend/.env.example` | Modify | Variáveis novas |
| `backend/README.md` | Modify | Documentação |
