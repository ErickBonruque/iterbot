<!-- generated-by: gsd-doc-writer -->

# Guia de Desenvolvimento — IterBot UTFPR

Este documento descreve como configurar o ambiente local, executar comandos de build, seguir o estilo de código e contribuir com o projeto.

---

## Sumário

1. [Setup Local](#setup-local)
2. [Comandos de Build](#comandos-de-build)
3. [Estilo de Código](#estilo-de-código)
4. [Convenções de Branch](#convenções-de-branch)
5. [Processo de PR](#processo-de-pr)
6. [Estrutura do Projeto](#estrutura-do-projeto)

---

## Setup Local

### Pré-requisitos

- **Python** 3.11
- **Poetry** (gerenciador de dependências)
- **Docker** e **Docker Compose** v2+
- **Git**

### 1. Fork e Clone

```bash
# Fork no GitHub, depois:
git clone https://github.com/<seu-usuario>/iterbot.git
cd iterbot
```

### 2. Configurar Secrets

O script `setup_secrets.sh` gera os arquivos de secret necessários em `secrets/`:

```bash
make setup
# ou diretamente:
bash ./deployment/scripts/setup_secrets.sh
```

Isso criará os seguintes arquivos em `secrets/`:
- `django_secret_key.txt`
- `postgres_password.txt`
- `waha_api_key.txt`
- `waha_dashboard_password.txt`
- `waha_swagger_password.txt`
- `email_password.txt`

> **Atenção:** Esses arquivos estão no `.gitignore` e **nunca** devem ser commitados. Substitua o `email_password.txt` pela senha SMTP real antes de usar em produção.

### 3. Configurar Variáveis de Ambiente

Copie o arquivo de exemplo e edite com seus valores:

```bash
cp .env.example .env
# Edite o .env com suas configurações locais
```

O `.env.example` contém todas as variáveis com descrições e valores de exemplo. Para desenvolvimento local, as variáveis principais são:

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DEBUG` | Modo debug do Django | `True` |
| `ALLOWED_HOSTS` | Hosts permitidos | `localhost,127.0.0.1` |
| `DATABASE_URL` | URL de conexão com o banco | `postgres://iterbot_user:senha@db:5432/iterbot` |
| `REDIS_URL` | URL de conexão com Redis | `redis://redis:6379/0` |
| `WAHA_URL` | URL da API WAHA | `http://waha:3000` |
| `WAHA_API_KEY` | Chave da API WAHA | (lido de `secrets/waha_api_key.txt`) |

### 4. Validar Ambiente

```bash
make validate
```

Isso executa `deployment/scripts/validate_environment.sh` para verificar se todas as configurações estão corretas.

### 5. Instalar Dependências ( desenvolvimento local sem Docker)

```bash
make dev-install
# ou: poetry install --all-extras
```

### 6. Subir Ambiente Local

```bash
make dev-run
# ou: docker compose up -d
```

Isso inicia todos os serviços: PostgreSQL, Redis, Backend (Django), WAHA e Traefik.

### 7. Executar Migrações

```bash
make migrate
```

### 8. Verificar Saúde dos Serviços

```bash
make health
```

Verifica se Backend, WAHA, PostgreSQL e Redis estão respondendo.

### URLs Locais

| Serviço | URL |
|---------|-----|
| Django Admin | http://localhost:8000/admin/ |
| API Docs | http://localhost:8000/api/docs/ |
| Dashboard do Bot | http://localhost:8000/dashboard/ |
| WAHA Dashboard | http://localhost:3000/dashboard |
| Traefik Dashboard | http://localhost:8080 |

---

## Comandos de Build

Todos os comandos são executados via `make`. Abaixo está a referência completa:

| Comando | Descrição |
|---------|-----------|
| `make setup` | Setup inicial: gera secrets e valida ambiente |
| `make validate` | Valida configuração de ambiente |
| `make dev-install` | Instala dependências Python com Poetry (`poetry install --all-extras`) |
| `make dev-run` | Sobe ambiente Docker em modo desenvolvimento |
| `make start` | Inicia todos os serviços Docker |
| `make stop` | Para todos os serviços Docker |
| `make restart` | Reinicia todos os serviços |
| `make rebuild` | Rebuild e reinicia todos os serviços (sem cache) |
| `make clean` | Para e remove todos os containers e volumes (⚠️ destrutivo) |
| `make health` | Verifica saúde dos serviços (Backend, WAHA, PostgreSQL, Redis) |
| `make status` | Mostra status dos containers e URLs de acesso |
| `make logs` | Mostra logs de todos os serviços (follow mode) |
| `make logs-waha` | Mostra logs do serviço WAHA |
| `make logs-backend` | Mostra logs do serviço Backend |
| `make waha-restart` | Reinicia apenas o serviço WAHA |
| `make waha-logs` | Mostra logs do WAHA filtrados por emojis de status |
| `make dev-test` | Executa testes dentro do container Docker |
| `make test` | Executa testes dentro do container Docker |
| `make lint` | Roda `ruff check` para linting |
| `make format` | Roda `ruff format` para formatação automática |
| `make ci-check` | Verificação completa de CI: `ruff check` + `ruff format --check` + `mypy` |
| `make migrate` | Executa migrações pendentes do banco |
| `make makemigrations` | Cria novas migrações a partir dos models |
| `make createsuperuser` | Cria superusuário Django |
| `make shell` | Abre o Django shell |
| `make backup` | Cria backup do banco e secrets em `backups/` |
| `make pre-commit-install` | Instala hooks de pre-commit |
| `make pre-commit-run` | Roda pre-commit em todos os arquivos |
| `make pre-commit-update` | Atualiza versões dos hooks de pre-commit |
| `make cz-commit` | Commit interativo com commitizen (conventional commits) |
| `make changelog` | Gera/atualiza CHANGELOG.md |

---

## Estilo de Código

### Ruff

O projeto usa **Ruff** como ferramenta unificada de linting e formatação, configurado em `pyproject.toml`:

- **Linha máxima:** 100 caracteres
- **Regras habilitadas:** `E`, `F`, `I`, `N`, `W` (pyflakes, isort, pycodestyle, naming)
- **Exceção:** `E501` é ignorada (linha longa handlerada pelo formatter)
- **Exceção por arquivo:** `waha_bot/settings.py` ignora `E402` (imports condicionais)
- **Exclusões:** diretórios de `migrations/` são excluídos
- **Formatação:** aspas duplas, indentação com espaços, fim de linha `lf`

#### Comandos

```bash
# Verificar linting
make lint
# ou: poetry run ruff check .

# Formatar código automaticamente
make format
# ou: poetry run ruff format .

# Checagem completa de CI (lint + format check + mypy)
make ci-check
```

### mypy

Verificação de tipos estáticos configurada em `pyproject.toml`:

- **Python version:** 3.11
- **Ferramenta:** `mypy` com plugin `mypy_django_plugin.main`
- **Settings module:** `waha_bot.settings.development`
- **Flags:** `warn_return_any`, `warn_unused_configs`, `disallow_untyped_defs`

```bash
poetry run mypy .
```

### Pre-commit

Hooks configurados em `.pre-commit-config.yaml`:

| Hook | Versão | Estágio |
|------|--------|---------|
| `trailing-whitespace` | v4.6.0 | pre-commit |
| `end-of-file-fixer` | v4.6.0 | pre-commit |
| `check-added-large-files` | v4.6.0 | pre-commit |
| `check-merge-conflict` | v4.6.0 | pre-commit |
| `check-yaml` | v4.6.0 | pre-commit |
| `check-json` | v4.6.0 | pre-commit |
| `check-toml` | v4.6.0 | pre-commit |
| `ruff` (com `--fix`) | v0.1.8 | pre-commit |
| `ruff-format` | v0.1.8 | pre-commit |
| `commitizen` | v4.13.9 | commit-msg |

Instalação dos hooks:

```bash
make pre-commit-install
# instala tanto pre-commit quanto commit-msg hook
```

Execução manual:

```bash
make pre-commit-run
# ou: poetry run pre-commit run --all-files
```

Atualização:

```bash
make pre-commit-update
# ou: poetry run pre-commit autoupdate
```

> Exclusão: arquivos em `migrations/` são excluídos dos hooks.

### Commits Conventional Commits

O projeto usa **commitizen** com o preset `cz_conventional_commits`. Formato:

```
tipo(escopo): descrição
```

Tipos comuns: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `perf`.

Para criar commits:

```bash
make cz-commit
# ou: poetry run cz commit
```

---

## Convenções de Branch

O projeto segue o modelo **GitHub Flow** com a branch principal `master`.

### Prefixos de Branch

| Prefixo | Propósito | Exemplo |
|---------|-----------|---------|
| `feature/` | Novas funcionalidades | `feature/busca-vagas-avancada` |
| `fix/` | Correção de bugs | `fix/erro-timeout-api` |
| `release/` | Preparação de release (opcional) | `release/v1.1` |
| `hotfix/` | Correções urgentes em produção (opcional) | `hotfix/erro-ssl-certificado` |

### Regras de Nomenclatura

1. **Apenas letras minúsculas** — sem maiúsculas
2. **Hífens como separadores** — usar `-`, não `_` ou espaços
3. **Sem números de issue** — manter nomes descritivos
4. **Descrições curtas** — idealmente abaixo de 50 caracteres
5. **Sem caracteres especiais** — apenas letras, números, hífens e `/`

### Fluxo

```bash
# Criar branch a partir de master
git checkout master && git pull
git checkout -b feature/nova-funcionalidade

# Desenvolver e commitar
git add .
make cz-commit

# Push e PR
git push -u origin feature/nova-funcionalidade
```

---

## Processo de PR

### 1. Criar a Branch e Desenvolver

Crie a branch a partir de `master`, faça as alterações e commit usando conventional commits (`make cz-commit`).

### 2. Verificar Qualidade Localmente

Antes de abrir o PR, execute:

```bash
make ci-check   # ruff check + ruff format check + mypy
make test       # pytest com cobertura mínima de 70%
```

### 3. Abrir Pull Request

Push para o remoto e abra um PR no GitHub contra a branch `master`.

### 4. CI Automático (Obrigatório)

O CI do GitHub Actions executa automaticamente três jobs:

| Job | O que faz |
|-----|-----------|
| **Lint** | `ruff check` + `ruff format --check` |
| **Test** | `pytest --cov` com PostgreSQL e Redis como serviços, cobertura mínima de 70% |
| **Security** | `pip-audit` (dependências críticas) + `trivy` (vulnerabilidades no filesystem) |

Os três jobs devem passar antes do merge.

### 5. Revisão e Merge

- **1 aprovação** necessária de qualquer membro do projeto
- Aprovações obsoletas são invalidadas por novos commits
- Estratégia de merge: **Squash merge** (um commit por feature/fix)
- Branch `master` é protegida: exige PR, aprovação e CI passando

### 6. Deploy

O deploy para EC2 é automático via GitHub Actions (`deploy.yml`) após merge em `master`, com gate de CI obrigatório. O processo:

1. CI passa (lint + test + security)
2. Deploy via AWS SSM para a instância EC2
3. Smoke check automático pós-deploy
4. Rollback disponível via `workflow_dispatch` com `rollback=true`

<!-- VERIFY: deploy é automático após merge em master com CI gate -->

---

## Estrutura do Projeto

```
iterbot/
├── apps/                       # Aplicações Django
│   ├── bot/                    # Bot WhatsApp (handlers, services, views, tasks, health)
│   ├── companies/              # Portal da empresa (views, forms, urls)
│   ├── core/                   # TimeStampedModel, health checks, admin customizado
│   ├── courses/                # Cursos e search terms
│   ├── dashboard/              # Dashboard admin + DRF API
│   ├── jobs/                   # Vagas (models, tasks, validators)
│   └── users/                  # Auth (models, adapters, services)
├── config/
│   └── env.py                  # Configuração de variáveis de ambiente e secrets
├── deployment/
│   └── scripts/                # Scripts de infra (setup-ec2, backup, smoke-check, rollback)
├── docker/
│   └── django/                 # Dockerfile e scripts de entrada
├── infra/
│   ├── jobspy/                 # Service de busca de vagas
│   ├── middleware/             # Correlation ID + structured logging
│   ├── security/               # Encryption + EncryptedCharField
│   ├── traefik/                # Config do proxy reverso
│   └── waha/                   # Client WAHA HTTP API
├── secrets/                    # Docker secrets (gitignored, gerados por setup_secrets.sh)
├── waha_bot/                   # Configuração do projeto Django (settings, urls, celery)
├── .env.example                # Template de variáveis de ambiente
├── .pre-commit-config.yaml      # Hooks de pre-commit
├── .github/workflows/           # CI e deploy workflows
├── docker-compose.yml           # Compose de desenvolvimento
├── docker-compose.prod.yml      # Compose de produção <!-- VERIFY: existe, usado no deploy -->
├── Makefile                     # Comandos de automação
└── pyproject.toml               # Dependências, config ruff, mypy, pytest, commitizen
```

### Testes

Os testes usam **pytest** com as seguintes configurações em `pyproject.toml`:

- **Settings module:** `waha_bot.settings.development`
- **Test paths:** `apps/`
- **Padrão de nomes:** `test_*.py` ou `*_test.py`
- **Cobertura mínima:** 70% (`fail_under = 70`)
- **Cobertura de branches:** habilitada
- **Diretórios omitidos:** `migrations`, `tests`, `__pycache__`, `conftest.py`

```bash
# Rodar testes localmente (requer Poetry)
poetry run pytest

# Rodar testes no container Docker
make test
# ou: make dev-test
```