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
2. ficheiro `.env` (por omissão `./.env`; outro caminho via `VCCTF_ENV_FILE`);
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
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `text` | `json` recomendado em produção |
| `LOG_FILE` | — | Se definido, ficheiro com rotação (`LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`) |
| `HEALTH_MIN_FREE_DISK_MB` | `1024` | Limiar de disco para readiness `degraded` |

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

## Migrations, índices e seeds

Executam-se pela CLI, nunca no arranque da API nem por pedido HTTP. Usam a mesma configuração
que a API. O utilizador MongoDB precisa de `readWrite` na base de dados.

```bash
.venv/bin/python -m app.cli status             # migrations e índices em falta
.venv/bin/python -m app.cli migrate --dry-run  # o que seria aplicado
.venv/bin/python -m app.cli migrate            # migrations pendentes + índices
.venv/bin/python -m app.cli seed               # dados iniciais em falta
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
