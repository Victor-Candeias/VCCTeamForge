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
| `ATTACHMENTS_PATH` | `var/attachments` | Absoluto em produção |

Em `APP_ENV=production` a aplicação recusa arrancar se faltarem credenciais MongoDB ou se
`ATTACHMENTS_PATH` for relativo.

## Dependências

- Limites de versão em `pyproject.toml`.
- Versões exatas de runtime em `requirements.txt`, geradas com `scripts/lock-requirements.sh`.
- Em produção instalar apenas `requirements.txt` e o pacote (`pip install --no-deps .`).
