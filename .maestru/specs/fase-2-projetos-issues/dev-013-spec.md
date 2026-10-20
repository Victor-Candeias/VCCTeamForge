---
maestru: "0.4"
type: work-spec
id: dev-013-spec
title: "DEV-013 - Anexos e controlo de acesso"
template: implementation-plan-v1
work-item: fase-2-projetos-issues/DEV-013
owner: developer
created: 2026-10-20
---

# DEV-013 - Anexos e controlo de acesso

## Overview

Anexos em issues guardados no disco local (`ATTACHMENTS_PATH`) com metadados na collection `attachments` (README §4.3, §5.1 e §10): limites de tamanho, validação de tipo, nomes internos aleatórios e acesso apenas a quem pode ver a issue. Prepara as evidências da Fase 4.

### Regras

| Regra | Decisão |
|-------|---------|
| Armazenamento | `<ATTACHMENTS_PATH>/<projectId>/<yyyy>/<mm>/<token hex 32>`; diretórios `0750`, ficheiros `0640`; nunca usar o nome original no disco |
| Escrita | Streaming para ficheiro temporário no mesmo diretório e `os.replace` atómico; SHA-256 e tamanho calculados durante a escrita; limite verificado durante o streaming (não confiar em `Content-Length`) |
| Limites | `ATTACHMENTS_MAX_BYTES` (default 20 MiB, abaixo dos 25 MiB do Nginx), `ATTACHMENTS_MAX_PER_ISSUE` (default 50); excedido → 413/422 |
| Tipos | Lista branca por extensão + MIME: `png`, `jpg`, `jpeg`, `gif`, `webp`, `pdf`, `txt`, `log`, `md`, `csv`, `json`, `zip`, `docx`, `xlsx`, `pptx`. Assinatura (magic bytes) verificada para imagens, PDF e formatos ZIP; ficheiros de texto rejeitados se contiverem bytes nulos |
| Nome | `originalName` normalizado (sem caminhos, caracteres de controlo; ≤ 200) |
| Upload | `issues:write` + acesso ao projeto; projeto arquivado → 422 |
| Download | `issues:read` + acesso; `Content-Disposition: attachment` com `filename*` RFC 5987, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox`, `Cache-Control: private, no-store`; imagens podem ser pré-visualizadas (`?inline=1` só para tipos de imagem) |
| Remover | Autor do upload, lead do projeto ou admin; metadados com `deletedAt`/`deletedBy` e ficheiro apagado do disco |
| Consistência | Ficheiro escrito antes dos metadados; se a inserção falhar, o ficheiro é apagado (compensação). Script `vccteamforge-manage` passa a reportar órfãos (`attachments-check`) |
| Histórico/auditoria | `attachment_added`/`attachment_removed` no `issue_history`; `attachment.created`/`attachment.deleted` em `audit_logs` |
| Dependência | `python-multipart` (FastAPI `UploadFile`) |

### Contratos API

| Método | Endpoint | Resposta |
|--------|----------|----------|
| GET | `/api/issues/{id}/attachments` | Lista de metadados (sem caminho interno) |
| POST | `/api/issues/{id}/attachments` | `multipart/form-data` campo `file` → 201 + metadados |
| GET | `/api/attachments/{id}/content` | Conteúdo do ficheiro |
| DELETE | `/api/attachments/{id}` | 204 |

## Implementation

### Phase 1: Testes

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_attachments.py` | Upload/download/remoção, nome aleatório no disco, path traversal no nome, tipo não permitido, assinatura falsa, limite de tamanho e por issue, acesso de utilizador sem projeto → 404, cabeçalhos de segurança, compensação quando os metadados falham, histórico e auditoria |

### Phase 2: Backend

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/pyproject.toml`, `backend/requirements.txt` | `python-multipart` |
| Modify | `backend/app/core/config.py`, `backend/.env.example`, `deployment/env/api.env.example` | `ATTACHMENTS_MAX_BYTES`, `ATTACHMENTS_MAX_PER_ISSUE` |
| Create | `backend/app/domain/attachments.py` | Lista branca, assinaturas, `sanitize_filename` |
| Create | `backend/app/storage/attachments.py` | `AttachmentStorage` (escrita atómica com limite, leitura, remoção, resolução segura de caminhos) |
| Create | `backend/app/repositories/attachments.py` | Metadados |
| Create | `backend/app/services/attachments.py` | Regras, compensação, histórico e auditoria |
| Create | `backend/app/schemas/attachments.py` | DTO |
| Create | `backend/app/api/routes/attachments.py` | Endpoints |
| Modify | `backend/app/api/router.py` | Incluir rotas |
| Modify | `database/indexes/indexes.json` | `attachments_issueId_createdAt` |
| Modify | `backend/app/cli.py` | `attachments-check` (ficheiros órfãos e metadados sem ficheiro) |

### Phase 3: Frontend

| Action | File | Details |
|--------|------|---------|
| Modify | `frontend/src/services/apiClient.ts` | Não definir `Content-Type` para `FormData` |
| Create | `frontend/src/services/attachments.ts` | Cliente |
| Create | `frontend/src/features/issues/IssueAttachments.tsx` | Lista, upload (validação de tamanho no cliente), download e remoção |
| Modify | `frontend/src/features/issues/IssueDetailPage.tsx` | Secção Anexos |
| Create | `frontend/src/features/issues/attachments.test.tsx` | Upload, erro de tamanho, remoção |

- [ ] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/tests/test_attachments.py` | Create | Testes |
| `backend/pyproject.toml`, `backend/requirements.txt` | Modify | Dependência multipart |
| `backend/app/core/config.py`, `backend/.env.example`, `deployment/env/api.env.example` | Modify | Limites |
| `backend/app/domain/attachments.py` | Create | Validação |
| `backend/app/storage/attachments.py` | Create | Armazenamento em disco |
| `backend/app/repositories/attachments.py` | Create | Metadados |
| `backend/app/services/attachments.py` | Create | Regras |
| `backend/app/schemas/attachments.py` | Create | DTO |
| `backend/app/api/routes/attachments.py`, `backend/app/api/router.py` | Create/Modify | API |
| `backend/app/cli.py` | Modify | Verificação de órfãos |
| `database/indexes/indexes.json` | Modify | Índices |
| `frontend/src/services/{apiClient,attachments}.ts`, `frontend/src/features/issues/*` | Create/Modify | UI |
| `backend/README.md`, `deployment/README.md` | Modify | Documentação |
