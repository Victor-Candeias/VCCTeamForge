---
maestru: "0.4"
type: work-track
id: fase-1-fundacao
title: Fase 1 - Fundação
created: 2026-10-20
description: "Estrutura, autenticação, permissões, MongoDB 4.4 e Linux (M1)"
owner: developer
status: active
---

# fase-1-fundacao: Fase 1 - Fundação

## Summary

<!-- maestru:work-items-list -->
| ID | Title | Status | Created | Owner | Priority | Completed | Template | Blocked By | Spec |
|---|---|---|---|---|---|---|---|---|---|
| DEV-001 | Criar projeto backend modular em Python/FastAPI | done | 2026-10-20 | developer | high | 2026-10-20 |  |  | [DEV-001](../specs/fase-1-fundacao/dev-001-spec.md) |
| DEV-002 | Criar projeto React/Vite/TypeScript | done | 2026-10-20 | developer | high | 2026-10-20 |  |  | [DEV-002](../specs/fase-1-fundacao/dev-002-spec.md) |
| DEV-003 | Implementar configuração por ambiente | done | 2026-10-20 | developer | high | 2026-10-20 |  | DEV-001 | [DEV-003](../specs/fase-1-fundacao/dev-003-spec.md) |
| DEV-004 | Implementar acesso MongoDB 4.4 com PyMongo e testes de compatibilidade | backlog | 2026-10-20 | developer | critical |  |  | DEV-001, DEV-003 |  |
| DEV-005 | Criar migrations/seeds e índices idempotentes | backlog | 2026-10-20 | developer | high |  |  | DEV-004 |  |
| DEV-006 | Implementar login/logout, sessão e RBAC | backlog | 2026-10-20 | developer | critical |  |  | DEV-004, DEV-005 |  |
| DEV-007 | Configurar Nginx e serviço systemd | backlog | 2026-10-20 | developer | medium |  |  | DEV-001, DEV-002 |  |
| DEV-008 | Configurar logging, tratamento de erros e health checks | backlog | 2026-10-20 | developer | medium |  |  | DEV-001 |  |
<!-- /maestru:work-items-list -->
