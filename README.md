# VCCTeamForge — Especificação funcional e plano de desenvolvimento

**Versão:** 1.0  
**Data:** 20-10-2026  
**Idioma:** Português (Portugal)  
**Estado:** Proposta técnica para implementação

## 1. Objetivo

Desenvolver uma aplicação web interna para gestão de projetos de software, dirigida a uma equipa Scrum de **6 a 10 developers**, com acompanhamento de issues, bugs, sprints, testes, releases, dashboards e relatórios. A aplicação será instalada num computador Linux antigo e utilizada apenas na rede local.

### Restrições confirmadas

- **MongoDB 4.4 existente e obrigatório**: o hardware não permite instalar uma versão mais recente; não planear migração como pré-requisito.
- Sem exposição da aplicação ou do MongoDB à Internet.
- Sem integração GitHub.
- Preferência por baixo consumo de RAM e CPU e por poucos serviços em execução.
- Utilização através de browser, sem instalação nos postos dos developers.
- Scrum como metodologia de trabalho.

> Nota de segurança: uma rede local reduz a superfície de exposição, mas não elimina riscos. MongoDB 4.4 está fora do suporte normal; manter isolamento, autenticação, backups e restrições de acesso. Não utilizar funcionalidades ou drivers incompatíveis com MongoDB 4.4.

## 2. Stack tecnológica

| Camada | Proposta | Observações |
|---|---|---|
| Frontend | React, TypeScript, Vite | Build estático servido pelo Nginx |
| Interface | Tailwind CSS, shadcn/ui | Componentes reutilizáveis |
| Estado remoto | TanStack Query | Cache e invalidação |
| Formulários | React Hook Form, Zod | Validação no cliente; repetir no servidor |
| Kanban | dnd-kit | Drag-and-drop acessível |
| Gráficos | Recharts | Dashboards |
| Backend | Python, FastAPI, Pydantic, Uvicorn | Monólito modular; API síncrona; versão de Python compatível com o Linux/CPU |
| Persistência | MongoDB 4.4 | PyMongo (síncrono); versão compatível com MongoDB 4.4 a validar antes de fixar versões |
| Web server | Nginx | Reverse proxy e estáticos |
| Serviços | systemd | Arranque automático e recuperação |
| Anexos | Sistema de ficheiros | Metadados na BD |
| Exportação | CSV, XLSX, PDF | Bibliotecas a selecionar e validar |

**Sem Redis, Kubernetes, Elasticsearch, microserviços ou processo Node.js em produção.** Docker não é necessário.

### Validação prévia do ambiente

```bash
uname -m
cat /etc/os-release
free -h
lscpu
df -h
mongod --version
systemctl status mongodb44.service
```

Confirmar arquitetura do processador, glibc, RAM, disco, versão de Python suportada e compatibilidade do PyMongo com MongoDB 4.4. Não assumir que a versão mais recente do driver suporta o servidor legado.

## 3. Perfis e permissões

- **Administrador:** utilizadores, perfis, parâmetros e manutenção.
- **Tech Lead:** projetos, backlog, sprints, relatórios e aprovação de releases.
- **Developer:** issues atribuídas, comentários, estimativas, atualizações e consulta dos projetos autorizados.
- **QA:** casos de teste, execuções, evidências e criação de bugs.

As permissões são verificadas no backend e também por projeto. Um utilizador pode pertencer a vários projetos.

## 4. Navegação e páginas

### 4.1 Dashboard

- KPIs: issues abertas, em progresso, bloqueadas e concluídas; bugs críticos; taxa de testes aprovados.
- Sprint atual, objetivo, progresso e prazo.
- Gráficos de burndown, distribuição por estado e tendências.
- Alertas: bloqueios prolongados, issues sem atualização, bugs críticos sem responsável.
- Visão diferente por perfil (Tech Lead, Developer, QA).

### 4.2 Projetos

- Listar, criar, editar e arquivar projetos.
- Campos: código único, nome, descrição, estado, prioridade, responsável, datas e membros.
- Separadores: resumo, backlog, sprints, testes, releases, documentação e métricas.
- Indicadores calculados a partir do trabalho concluído.

### 4.3 Backlog e issues

- Tipos: Epic, Story, Task, Bug, Spike, Improvement e Subtask.
- Identificador sequencial por projeto: `DVC-125`.
- Campos: título, descrição Markdown, tipo, prioridade, estado, responsável, criador, story points, sprint, etiquetas, critérios de aceitação, datas e dependências.
- Comentários, anexos, histórico e auditoria.
- Filtros por projeto, sprint, estado, prioridade, responsável, tipo e etiqueta.
- Vistas: tabela, backlog e quadro.
- Estados iniciais: `todo`, `in_progress`, `code_review`, `testing`, `done`.
- Impedimento representado por `blocked` e `blockReason`, independente do estado.
- Fluxo sem saltos: cada issue passa por todos os estados por ordem; recuos permitidos conforme §14 (questão 7).
- Validar transições e alterações concorrentes no backend.

### 4.4 Sprints Scrum

- Criar sprint com nome, objetivo, início e fim.
- Associar issues do backlog e definir estimativas.
- Iniciar sprint e guardar compromisso inicial imutável.
- Quadro Scrum, progresso, burndown e capacidade.
- Fechar sprint, registar retrospectiva e transportar trabalho incompleto para o backlog ou sprint seguinte.
- Preservar eventos para reconstrução histórica de métricas.

### 4.5 Testes e QA

- Casos de teste com pré-condições, passos e resultado esperado.
- Planos de teste e associação a projeto, issue e release.
- Execuções com estados `pass`, `fail`, `blocked`, `not_run`, `skipped`.
- Evidências em anexo, executor, data e observações.
- Criar bug a partir de uma execução falhada mantendo a ligação.
- Relatórios de execução e regressão.

### 4.6 Releases

- Versão, descrição, datas, issues incluídas, bugs conhecidos e notas.
- Workflow: `draft` → `ready_for_qa` → `approved` → `released`.
- Checklist e critérios configuráveis para aprovação.
- Histórico de aprovações e alterações.

### 4.7 Reports

- Filtros por projeto, sprint, período, tipo de issue e equipa.
- Visualização em gráficos e tabelas.
- Exportação CSV, XLSX e PDF.
- Snapshots de métricas para relatórios históricos sem recalcular tudo.

### 4.8 Administração

- Utilizadores, equipas, permissões, estados e prioridades.
- Configuração de projetos, parâmetros Scrum e regras de release.
- Consulta de logs de auditoria e estado dos serviços.

## 5. Modelo MongoDB 4.4

**Base de dados:** `VCCTeamForgeDB`.

### 5.1 Collections

| Collection | Finalidade | Fase |
|---|---|---|
| `users` | Contas, perfil e autenticação | 1 |
| `teams` | Equipas e membros | 1 |
| `projects` | Projetos e configurações | 1 |
| `counters` | Numeração atómica de issues | 1 |
| `issues` | Issues e bugs | 2 |
| `issue_comments` | Comentários | 2 |
| `issue_history` | Histórico de eventos | 2 |
| `attachments` | Metadados de ficheiros | 2 |
| `sprints` | Planeamento Scrum | 3 |
| `sprint_snapshots` | Compromissos e evolução histórica | 3 |
| `test_cases` | Definição de testes | 4 |
| `test_plans` | Agrupamento de testes | 4 |
| `test_runs` | Resultados de execução | 4 |
| `releases` | Versões e aprovações | 4 |
| `report_snapshots` | Agregados para dashboards | 5 |
| `notifications` | Alertas internos | 5 |
| `audit_logs` | Eventos administrativos | 1 |
| `settings` | Parâmetros globais | 1 |

### 5.2 Exemplo de projeto

```javascript
{
  _id: ObjectId("..."),
  key: "DVC",
  name: "VCCTeamForge",
  description: "Gestão técnica",
  status: "active",
  leadUserId: ObjectId("..."),
  memberIds: [ObjectId("...")],
  settings: {
    methodology: "scrum",
    sprintDurationDays: 14,
    estimationType: "story_points"
  },
  createdAt: ISODate("2026-10-20T09:00:00Z"),
  updatedAt: ISODate("2026-10-20T09:00:00Z")
}
```

### 5.3 Exemplo de issue

```javascript
{
  _id: ObjectId("..."),
  projectId: ObjectId("..."),
  number: 125,
  key: "DVC-125",
  type: "story",
  title: "Implementar autenticação",
  description: "Login e logout",
  status: "in_progress",
  priority: "high",
  assigneeId: ObjectId("..."),
  reporterId: ObjectId("..."),
  sprintId: ObjectId("..."),
  parentIssueId: null,
  storyPoints: 5,
  labels: ["backend", "security"],
  blocked: false,
  blockReason: null,
  acceptanceCriteria: ["Login válido", "Logout termina a sessão"],
  createdAt: ISODate("2026-10-20T09:00:00Z"),
  updatedAt: ISODate("2026-10-20T09:00:00Z"),
  completedAt: null
}
```

### 5.4 Exemplo de sprint

```javascript
{
  _id: ObjectId("..."),
  projectId: ObjectId("..."),
  name: "Sprint 12",
  goal: "Concluir autenticação",
  status: "active",
  startDate: ISODate("2026-10-19T00:00:00Z"),
  endDate: ISODate("2026-11-01T23:59:59Z"),
  committedStoryPoints: 42,
  committedIssueCount: 15,
  createdAt: ISODate("2026-10-18T12:00:00Z"),
  closedAt: null
}
```

Os tipos reais serão BSON `ObjectId` e `Date`. Os exemplos acima usam sintaxe de shell MongoDB, não JSON puro.

### 5.5 Índices

```javascript
use VCCTeamForgeDB

db.projects.createIndex({ key: 1 }, { unique: true });
db.users.createIndex({ normalizedEmail: 1 }, { unique: true });
db.issues.createIndex({ projectId: 1, number: 1 }, { unique: true });
db.issues.createIndex({ projectId: 1, status: 1 });
db.issues.createIndex({ sprintId: 1, status: 1 });
db.issues.createIndex({ assigneeId: 1, status: 1 });
db.issue_history.createIndex({ issueId: 1, createdAt: -1 });
db.sprints.createIndex({ projectId: 1, status: 1 });
db.test_runs.createIndex({ projectId: 1, executedAt: -1 });
```

Criar os índices no processo de provisionamento/migração, não em cada pedido HTTP. Validar planos de execução de consultas relevantes.

### 5.6 Regras de persistência

- Usar `$inc` atómico na collection `counters` para números sequenciais; não usar contagem de documentos.
- Guardar comentários e histórico em collections separadas; evitar arrays ilimitados.
- Paginar listagens e projetar apenas os campos necessários.
- Usar UTC para timestamps e apresentar fuso horário no frontend.
- Não depender de transações multi-documento, pois a instância pode ser standalone; definir consistência e compensação para operações compostas.
- Para concorrência, usar campo `version` ou controlo otimista nas operações sensíveis.
- Não apagar histórico de sprints e auditoria ao arquivar projetos.

## 6. API REST — Contratos iniciais

Prefixo: `/api`.

| Método | Endpoint | Operação |
|---|---|---|
| POST | `/auth/login` | Iniciar sessão |
| POST | `/auth/logout` | Terminar sessão |
| GET | `/users/me` | Perfil atual |
| GET/POST | `/projects` | Listar/criar projetos |
| GET/PATCH | `/projects/{id}` | Consultar/editar projeto |
| GET/POST | `/issues` | Pesquisar/criar issues |
| GET/PATCH | `/issues/{id}` | Consultar/editar issue |
| POST | `/issues/{id}/comments` | Adicionar comentário |
| GET | `/issues/{id}/history` | Consultar histórico |
| GET/POST | `/sprints` | Listar/criar sprints |
| POST | `/sprints/{id}/start` | Iniciar sprint |
| POST | `/sprints/{id}/close` | Fechar sprint |
| GET/POST | `/test-cases` | Consultar/criar casos |
| POST | `/test-runs` | Registar execução |
| GET/POST | `/releases` | Consultar/criar release |
| GET | `/dashboard/overview` | Indicadores gerais |
| GET | `/reports/sprints/{id}` | Métricas da sprint |
| GET | `/reports/export` | Exportação parametrizada |

**Convenções:** validação no backend, erros no formato RFC 7807 (`application/problem+json`), paginação e ordenação com limites, códigos HTTP adequados, auditoria das mutações, autorização por projeto e documentação OpenAPI acessível apenas internamente.

## 7. Estrutura do repositório

```text
VCCTeamForge/
├── frontend/
│   └── src/
│       ├── app/
│       ├── components/
│       ├── features/
│       │   ├── dashboard/
│       │   ├── projects/
│       │   ├── issues/
│       │   ├── sprints/
│       │   ├── testing/
│       │   ├── releases/
│       │   └── reports/
│       ├── hooks/
│       └── services/
├── backend/
│   ├── app/
│   │   ├── api/             # routers FastAPI
│   │   ├── services/        # lógica de aplicação
│   │   ├── domain/          # entidades e regras
│   │   ├── repositories/    # acesso PyMongo
│   │   ├── schemas/         # modelos Pydantic (DTOs)
│   │   └── main.py
│   ├── tests/
│   └── pyproject.toml
├── database/
│   ├── indexes/
│   ├── migrations/
│   └── seed/
├── deployment/
│   ├── env/
│   ├── nginx/
│   ├── systemd/
│   └── scripts/
└── docs/
```

**Backend:** Routers → Services → Domain → Repositories (PyMongo). Não expor diretamente os documentos de persistência como contratos da API; usar schemas Pydantic (DTOs).

## 8. Deployment local

```text
Browsers na LAN
       |
       v
Nginx (80/443, endereço LAN)
       |-- /       -> frontend estático
       +-- /api   -> 127.0.0.1:5000 (FastAPI/Uvicorn)
                               |
                               v
                      127.0.0.1:27017
                         MongoDB 4.4
```

- Publicar o frontend como estáticos no Nginx.
- Instalar a API num virtualenv com dependências fixas (`requirements.txt`/lock) e executá-la com Uvicorn (ou Gunicorn com workers Uvicorn), com poucos workers para limitar a RAM.
- Executar a API com utilizador de sistema dedicado, através de `VCCTeamForge-api.service`.
- Usar variáveis de ambiente ou ficheiro de configuração protegido para segredos.
- Não abrir a porta 27017 à rede; manter `bindIp` no loopback se API e BD estiverem no mesmo computador.
- Abrir apenas a porta web à sub-rede autorizada; usar firewall.
- Preferir HTTPS interno com certificado confiável nos postos.
- Não pressupor resolução automática de `VCCTeamForge.local`; configurar DNS interno ou IP estático.

Os ficheiros de instalação (unidade systemd, Nginx, scripts de instalação/deploy e exemplo de configuração) e o procedimento completo estão em [`deployment/`](deployment/README.md).

### Configuração exemplificativa da API

```dotenv
APP_ENV=production
APP_HOST=127.0.0.1
APP_PORT=5000
MONGODB_HOST=127.0.0.1
MONGODB_PORT=27017
MONGODB_DATABASE=VCCTeamForgeDB
MONGODB_USERNAME=VCCTeamForge_app
MONGODB_PASSWORD=SUBSTITUIR_POR_SEGREDO_FORTE
MONGODB_AUTH_SOURCE=VCCTeamForgeDB
ATTACHMENTS_PATH=/var/lib/VCCTeamForge/attachments
```

Criar o utilizador da aplicação no MongoDB com permissões mínimas sobre `VCCTeamForgeDB`. Proteger o ficheiro de ambiente com permissões restritas; nunca incluir credenciais reais no Git.

## 9. Métricas e relatórios

| Métrica | Cálculo/observação |
|---|---|
| Burndown | Story points restantes por dia, a partir de snapshots/eventos |
| Velocity | Story points concluídos por sprint |
| Predictability | Compromisso inicial versus trabalho concluído do compromisso |
| Lead Time | Tempo entre criação e conclusão |
| Cycle Time | Tempo entre início de trabalho e conclusão |
| Aging | Tempo das issues ainda abertas |
| Bug Severity | Distribuição por severidade e estado |
| QA Pass Rate | Aprovados / executados com resultado relevante; definir tratamento de skipped/blocked |
| Release Quality | Bugs conhecidos e testes por versão |
| Workload | Distribuição de issues e capacidade, sem equiparar contagem a produtividade |

Não usar commits, linhas de código ou story points individuais como indicadores diretos de desempenho pessoal.

### Exportações

- **CSV:** tabelas e filtros ativos.
- **XLSX:** detalhe, múltiplas folhas e resumos.
- **PDF:** relatório formatado com KPIs, gráficos e contexto.
- Para grandes volumes, geração assíncrona e retenção temporária com limpeza.

## 10. Segurança, backups e operação

- Autenticação local com hash de passwords robusto e cookies `HttpOnly`, `Secure` (com HTTPS), `SameSite` e proteção CSRF.
- Rate limiting em login e registo de tentativas falhadas.
- Autorização por perfil e projeto, sempre validada na API.
- Sanitização da apresentação de Markdown; proteção contra XSS.
- Uploads com limites de tamanho, validação de tipo, nomes internos aleatórios e controlo de acesso.
- Auditoria de alterações críticas.
- Logs rotativos e política de retenção.
- Backup diário da BD e dos anexos, com cópia para outro dispositivo.
- Teste periódico de restauro; documentar RPO/RTO.
- Monitorizar RAM, CPU, disco e espaço disponível para backups.
- O MongoDB 4.4 não será atualizado neste projeto; documentar o risco residual do software sem suporte.

## 11. Roadmap

| Fase | Prazo indicativo | Entregáveis |
|---|---|---|
| 1. Fundação | Semana 1 | Estrutura, autenticação, permissões, MongoDB e Linux |
| 2. Projetos e issues | Semanas 2–3 | Projetos, membros, issues, comentários e histórico |
| 3. Scrum | Semanas 4–5 | Backlog, sprints, quadro, snapshots e dashboard MVP |
| 4. QA e releases | Semanas 6–7 | Casos, planos, execuções, bugs e releases |
| 5. Analytics | Semanas 8–9 | Reports, gráficos, CSV/XLSX/PDF |
| 6. Estabilização | Semana 10 | Testes, segurança, backups, documentação e produção |

**Estimativa condicional:** cerca de 10 semanas com dedicação significativa e âmbito controlado. Para desenvolvimento individual em paralelo com outras responsabilidades, rever o calendário.

### Marcos de entrega

1. **M1 — Base operacional:** login e gestão de projetos.
2. **M2 — Backlog utilizável:** issues, filtros, comentários e histórico.
3. **M3 — MVP Scrum:** planeamento, execução e fecho de sprints.
4. **M4 — Qualidade:** gestão de testes e releases.
5. **M5 — Gestão analítica:** dashboards e exportações.
6. **M6 — Produção local:** deployment, backups e validação.

## 12. Critérios de aceitação do MVP

- [ ] Autenticação e autorização por projeto.
- [ ] Criar, editar e arquivar projetos.
- [ ] Associar utilizadores a projetos.
- [ ] Criar, pesquisar e atualizar issues.
- [ ] Comentários e histórico consultável.
- [ ] Criar e iniciar sprint.
- [ ] Adicionar e estimar issues numa sprint.
- [ ] Movimentar issues no quadro Scrum.
- [ ] Marcar e consultar impedimentos.
- [ ] Dashboard da sprint com KPIs.
- [ ] Fechar sprint e preservar compromisso/histórico.
- [ ] Reiniciar Linux e verificar arranque automático dos serviços.
- [ ] Fazer backup e restaurar MongoDB e anexos.
- [ ] Validar consumo de recursos com utilização representativa.

## 13. Backlog técnico inicial

### Fundação

- DEV-001: Criar solução backend modular.
- DEV-002: Criar projeto React/Vite/TypeScript.
- DEV-003: Implementar configuração por ambiente.
- DEV-004: Implementar acesso MongoDB 4.4 e testes de compatibilidade.
- DEV-005: Criar migrations/seeds e índices idempotentes.
- DEV-006: Implementar login/logout, sessão e RBAC.
- DEV-007: Configurar Nginx e serviço systemd.
- DEV-008: Configurar logging, tratamento de erros e health checks.

### Gestão operacional

- DEV-009: CRUD de projetos e associação de membros.
- DEV-010: CRUD de issues com numeração atómica.
- DEV-011: Filtros, paginação e ordenação.
- DEV-012: Comentários, histórico e auditoria.
- DEV-013: Anexos e controlo de acesso.
- DEV-014: Backlog e quadro Kanban.

### Scrum

- DEV-015: Criar e editar sprints.
- DEV-016: Planeamento e estimativas.
- DEV-017: Início e snapshot do compromisso.
- DEV-018: Fecho e transporte de issues.
- DEV-019: Dashboard de sprint e burndown.

### Evolução

- DEV-020: Casos e planos de teste.
- DEV-021: Execuções e evidências.
- DEV-022: Releases e checklists.
- DEV-023: Analytics e snapshots.
- DEV-024: Exportação CSV/XLSX/PDF.
- DEV-025: Testes de carga, segurança e restauro.

## 14. Questões a fechar antes da implementação

| # | Questão | Resposta (21-10-2026) | Estado |
|---|---|---|---|
| 1 | Arquitetura CPU e versão exata do Linux | x86_64, Intel Atom x5-Z8350 @ 1,44 GHz (4 cores, 1 thread/core, sem AVX); Debian GNU/Linux 13.6 (trixie) | Fechada |
| 2 | RAM disponível e tipo de disco | 1,9 GiB RAM (~1 GiB disponível) + 1,5 GiB swap; eMMC de 28,9 GB (`mmcblk1`, não rotacional) | Fechada |
| 3 | Versão exata do MongoDB 4.4 e configuração de autenticação | MongoDB 4.4.29 (build `ubuntu2004`, x86_64, OpenSSL 1.1.1w); autenticação configurada no ficheiro `.env` (`MONGODB_USERNAME`, `MONGODB_PASSWORD`, `MONGODB_AUTH_SOURCE`), fora do Git | Fechada |
| 4 | Número de projetos simultaneamente ativos | 6 por sprint | Fechada |
| 5 | Volume previsto de issues, testes e anexos | 6 por sprint; anexos não são previstos, mas a funcionalidade deve existir | Fechada |
| 6 | Necessidade de HTTPS com DNS interno ou acesso por IP | Acesso por IP, apenas na rede local, sem exposição à Internet (confirma §1) | Fechada |
| 7 | Regras de transição das issues e definição formal de `Done` | Fluxo sem saltos: avançar apenas para o estado seguinte (`todo` → `in_progress` → `code_review` → `testing` → `done`); recuos permitidos `in_progress` → `todo`, `code_review` → `in_progress`, `testing` → `in_progress`/`code_review` e `done` → `in_progress` (reabrir). Aplicação com um único utilizador (gestor), que faz todas as alterações. `Done` sem pré-condições adicionais | Fechada |
| 8 | Política de backups, retenção e restauro | Usar o standard: backup diário às 02:30, retenção dos 14 mais recentes, restauro via `vccteamforge-manage restore` (ver [`deployment/README.md`](deployment/README.md#backups-e-restauro)) | Fechada |

**Implicações do hardware:** CPU sem AVX (explica a impossibilidade de MongoDB ≥ 5.0) e RAM muito limitada — considerar `APP_WORKERS=1` (o exemplo em `deployment/env/api.env.example` usa 2), limitar a cache do WiredTiger e geração de exportações com volumes pequenos. O eMMC tem escrita limitada: manter logs rotativos e a retenção de backups; a cópia para outro dispositivo é essencial.

## 15. Recomendação final

Implementar primeiro **Projetos + Issues + Sprints + Dashboard**, com modelo histórico preparado desde o início. Só depois adicionar QA, releases e reports avançados. Manter MongoDB 4.4 no servidor atual, sem exigir upgrades, e validar compatibilidade das dependências antes de iniciar o desenvolvimento.
