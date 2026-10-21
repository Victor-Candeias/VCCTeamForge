---
maestru: "0.4"
type: work-spec
id: dev-025-spec
title: "DEV-025 Spec — Testes de carga, segurança e restauro"
template: implementation-plan-v1
work-item: fase-6-estabilizacao/DEV-025
owner: developer
created: 2026-10-21
---

# DEV-025 Testes de carga, segurança e restauro

## Overview

Fecho operacional antes da produção (README §10 "Backups", §12 "Segurança", §14.8): backups diários da BD e dos anexos com teste de restauro e RPO/RTO documentados; verificação automática dos controlos de acesso de todas as rotas; ferramenta de carga com medições numa carga representativa e validação dos recursos (limite de 512 MiB da API).

### Regras

| Regra | Decisão |
|-------|---------|
| Ferramenta de backup | Python puro (PyMongo + `tarfile`), sem `mongodump` (não instalado; evita dependência de versão das database-tools). BSON em bruto (`RawBSONDocument`) preserva todos os tipos |
| Formato | `.tar.gz` com `db/<collection>.bson`, `attachments/<storageKey>` e `manifest.json` no fim (formato, data, BD, versão MongoDB, opções/índices, contagens, SHA-256 e tamanho por membro) |
| Dados transitórios | `sessions`, `login_attempts`, `maintenance_locks`: só estrutura (sem segredos de sessão nos backups; restauro termina sessões) |
| Escrita | `.partial` com `0600`, `fsync` e `os.replace`; nunca fica um arquivo a meio com nome válido |
| Agenda e retenção | Timer systemd diário 02:30 (`Persistent=true`); `BACKUP_RETENTION=14` só sobre backups agendados |
| Verificação | `backup-verify` lê o arquivo em streaming e valida nomes (sem travessia de caminhos, chaves de anexos válidas), checksums, tamanhos e contagens BSON |
| Restauro | Exige `--yes` e a API parada. Primeiro verifica o arquivo e o espaço livre, depois cria um backup de segurança `pre-restore`. Por cada collection: drop, `create_collection(options)`, inserção em lotes de 500 e índices; as collections que não estão no backup são removidas. Os anexos são preparados em `.restore-*`, dentro da raiz, e trocados no fim. Se falhar a meio, a mensagem indica o comando para repor o backup de segurança |
| Cópia externa | Modelo *pull* (rsync a partir de outro dispositivo), cifrada fora do servidor; não automatizada no servidor |
| RPO/RTO | RPO ≤ 24 h; RTO ≤ 1 h (servidor disponível) / ≤ 4 h (máquina nova) |
| Segurança das rotas | Inventário a partir do OpenAPI: privadas → 401 sem sessão; escritas → 403 sem CSRF/CSRF forjado; lista explícita de rotas públicas |
| Carga | `tools/loadtest.py` só com a biblioteca padrão (pode correr em qualquer posto ou no servidor); utilizadores com sessão própria, operações ponderadas, p50/p95/p99, limites com código de saída |

## Implementation

### Phase 1: Backup e restauro

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/maintenance/backup.py` | `create_backup`, `list_backups`, `prune_backups`, `verify_backup`, `restore_backup`, verificação de espaço livre |
| Modify | `backend/app/cli.py` | `backup [--output] [--keep]`, `backup-verify`, `restore --yes [--no-safety-backup]`, último backup em `status` |
| Modify | `backend/app/core/config.py` | `BACKUP_PATH` (absoluto em produção), `BACKUP_RETENTION` |
| Create | `deployment/systemd/VCCTeamForge-backup.{service,timer}` | Oneshot com o hardening da API, escrita só em `/var/backups/VCCTeamForge`, prioridade baixa |
| Modify | `deployment/scripts/install.sh`, `deploy-local.sh` | Diretoria de backups, units e timer ativos; `BACKUP_PATH` acrescentado a `api.env` existentes no deploy local |
| Modify | `deployment/env/api.env.example`, `backend/.env.example`, `.gitignore` | Variáveis novas; backups locais fora do Git |
| Create | `backend/tests/test_backup.py` | Ida e volta via CLI (tipos, validador, índices parciais/únicos, sessões, anexos, backup de segurança), arquivos adulterados/truncados, espaço insuficiente, falha a meio, retenção e `status` |

### Phase 2: Segurança

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_security.py` | 401/403 para todas as rotas do OpenAPI; rotas públicas explícitas |

#### Revisão de segurança

| Controlo | Evidência |
|----------|-----------|
| Autenticação e CSRF | Cookie de sessão `HttpOnly`, `SameSite`, `Secure` em produção; double-submit CSRF em todas as escritas (`test_security.py`, todas as rotas) |
| Passwords | Argon2id (`time_cost=2`, `memory_cost=19 MiB`), mínimos OWASP |
| Força bruta | Rate limiting por email e por IP (`LOGIN_MAX_FAILURES_*`); `X-Forwarded-For` só de proxies confiáveis |
| Autorização | Permissões por papel e acesso por projeto (404 sem acesso), testadas por domínio (DEV-005 a DEV-024) |
| Nginx | `server_tokens off`, CSP sem scripts inline, `X-Frame-Options`, `nosniff`, `limit_req` 20 r/s, `client_max_body_size 25m`, `/api/docs` só local |
| systemd | Utilizador sem privilégios, `ProtectSystem=strict`, filtro de syscalls, `MemoryDenyWriteExecute`, `MemoryMax=512M` |
| Anexos e exportações | Extensão e conteúdo validados, chaves de armazenamento sem travessia; fórmulas neutralizadas em CSV/XLSX |
| Backups | `0600`/`0750`, nomes do tar validados antes de restaurar, checksums |
| Dependências | `npm audit --omit=dev`: 0 vulnerabilidades; `pip-audit -r requirements.txt`: nenhuma vulnerabilidade conhecida (2026-10-21) |

Riscos residuais (aceites, documentados no `deployment/README.md`):

- MongoDB 4.4 já sem suporte do fabricante: manter o servidor só no loopback, com autenticação, e planear a migração.
- O deploy local (`deploy-local.sh`) usa HTTP sem os cabeçalhos do Nginx: só para redes de confiança.
- Os backups não são cifrados no servidor (contêm hashes de passwords): a proteção vem das permissões e de cifrar as cópias externas.
- O backup corre com a API ativa, sem snapshot atómico: as escritas feitas durante a cópia (segundos) podem ficar só em parte.

### Phase 3: Carga e recursos

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tools/loadtest.py` | Sessões keep-alive com cookies/CSRF, `--seed-issues`, `--write`, relatório por operação, limites `--max-p95-ms`/`--max-error-rate` |
| Create | `backend/tests/test_loadtest.py` | Uvicorn real numa porta efémera; todas as operações sem erros |
| Modify | `deployment/README.md`, `backend/README.md` | Backups, restauro, RPO/RTO, teste periódico, carga, monitorização, medições |

Medições (portátil x86_64 de 4 núcleos, 1,9 GB de RAM, eMMC, MongoDB 4.4, 1 worker, ~2 000 issues, 50 anexos de 1 MiB):

| Medição | Resultado |
|---------|-----------|
| 20 utilizadores, pausa 3 s | 6,3 pedidos/s, p95 520 ms, 0 erros, RSS 173 MiB |
| 20 utilizadores, pausa 0,5 s (stress) | 19,2 pedidos/s, p95 1 172 ms (quadro 1 548 ms, métricas 1 490 ms), 0 erros, RSS 275 MiB |
| Backup (~6 700 documentos + 50 MiB) | 7 s, arquivo de 50 MiB; verificação 1,3 s |
| Restauro (o mesmo arquivo, com backup de segurança) | 11,7 s; `status` e `attachments-check` sem inconsistências |

A primeira tentativa de restauro, num tmpfs quase cheio, falhou com ENOSPC a meio. Daí vieram a verificação prévia do espaço livre e a mensagem que indica como repor o backup de segurança.

- [x] `pytest`, `ruff`, `npm test` passam

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/maintenance/backup.py` | Create | Backup, verificação e restauro |
| `backend/app/cli.py` | Modify | Comandos `backup`, `backup-verify`, `restore`; estado do último backup |
| `backend/app/core/config.py` | Modify | `BACKUP_PATH`, `BACKUP_RETENTION` |
| `backend/tools/loadtest.py` | Create | Teste de carga |
| `backend/tests/test_backup.py`, `test_security.py`, `test_loadtest.py`, `test_config.py` | Create/Modify | Testes |
| `deployment/systemd/VCCTeamForge-backup.{service,timer}` | Create | Backup diário |
| `deployment/scripts/install.sh`, `deploy-local.sh` | Modify | Instalação dos backups |
| `deployment/env/api.env.example`, `backend/.env.example`, `.gitignore` | Modify | Configuração |
| `deployment/README.md`, `backend/README.md` | Modify | Operação e medições |
