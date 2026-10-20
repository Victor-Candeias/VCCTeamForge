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

## Dependências

- Limites de versão em `pyproject.toml`.
- Versões exatas de runtime em `requirements.txt`, geradas com `scripts/lock-requirements.sh`.
- Em produção instalar apenas `requirements.txt` e o pacote (`pip install --no-deps .`).
