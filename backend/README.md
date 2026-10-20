# VCCTeamForge — Backend

API FastAPI (monólito modular) sobre MongoDB 4.4 com PyMongo síncrono.

## Arquitetura

```text
app/
├── api/           # routers FastAPI (HTTP apenas)
├── services/      # lógica de aplicação
├── domain/        # entidades e regras, sem dependências de framework
├── repositories/  # acesso PyMongo (única camada que conhece collections)
├── schemas/       # DTOs Pydantic (contratos da API)
├── core/          # configuração, logging, erros, segurança
└── main.py        # create_app()
```

Fluxo: **Routers → Services → Domain → Repositories**. Os documentos MongoDB nunca são devolvidos
diretamente; a API expõe sempre schemas Pydantic.

## Desenvolvimento

Requer Python 3.11+.

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt -e .
.venv/bin/python -m app            # API em http://127.0.0.1:5000/api
.venv/bin/pytest                   # testes
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Documentação OpenAPI: `http://127.0.0.1:5000/api/docs`.

## Configuração

A configuração é lida por `app/core/config.py` (pydantic-settings) com a seguinte prioridade:

1. variáveis de ambiente do processo;
2. ficheiro `.env` (por omissão `./.env`, opcional; outro caminho via `VCCTF_ENV_FILE`, que tem de existir — a API recusa arrancar se não existir);
3. valores por omissão.

Partir de `.env.example` (`cp .env.example .env`). Nunca colocar credenciais reais no Git.

| Variável | Omissão | Notas |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test` ou `production` |
| `APP_HOST` / `APP_PORT` | `127.0.0.1` / `5000` | Endereço do Uvicorn |
| `APP_WORKERS` | `1` | 1–8; poucos workers para limitar RAM |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Proxies confiáveis (Nginx) |
| `API_DOCS_ENABLED` | `true` fora de produção | Expõe `/api/docs` e `/api/openapi.json` |
| `MONGODB_HOST` / `MONGODB_PORT` | `127.0.0.1` / `27017` | |
| `MONGODB_DATABASE` | `VCCTeamForgeDB` | |
| `MONGODB_USERNAME` / `MONGODB_PASSWORD` | — | Obrigatórios em produção, sempre em conjunto |
| `MONGODB_AUTH_SOURCE` | `MONGODB_DATABASE` | |
| `MONGODB_SERVER_SELECTION_TIMEOUT_MS` | `5000` | |
| `MONGODB_MAX_POOL_SIZE` | `20` | Por worker |
| `DATABASE_DIR` | `<repo>/database` | Migrations, índices e seeds |
| `ATTACHMENTS_PATH` | `var/attachments` | Absoluto em produção |
| `ATTACHMENTS_MAX_BYTES` | `20971520` (20 MiB) | Por anexo; máximo 25 MiB (limite do Nginx) |
| `ATTACHMENTS_MAX_PER_ISSUE` | `50` | Anexos ativos por issue |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `text` | `json` recomendado em produção |
| `LOG_FILE` | — | Se definido, ficheiro com rotação (`LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`) |
| `HEALTH_MIN_FREE_DISK_MB` | `1024` | Limiar de disco para readiness `degraded` |
| `COOKIE_SECURE` | `true` só em produção | `false` apenas se produção servir HTTP sem TLS |
| `COOKIE_SAMESITE` | `lax` | `lax` ou `strict` |
| `SESSION_IDLE_MINUTES` | `120` | Expiração por inatividade |
| `SESSION_ABSOLUTE_HOURS` | `12` | Duração máxima da sessão |
| `LOGIN_MAX_FAILURES_PER_EMAIL` | `5` | Falhas por email na janela |
| `LOGIN_MAX_FAILURES_PER_IP` | `20` | Falhas por IP na janela |
| `LOGIN_WINDOW_MINUTES` | `15` | Janela do rate limiting |

Em `APP_ENV=production` a aplicação recusa arrancar se faltarem credenciais MongoDB ou se
`ATTACHMENTS_PATH` for relativo.

## Logging, erros e health checks

- **Logging** (`app/core/logging.py`): cada linha inclui o request id. Em produção, usar
  `LOG_FORMAT=json` e o journald (`journalctl -u VCCTeamForge-api`). Com `LOG_FILE`, o ficheiro
  roda por tamanho. O access log do Uvicorn está desativado; é o middleware que regista
  método, caminho, estado e duração.
- **Request id** (`app/core/middleware.py`): é aceite o `X-Request-ID` enviado pelo Nginx, se
  for válido; caso contrário é gerado um novo. É devolvido no cabeçalho e no corpo dos erros.
- **Erros** (`app/core/errors.py`): todas as respostas de erro usam RFC 7807
  (`application/problem+json`) com `type`, `title`, `status`, `detail`, `instance` e
  `requestId`. Os serviços lançam `AppError` e subclasses (`NotFoundError`, `ConflictError`,
  `ForbiddenError`, ...). Erros de validação (422) incluem `errors` sem repetir os valores
  recebidos. Exceções não tratadas devolvem 500 sem detalhes internos, e falhas de ligação
  ao MongoDB devolvem 503.
- **Health checks**:

| Endpoint | Uso | Resposta |
|---|---|---|
| `GET /api/health`, `GET /api/health/live` | Processo vivo | Sempre 200 |
| `GET /api/health/ready` | Dependências | 200 `ok`/`degraded`; 503 se o MongoDB falhar |

## Autenticação e autorização

- **Passwords:** Argon2id (19 MiB, t=2, p=1). Os hashes são atualizados no login se os parâmetros
  mudarem. A password tem entre 12 e 128 caracteres.
- **Sessões no servidor** (`sessions`): o cookie `vcctf_session` (`HttpOnly`, `SameSite`,
  `Secure` em produção) contém um token aleatório; a BD guarda apenas o SHA-256 desse token. A
  sessão expira por inatividade e tem uma duração máxima; um índice TTL remove-a depois.
  Desativar um utilizador invalida as suas sessões no pedido seguinte.
- **CSRF:** os métodos não seguros exigem o cabeçalho `X-CSRF-Token` igual ao cookie
  `vcctf_csrf`. Com sessão, o token tem também de coincidir com o que está associado a ela no
  servidor. Antes do login, o frontend obtém o token em `GET /api/auth/csrf`.
- **Rate limiting:** as falhas de login por email e por IP ficam em `login_attempts` (TTL 24h).
  Acima do limite a API devolve 429 com `Retry-After`. Credenciais erradas e utilizador
  inexistente dão a mesma resposta, e o tempo de resposta também é igual.
- **Auditoria** (`audit_logs`): `auth.login`, `auth.login_failed`, `auth.logout`, `user.created`
  e `project.*` (created, updated, archived, restored, member_added, member_removed), com IP e
  request id.
- **RBAC:** os perfis `admin`, `tech_lead`, `developer` e `qa` são mapeados para permissões em
  `app/domain/permissions.py`. Nas rotas usa-se `Depends(require_permissions(Permission.X))`.
  Para dados de um projeto, os serviços usam `app/services/authorization.py`: só administradores
  ou membros/lead têm acesso, e os restantes recebem 404.
- **Endpoints:** `GET /api/auth/csrf`, `POST /api/auth/login`, `POST /api/auth/logout` e
  `GET /api/users/me`.

## API de domínio

Convenções comuns:

- Listas paginadas devolvem `{items, total, page, pageSize}` (`page` ≥ 1, `pageSize` ≤ 100) e
  aceitam `sort=campo` ou `sort=-campo` (desempate estável por `_id`; campo inválido → 422).
- Documentos editáveis têm `version`: as mutações enviam a versão lida e recebem 409 com
  `currentVersion` se outra pessoa alterou entretanto.
- Erros de regra de negócio devolvem 422 com `field` quando se referem a um campo; IDs
  malformados em rotas dão 404.
- Mutações relevantes ficam em `audit_logs` (ação, entidade, utilizador, detalhes).

### Projetos

| Método e rota | Permissão | Notas |
|---------------|-----------|-------|
| `GET /api/projects` | `projects:read` | Só projetos acessíveis; filtros `status` (repetível), `includeArchived`, `q`; `sort` `name`/`key`/`updatedAt` |
| `POST /api/projects` | `projects:manage` | `key` única (`^[A-Z][A-Z0-9]{1,9}$`); um Tech Lead fica responsável e membro |
| `GET /api/projects/{id}` | membro/lead/admin | Inclui `canManage` e `memberCount` |
| `PATCH /api/projects/{id}` | admin ou lead do projeto | `key` e membros não são editáveis aqui; arquivado → 422 |
| `POST /api/projects/{id}/archive`, `/restore` | admin ou lead | Corpo `{version}` |
| `GET /api/projects/{id}/members` | membro/lead/admin | Responsável primeiro |
| `POST /api/projects/{id}/members` | admin ou lead | `{userId, version}`; utilizador ativo |
| `DELETE /api/projects/{id}/members/{userId}?version=` | admin ou lead | O responsável não pode ser removido |
| `GET /api/users?q=&limit=` | `projects:manage` ou `users:manage` | Utilizadores ativos (máx. 20) para seletores |

O responsável (`leadUserId`) tem de ser um utilizador ativo com perfil Tech Lead ou
Administrador. Projetos arquivados ficam só de leitura e saem das listas por omissão.

### Issues

| Método e rota | Permissão | Notas |
|---------------|-----------|-------|
| `GET /api/issues` | `issues:read` | Pesquisa paginada (ver filtros abaixo); sem `projectId` abrange todos os projetos acessíveis |
| `POST /api/issues` | `issues:write` | QA só cria `bug`; projeto arquivado → 422 |
| `GET /api/issues/{id}`, `GET /api/issues/by-key/{key}` | `issues:read` + acesso | Inclui `canEdit`, `allowedTransitions`, pai e dependências |
| `PATCH /api/issues/{id}` | admin/Tech Lead, ou responsável/autor | Corpo com `version`; `status`, `blocked` + `blockReason` e restantes campos |

Filtros de `GET /api/issues` (listas aceitam o parâmetro repetido; valores inválidos → 422):

| Parâmetro | Valores |
|-----------|---------|
| `projectId` | Projeto acessível (inacessível ou mal formado → 404) |
| `status`, `priority`, `type` | Valores dos enums |
| `assigneeId` | ID, `me` ou `none` (sem responsável) |
| `sprintId` | ID ou `none` (backlog) |
| `label` | Normalizada; corresponde a qualquer uma |
| `blocked` | `true`/`false` |
| `parentIssueId` | Filhos/subtarefas de uma issue |
| `q` | ≤ 100 caracteres: chave exata (`DVC-12`) ou parte do título (sem distinção de maiúsculas; carateres especiais escapados) |
| `sort` | `number`, `title`, `status`, `priority`, `updatedAt`, `createdAt`, `dueDate` (prefixo `-` = descendente; omissão `-number`) |

As listas devolvem apenas os campos de resumo (sem descrição, critérios nem dependências).
`GET /api/projects/{id}/labels` (`issues:read`) devolve as labels distintas do projeto.

- **Numeração:** a chave `PROJ-N` vem de um contador atómico por projeto (`counters`,
  `issues:<projectId>`); números não são reutilizados.
- **Transições:** `todo → in_progress`; `in_progress → todo/code_review/testing/done`;
  `code_review → in_progress/testing/done`; `testing → in_progress/code_review/done`;
  `done → in_progress` (reabrir). Outras → 422 `field=status`. `completedAt` é preenchido
  ao entrar em `done` e limpo ao reabrir.
- **Hierarquia:** epic sem pai; subtask exige pai que não seja epic nem subtask; os restantes
  tipos só podem ter um epic como pai. Pai e dependências têm de ser do mesmo projeto.
- **Bloqueio:** `blocked=true` exige `blockReason` (≤ 500); `blockedAt` é gerido pelo servidor.
- Labels normalizadas (minúsculas, sem duplicados, ≤ 20 × 40 caracteres); story points entre
  0 e 100 em múltiplos de 0,5; responsável tem de ser membro do projeto.

### Comentários, histórico e auditoria

| Método e rota | Permissão | Notas |
|---------------|-----------|-------|
| `GET /api/issues/{id}/comments` | `issues:read` + acesso | Paginado, mais antigos primeiro; removidos aparecem sem `body` (`deleted=true`) |
| `POST /api/issues/{id}/comments` | `issues:comment` + acesso | `body` Markdown, 1–10 000 caracteres; projeto arquivado → 422 |
| `PATCH /api/issues/{id}/comments/{commentId}` | `issues:comment`, só o autor | Define `editedAt` |
| `DELETE /api/issues/{id}/comments/{commentId}` | autor, Tech Lead do projeto ou admin | Remoção lógica (`deletedAt`, `deletedBy`, corpo apagado) → 204 |
| `GET /api/issues/{id}/history` | `issues:read` + acesso | Eventos paginados, mais recentes primeiro |
| `GET /api/audit-logs` | `audit:read` (admin) | Filtros `entityType`, `entityId`, `actorId`, `action`, `from`, `to` (datas, `to` inclusivo) |

- Cada comentário devolve `canEdit`/`canDelete` calculados no servidor.
- `issue_history` regista `created`, `updated` (lista `changes` com `field`/`from`/`to`),
  `comment_added/edited/deleted` e `attachment_added/removed`. Descrição e critérios só
  registam que mudaram (sem conteúdo).
- As mesmas ações são gravadas em `audit_logs` (`issue.created`, `issue.updated`,
  `comment.created/updated/deleted`). Falhas ao escrever histórico ou auditoria são registadas
  em log (com `requestId`) e não anulam a operação principal.

### Anexos

| Método e rota | Permissão | Notas |
|---------------|-----------|-------|
| `GET /api/issues/{id}/attachments` | `issues:read` + acesso | Metadados (sem caminho interno), mais antigos primeiro |
| `POST /api/issues/{id}/attachments` | `issues:write` + acesso | `multipart/form-data`, campo `file` → 201; projeto arquivado → 422 |
| `GET /api/attachments/{id}/content` | `issues:read` + acesso | `?inline=1` só tem efeito em imagens |
| `DELETE /api/attachments/{id}` | quem carregou, Tech Lead do projeto ou admin | Remoção lógica + ficheiro apagado → 204 |

- **Tipos aceites:** `png`, `jpg`, `jpeg`, `gif`, `webp`, `pdf`, `txt`, `log`, `md`, `csv`,
  `json`, `zip`, `docx`, `xlsx`, `pptx`. O `Content-Type` guardado deriva da extensão (o enviado
  pelo browser é ignorado); imagens, PDF e formatos ZIP são confirmados pelos *magic bytes* e
  ficheiros de texto com bytes nulos são recusados (422 `field=file`).
- **Limites:** acima de `ATTACHMENTS_MAX_BYTES` → 413 (verificado durante a leitura, sem
  confiar no `Content-Length`); mais de `ATTACHMENTS_MAX_PER_ISSUE` → 422.
- **Disco:** `<ATTACHMENTS_PATH>/<projectId>/<aaaa>/<mm>/<token hex 32>` (diretórios `0750`,
  ficheiros `0640`), escrita num temporário com `os.replace` atómico; o nome original
  (sem caminhos nem caracteres de controlo, ≤ 200) só existe nos metadados. Se a gravação dos
  metadados falhar, o ficheiro é apagado.
- **Download:** `Content-Disposition` com `filename*` (RFC 5987), `X-Content-Type-Options:
  nosniff`, `Content-Security-Policy: sandbox` e `Cache-Control: private, no-store`.
- Histórico `attachment_added`/`attachment_removed` e auditoria `attachment.created`/`attachment.deleted`.
- `python -m app.cli attachments-check` reporta ficheiros órfãos e anexos ativos sem ficheiro
  (código de saída 1 se houver inconsistências).

### Backlog e quadro

| Método e rota | Permissão | Notas |
|---------------|-----------|-------|
| `POST /api/issues/{id}/rank` | `issues:write` + regra de edição | `{beforeId?, afterId?, version}` → `IssueSummary`; sem histórico |
| `GET /api/projects/{id}/board` | `issues:read` + acesso | Filtros da pesquisa (`assigneeId`, `type`, `label`, `q`…); `status` é ignorado |

- **Ordem manual:** campo `rank` (float). Novas issues ficam no fim (`max(rank) + 1024`);
  `sort=rank` na pesquisa. `beforeId` coloca a issue acima dessa issue e `afterId` abaixo
  (ambos: tem de valer `afterId` antes de `beforeId`, senão 422). Vizinhos inexistentes, de
  outro projeto ou a própria issue → 422 com `field`. O novo rank é o ponto médio; se o
  intervalo for < 1e-6, os ranks do projeto são renormalizados (passo 1024) e o cálculo repete.
- **Quadro:** uma coluna por estado (`todo…done`) ordenada por `rank`, até 200 issues por
  coluna (`total` e `truncated`); `done` só mostra as concluídas nos últimos 14 dias, exceto
  com `sprintId` de um sprint (mostra todas as concluídas do sprint e `doneWindowDays` é `null`). Mover no
  quadro usa `PATCH /api/issues/{id}` (`status` + `version`, transições validadas).
- A migration `0003_issue_rank` atribui `rank` às issues existentes sem rank (por `number`).

### Sprints

| Método e rota | Permissão | Notas |
|---------------|-----------|-------|
| `GET /api/sprints?projectId=` | `projects:read` + acesso | Filtros `status` (repetível) e `q`; `sort` `startDate`/`name`/`createdAt` (omissão `-startDate`); paginado |
| `POST /api/sprints` | `sprints:manage` + acesso | `{projectId, name, goal?, startDate, endDate?, capacityStoryPoints?}` → 201; auditoria `sprint.created` |
| `GET /api/sprints/{id}` | `projects:read` + acesso | Inclui `durationDays`, `capacityStoryPoints`, `scope` e `canEdit` |
| `PATCH /api/sprints/{id}` | `sprints:manage` + acesso | `{name?, goal?, startDate?, endDate?, capacityStoryPoints?, version}`; auditoria `sprint.updated` |
| `POST /api/sprints/{id}/issues` | `sprints:manage` + acesso | `{issueIds}` (1–50) → sprint atualizado; auditoria `sprint.issues_added` |
| `DELETE /api/sprints/{id}/issues/{issueId}` | `sprints:manage` + acesso | Devolve a issue ao backlog → sprint atualizado; auditoria `sprint.issue_removed` |
| `POST /api/sprints/{id}/start` | `sprints:manage` + acesso | `{version}` → sprint `active`; auditoria `sprint.started` |
| `GET /api/sprints/{id}/commitment` | `projects:read` + acesso | Compromisso congelado no início + issues retiradas/adicionadas depois; 404 se não iniciado |
| `POST /api/sprints/{id}/close` | `sprints:manage` + acesso | `{version, carryOverSprintId?, retrospective?: {wentWell, toImprove, actions}}` → sprint `closed`; auditoria `sprint.closed` |

- Estados `planned`, `active`, `closed` (iniciar no DEV-017, fechar no DEV-018). Sprints novos
  ficam `planned`.
- Nome único por projeto sem distinção de maiúsculas (`nameKey`) → 409 com `field=name`.
- `endDate` por omissão = início + `settings.sprintDurationDays` − 1; fim ≥ início e duração
  máxima de 60 dias (422 com `field=endDate`).
- Sprints `planned`/`active` do mesmo projeto não se sobrepõem (422 com `field=startDate`).
- Sprint ativo: a data de início já não muda; sprint fechado e projeto arquivado → só leitura (422).
- `projectId` inválido ou sem acesso no corpo → 422 (`field=projectId`); `GET /api/sprints`
  sem `projectId` → 422. A migration `0004_sprint_collections` cria a collection `sprints`.
- **Planeamento (DEV-016):** `capacityStoryPoints` opcional (0–1000, múltiplos de 0,5). `scope`
  agrega as issues do sprint: `issueCount`, `storyPoints`, `unestimatedCount`,
  `completedIssueCount`, `completedStoryPoints`. A estimativa faz-se em `PATCH /api/issues/{id}`
  (`storyPoints`).
- Só entram em sprints `planned`/`active` issues do mesmo projeto, por concluir e que não sejam
  epics (422 com `field=issueIds` e `issueId`); máximo de 300 issues por sprint. Uma issue de
  outro sprint aberto muda de sprint; de um sprint fechado → 422. Adicionar uma issue que já
  está no sprint não faz nada.
- Cada mudança é condicional ao `sprintId` atual da issue (409 se mudou entretanto), incrementa
  a `version` da issue e regista no histórico a alteração `sprintId`.
- **Início (DEV-017):** só sprints `planned` (422 `field=status`), com pelo menos uma issue
  (422 `field=issueIds`) e `endDate` ≥ hoje (422 `field=endDate`). Um sprint ativo por projeto:
  pré-verificação (422 `field=status` com `sprintId`) e índice único parcial
  `sprints_projectId_active_unique` para pedidos concorrentes. Grava `startedAt`, `startedBy`,
  `committedIssueCount` e `committedStoryPoints` (sem estimativa conta 0).
- O compromisso fica em `sprint_snapshots` (`kind: "commitment"`, `day`, `issues[]` com estado e
  story points no início, `totals`), único por `(sprintId, kind, day)`. Sem transações: primeiro
  a transição condicional do sprint, depois o snapshot; se o snapshot falhar o sprint volta a
  `planned`. A migration `0006_sprint_snapshots` cria a collection.
- **Fecho (DEV-018):** só sprints `active` (422 `field=status`). As issues por concluir vão para
  o backlog (`carryOverSprintId` nulo) ou para um sprint `planned` do mesmo projeto (senão 422
  `field=carryOverSprintId`); as `done` ficam no sprint. Grava `closedAt`, `closedBy`,
  `retrospective` (cada texto ≤ 5000, sem espaços nas pontas) e `result` (concluídas,
  transportadas, destino e concluídas do compromisso), calculado antes do transporte.
- Ordem: transição condicional `active` → `closed`, snapshot `kind: "closing"` (se falhar o
  sprint volta a `active` e o pedido falha), transporte issue a issue com histórico `sprintId`
  (o limite de 300 issues não se aplica; falhas individuais ficam no log) e auditoria. Depois
  do fecho o compromisso compara com o snapshot de fecho.

### Relatório de sprint

| Método e rota | Permissão | Notas |
|---------------|-----------|-------|
| `GET /api/reports/sprints/{id}` | `reports:read` + acesso | KPIs, burndown, distribuição por estado, bloqueios e velocidade; sprint `planned` → 422 `field=status` |

- **Snapshots diários (DEV-019):** `sprint_snapshots` `kind: "daily"`, um por dia (substituído
  ao longo do dia). Gravados no início, ao associar/remover issues de um sprint ativo (também
  no sprint de origem), quando uma issue de um sprint ativo muda `status`/`storyPoints` e no
  fecho (antes do transporte). São best-effort: uma falha fica no log e não anula o pedido.
- `kpis`: compromisso, âmbito atual, concluídas, SP restantes, `progressPercent` (SP concluídos
  / âmbito; `null` sem SP), dias totais/decorridos/restantes, bloqueadas e adicionadas/
  retiradas face ao compromisso. Sprint fechado → dados do snapshot de fecho.
- `burndown`: um ponto por dia entre o início (ou o dia em que foi iniciado, se antes) e o fim
  (ou hoje/dia do fecho, se depois). `ideal` desce linearmente do compromisso a 0; `remaining`
  e `scope` vêm do último snapshot até esse dia (hoje, num sprint ativo, das issues atuais);
  dias futuros ou sem snapshot → `null`.
- `velocity`: até 5 sprints fechados do projeto com início até ao deste, com compromisso,
  concluído, concluído do compromisso e `predictabilityPercent`; `averageVelocity` = média dos
  concluídos.

### Casos e planos de teste

| Método e rota | Permissão | Notas |
|---------------|-----------|-------|
| `GET /api/test-cases?projectId=` | `tests:read` + acesso | Filtros `status`, `priority`, `label` (repetíveis), `issueId` e `q` (título ou `TC-n`); `sort` `number`/`title`/`priority`/`updatedAt`; paginado |
| `POST /api/test-cases` | `tests:manage` + acesso | `{projectId, title, description?, preconditions?, steps[], expectedResult?, priority?, status?, labels?, issueIds?}` → 201; auditoria `test_case.created` |
| `GET /api/test-cases/{id}` | `tests:read` + acesso | Inclui `key` (`TC-n`), issues ligadas e `canEdit` |
| `PATCH /api/test-cases/{id}` | `tests:manage` + acesso | Campos opcionais + `version`; auditoria `test_case.updated` |
| `GET /api/test-plans?projectId=` | `tests:read` + acesso | Filtros `status` (repetível) e `q`; `sort` `name`/`createdAt`/`updatedAt` (omissão `-createdAt`); paginado |
| `POST /api/test-plans` | `tests:manage` + acesso | `{projectId, name, description?, status?, testCaseIds[]}` → 201; auditoria `test_plan.created` |
| `GET /api/test-plans/{id}` | `tests:read` + acesso | Inclui os casos (ordem do plano) e `canEdit` |
| `PATCH /api/test-plans/{id}` | `tests:manage` + acesso | Campos opcionais + `version`; auditoria `test_plan.updated` |

- Casos: estados `draft`, `ready`, `deprecated`; número sequencial por projeto (counter
  `test_cases:<projectId>`), até 50 passos `{action, expectedResult?}` e 20 issues ligadas do
  mesmo projeto (422 com `field=issueIds`).
- Planos: estados `draft`, `active`, `closed`; nome único por projeto sem distinção de
  maiúsculas → 409 com `field=name`; até 500 casos do mesmo projeto, sem repetições
  (`field=testCaseIds`). Casos `deprecated` não podem ser adicionados, mas os já incluídos mantêm-se.
- Plano fechado só aceita mudar o `status` (422 com `field=status`); projeto arquivado → só leitura.
- Nas alterações a textos longos a auditoria regista apenas `{changed: true}`. Os planos são
  associados a releases em `testPlanIds` da release (ver "Releases"). A migration
  `0005_test_collections` cria as collections `test_cases` e `test_plans`.

### Execuções de testes e evidências

| Método e rota | Permissão | Notas |
|---------------|-----------|-------|
| `GET /api/test-runs?projectId=` | `tests:read` + acesso | Filtros `testCaseId`, `testPlanId`, `result` (repetível) e `executedBy` (`me` ou id); `sort` `executedAt` (omissão `-executedAt`); paginado |
| `POST /api/test-runs` | `tests:execute` + acesso | `{testCaseId, testPlanId?, result, actualResult?, notes?, environment?, executedAt?}` → 201; auditoria `test_run.created` |
| `GET /api/test-runs/{id}` | `tests:read` + acesso | Inclui bugs ligados, `canEdit`, `canAddEvidence` e `canCreateBug` |
| `PATCH /api/test-runs/{id}` | executor (`tests:execute`) ou `tests:manage` | `result`, `actualResult`, `notes`, `environment` + `version`; auditoria `test_run.updated` |
| `POST /api/test-runs/{id}/bugs` | `issues:write` + acesso | Só com `result=fail`; `{title?, priority?, assigneeId?}` → bug pré-preenchido e ligado à execução (201); auditoria `test_run.bug_created` |
| `GET /api/test-runs/{id}/evidences` | `tests:read` + acesso | Metadados das evidências |
| `POST /api/test-runs/{id}/evidences` | executor ou `tests:manage` | `multipart/form-data`, campo `file` → 201; auditoria `test_run_evidence.created` |
| `GET /api/test-runs/{id}/evidences/{evidenceId}/content` | `tests:read` + acesso | Mesmos cabeçalhos de segurança dos anexos; `?inline=1` só em imagens |
| `DELETE /api/test-runs/{id}/evidences/{evidenceId}` | quem carregou, `tests:manage` ou Tech Lead do projeto | 204; auditoria `test_run_evidence.deleted` |
| `GET /api/test-plans/{id}/progress` | `tests:read` + acesso | Último resultado por caso, contagens, `passRate` e regressões |

- Resultados: `pass`, `fail`, `blocked`, `not_run`, `skipped`. A execução guarda um snapshot
  do número e título do caso; casos `deprecated`, planos fechados, casos fora do plano e
  `executedAt` no futuro (tolerância de 5 minutos) → 422 com `field`.
- `passRate` = `pass / (pass + fail + blocked)` entre 0 e 1 (`null` sem execuções relevantes);
  regressão = execução anterior `pass` e última `fail` no mesmo plano. Casos sem execuções no
  plano contam como `not_run`.
- Evidências usam as mesmas validações, limites e armazenamento dos anexos (collection
  `attachments` com `testRunId`), e por isso entram no `attachments-check`.
- Até 20 bugs por execução. A migration `0007_test_runs` cria a collection `test_runs`.

### Releases

| Método e rota | Permissão | Notas |
|---------------|-----------|-------|
| `GET /api/releases?projectId=` | `releases:read` + acesso | Filtros `status` (repetível) e `q` (versão); `sort` `createdAt`, `name`, `plannedDate` (omissão `-createdAt`); paginado |
| `POST /api/releases` | `releases:manage` + acesso | `{name, description?, notes?, plannedDate?, issueIds?, knownBugIds?, testPlanIds?, checklist?, criteria?}` → 201; auditoria `release.created` |
| `GET /api/releases/{id}` | `releases:read` + acesso | Inclui issues, bugs conhecidos, planos, checklist, critérios, `quality`, histórico, `canEdit` e `availableTransitions` |
| `PATCH /api/releases/{id}` | `releases:manage` | Só em `draft`/`ready_for_qa`; com `version`; auditoria `release.updated` |
| `POST /api/releases/{id}/transitions` | conforme a transição | `{to, comment?, version}`; auditoria `release.transitioned` |

- `name` é o número da versão (ex.: `1.4.0`): 1–40 caracteres `[0-9A-Za-z._+-]`, único por
  projeto sem distinção de maiúsculas → 409 com `field=name`. `notes` (markdown) até 20000.
- Ligações do mesmo projeto: até 500 `issueIds`, 100 `knownBugIds` (só issues `bug`) e 50
  `testPlanIds` → 422 com o `field` respetivo.
- Checklist com até 30 itens `{id?, label, required, done}`; quem marcou e quando é definido pelo
  servidor (`doneBy`, `doneAt`). Sem `checklist` na criação, copia os itens (por marcar) da release
  mais recente do projeto ou usa a checklist por omissão.
- Workflow: `draft → ready_for_qa` (`releases:manage`), `ready_for_qa → approved`
  (`releases:approve`), `approved → released` (`releases:manage`, define `releasedAt`),
  `ready_for_qa → draft` e `approved → draft` (`releases:manage` ou `releases:approve`, comentário
  obrigatório → 422 `field=comment`). Transição inválida → 422 `field=to`; `released` é final.
- A aprovação exige os itens obrigatórios da checklist marcados (422 `field=checklist`) e os
  critérios ativos cumpridos (422 `field=criteria`): `issuesDone` (issues incluídas `done`),
  `testsPassed` (há planos e o último resultado de todos os casos é `pass`/`skipped`) e
  `noOpenCriticalBugs` (nenhum bug `critical` por concluir entre os conhecidos e os incluídos).
- `quality` agrega issues concluídas, bugs em aberto/críticos e o progresso dos planos (contagens,
  `passRate`, regressões). O histórico (`created`, `updated`, `submitted`, `approved`, `rejected`,
  `reopened`, `released`) guarda até 500 entradas. Projeto arquivado → só leitura (422).
- A migration `0008_releases` cria a collection `releases`.

Primeiro administrador (a password é pedida no terminal):

```bash
.venv/bin/python -m app.cli create-user --email admin@exemplo.pt --name "Administrador"
```

## Migrations, índices e seeds

Executam-se pela CLI, nunca no arranque da API nem por pedido HTTP. Usam a mesma configuração
que a API. O utilizador MongoDB precisa de `readWrite` na base de dados.

```bash
.venv/bin/python -m app.cli status             # migrations e índices em falta
.venv/bin/python -m app.cli migrate --dry-run  # o que seria aplicado
.venv/bin/python -m app.cli migrate            # migrations pendentes + índices
.venv/bin/python -m app.cli seed               # dados iniciais em falta
.venv/bin/python -m app.cli create-user --email ... --name ... [--role admin|tech_lead|developer|qa]
```

- **Migrations** (`database/migrations/NNNN_nome.py`, com `up(db)` e `DESCRIPTION` opcional):
  são aplicadas por ordem e registadas em `schema_migrations` (com checksum). Um lock em
  `maintenance_locks`, com expiração de 15 minutos, impede execuções concorrentes. Sem
  transações, cada `up` tem de ser idempotente. Uma migration aplicada não deve ser alterada;
  o `status` assinala ficheiros alterados.
- **Índices** (`database/indexes/indexes.json`): todos os índices são validados antes de se
  criar algum, e os existentes não são tocados. Se um nome existir com outra definição, o
  comando falha; é preciso uma migration que remova o índice antes de o redefinir.
- **Seeds** (`database/seed/<collection>.json`): cada documento tem `_id` e só é inserido se
  ainda não existir. Alterações feitas na Administração nunca são sobrepostas.

## MongoDB 4.4

- Driver: **PyMongo 4.19.x**, que suporta MongoDB ≥ 4.4. As versões 4.18+ deixaram de suportar a
  4.2, e versões futuras podem deixar de suportar a 4.4. Só atualizar depois de os testes de
  compatibilidade passarem contra o servidor real.
- `app/repositories/mongo.py` cria o cliente (`tz_aware=True`, UTC) e verifica a versão do
  servidor no arranque. Uma versão abaixo de 4.4 é rejeitada. Se o servidor estiver indisponível,
  a API arranca na mesma.
- Sem transações multi-documento e sem operadores posteriores à 4.4 (`$setWindowFields`,
  `$dateTrunc`, `$getField`, time-series).
- Números sequenciais com `CounterRepository.next_value()` (`$inc` atómico em `counters`).

### Testes de integração

Os testes que precisam de MongoDB usam uma base de dados descartável
(`VCCTeamForgeDB_test_<aleatório>`), apagada no fim. Se o servidor não estiver acessível ou
não autorizar o acesso, esses testes são ignorados (*skip*).

| Variável | Omissão |
|---|---|
| `VCCTF_TEST_MONGODB_HOST` / `_PORT` | `127.0.0.1` / `27017` |
| `VCCTF_TEST_MONGODB_USERNAME` / `_PASSWORD` / `_AUTH_SOURCE` | — |
| `VCCTF_TEST_MONGODB_DATABASE` | aleatório |
| `VCCTF_REQUIRE_MONGO=1` | falhar em vez de ignorar |

Exemplo com uma instância 4.4 temporária, sem autenticação e isolada da de produção:

```bash
mkdir -p /tmp/mongo-test
LD_LIBRARY_PATH=/opt/mongodb44/lib /opt/mongodb44/bin/mongod \
  --dbpath /tmp/mongo-test --port 27027 --bind_ip 127.0.0.1 --wiredTigerCacheSizeGB 0.25 &
VCCTF_REQUIRE_MONGO=1 VCCTF_TEST_MONGODB_PORT=27027 .venv/bin/pytest
```

## Dependências

- Limites de versão em `pyproject.toml`.
- Versões exatas de runtime em `requirements.txt`, geradas com `scripts/lock-requirements.sh`.
- Em produção instalar apenas `requirements.txt` e o pacote (`pip install --no-deps .`).
