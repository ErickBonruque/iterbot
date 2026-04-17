<!-- generated-by: gsd-doc-writer -->

# IterBot-UTFPR

Assistente de WhatsApp para conectar estudantes da UTFPR com oportunidades de estágio e emprego — combina vagas online (via python-jobspy) com vagas locais cadastradas por empresas da região.

## Instalação

**Pré-requisitos:** Docker, Docker Compose e Git.

```bash
git clone git@github.com:ErickBonruque/CapyVagas-UTFPR.git
cd CapyVagas-UTFPR
```

## Início Rápido

1. **Configurar credenciais locais:**

   ```bash
   ./scripts/setup-local.sh
   ```
   O script copia `.env.example` para `.env` e gera senhas aleatórias para os serviços.

2. **Subir os serviços:**

   ```bash
   docker compose up -d
   ```

3. **Executar migrações e criar superusuário:**

   ```bash
   docker compose exec backend python manage.py migrate
   docker compose exec backend python manage.py createsuperuser
   ```

4. **Acessar os serviços:**

| Serviço | URL |
    |---------|-----|
    | Django Admin | http://localhost:8000/admin/ |
    | WAHA Dashboard | http://localhost:3000/dashboard/ |
    | Traefik | http://localhost:8080 |

## Exemplos de Uso

### Comandos Make mais usados

```bash
make dev-install      # Instalar dependências com Poetry
make start            # Subir todos os serviços
make stop             # Parar serviços
make health           # Verificar saúde dos serviços
make logs             # Ver logs (todos os serviços)
make logs-backend     # Ver logs do backend
make test             # Rodar testes no container
make lint             # Verificar lint com ruff
make format           # Formatar código com ruff
make ci-check         # Lint + format check + mypy
make backup           # Backup do banco e secrets
```

### Verificação de saúde dos serviços

```bash
make health
```
Verifica conectividade do Backend, WAHA, PostgreSQL e Redis.

### Desenvolvimento local (sem Docker)

```bash
poetry install --all-extras
poetry shell
export DATABASE_URL="postgresql://iterbot_user:senha@localhost:5432/iterbot"
export REDIS_URL="redis://localhost:6379/0"
python manage.py migrate
python manage.py runserver
```

## Estrutura do Projeto

```
apps/
  bot/          # Bot WhatsApp: handlers, services, views, tasks
  jobs/         # Vagas: models, tasks, validators
  companies/    # Portal de empresas
  dashboard/    # Dashboard admin + DRF API
  users/        # Autenticação e perfis
  courses/      # Cursos e termos de busca
  core/         # TimeStampedModel, health checks
infra/
  waha/         # Cliente WAHA HTTP
  jobspy/       # Serviço de busca de vagas
  security/     # Criptografia + EncryptedCharField
  traefik/      # Proxy reverso com TLS
deployment/
  scripts/      # setup-ec2, backup, smoke-check, rollback, etc.
```

## Contribuindo

Veja o guia completo em [CONTRIBUTING.md](CONTRIBUTING.md) — inclui convenções de branches, commits (Conventional Commits via `cz commit`) e fluxo de PR.

## Licença

Projeto de Iniciação Científica da UTFPR Campus Santa Helena. Sem arquivo de licença definido no repositório.