<!-- generated-by: gsd-doc-writer -->

# Guia de Início Rápido — IterBot UTFPR

Guia passo a passo para configurar o ambiente de desenvolvimento e executar o IterBot localmente.

## Pré-requisitos

| Ferramenta | Versão | Como verificar |
|------------|--------|----------------|
| Docker | 20.10+ | `docker --version` |
| Docker Compose (plugin v2) | 2.0+ | `docker compose version` |
| Git | qualquer | `git --version` |
| Python | 3.11 | `python3 --version` |
| Poetry | 2.x | `poetry --version` |
| openssl | qualquer | `openssl version` |

> **Nota:** O Docker Compose v2 é usado como plugin (`docker compose`), não como comando separado (`docker-compose`). <!-- VERIFY: Docker Compose v2 is required based on docker compose usage in scripts -->

### Para desenvolvimento local (sem Docker)

- Python 3.11
- Poetry (gerenciador de dependências)
- PostgreSQL 15 em execução local
- Redis 7 em execução local

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/ErickBonruque/iterbot.git
cd iterbot
```

### 2. Configure as variáveis de ambiente e secrets

Use o script de setup automático:

```bash
./scripts/setup-local.sh
```

Esse script copia `.env.example` para `.env` e gera senhas aleatórias para os serviços. As credenciais são exibidas no terminal ao final. <!-- VERIFY: O script pode conter referências legadas a `iterbot`; verifique se os padrões de substituição correspondem ao `.env.example` atual. -->

**Configuração manual alternativa:**

```bash
cp .env.example .env
```

Depois edite `.env` — para desenvolvimento local, ajuste pelo menos:

```ini
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,backend
DOMAIN=localhost
```

### 3. Configure os Docker Secrets

```bash
make setup
```

Esse comando executa `deployment/scripts/setup_secrets.sh`, que gera os arquivos em `secrets/` com valores seguros:

- `secrets/django_secret_key.txt`
- `secrets/postgres_password.txt`
- `secrets/waha_api_key.txt`
- `secrets/waha_dashboard_password.txt`
- `secrets/waha_swagger_password.txt`
- `secrets/email_password.txt`

> **Importante:** Os arquivos `secrets/*.txt` (sem `.example`) estão no `.gitignore` e **nunca** devem ser commitados.

### 4. Valide o ambiente

```bash
make validate
```

Verifica se Docker está rodando, se os secrets existem e não estão vazios, e se o `docker-compose.yml` é válido.

## Primeira execução

### Com Docker (recomendado)

```bash
docker compose up -d
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

Verifique se todos os serviços estão saudáveis:

```bash
make health
```

Saída esperada:

```
  Backend:    ✅ OK
  WAHA:       ✅ OK
  PostgreSQL: ✅ OK
  Redis:      ✅ OK
```

Acesse os serviços:

| Serviço | URL |
|---------|-----|
| Django Admin | http://localhost:8000/admin/ |
| Status do Bot | http://localhost:8000/admin/status-bot/ |
| Observabilidade | http://localhost:8000/admin/observabilidade/ |
| Métricas de Negócio | http://localhost:8000/admin/metricas-negocio/ |
| Métricas Técnicas | http://localhost:8000/admin/metricas-tecnicas/ |
| WAHA Dashboard | http://localhost:3000/dashboard |
| Traefik Dashboard | http://localhost:8080 |

As credenciais do WAHA Dashboard são `admin` e a senha está em `secrets/waha_dashboard_password.txt`:

```bash
cat secrets/waha_dashboard_password.txt
```

### Sem Docker (desenvolvimento local)

```bash
poetry install --all-extras
poetry shell
export DATABASE_URL="postgresql://iterbot_user:senha@localhost:5432/iterbot"
export REDIS_URL="redis://localhost:6379/0"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Rodar os testes

```bash
# No container
make test
# ou
docker compose exec backend pytest

# Localmente (com Poetry)
poetry run pytest
```

## Problemas comuns

### 1. HEALTH CHECK: "Backend: ⚠️ Down"

O container `backend` demora cerca de 40 segundos para iniciar (`start_period: 40s` no docker-compose.yml). Aguarde e verifique os logs:

```bash
make logs-backend
```

Se persistir, confira se o PostgreSQL está saudável:

```bash
docker compose ps db
```

### 2. "ALLOWED_HOSTS error" ou erro 400 no Django

Verifique se `ALLOWED_HOSTS` no `.env` inclui `backend` e `localhost`:

```ini
ALLOWED_HOSTS=localhost,127.0.0.1,backend
```

Após alterar o `.env`, reinicie os serviços:

```bash
docker compose down && docker compose up -d
```

### 3. "Permission denied" em `secrets/*.txt`

Os secrets precisam de permissões restritas:

```bash
chmod 600 secrets/*.txt
```

### 4. WAHA não conecta / 401 Unauthorized

Confira se `WAHA_API_KEY` no `.env` coincide com `secrets/waha_api_key.txt`. Reinicie o WAHA:

```bash
make waha-restart
```

### 5. Docker Compose não encontra o comando

O projeto usa o **plugin v2** (`docker compose`), não o comando legado (`docker-compose`). Verifique:

```bash
docker compose version
```

### 6. Porta já em uso (80, 443, 3000, 8000)

Identifique o processo conflitante:

```bash
sudo lsof -i :8000
sudo lsof -i :3000
```

E encerre-o ou ajuste as portas no `docker-compose.yml`.

## Próximos passos

- [Visão Geral da Arquitetura](../architecture/OVERVIEW.md) — entender os componentes do sistema
- [Configuração Detalhada](../configuration/CONFIGURATION.md) — todas as variáveis de ambiente e secrets
- [Guia Docker Completo](COMO_RODAR_DOCKER.md) — troubleshooting avançado e comandos Docker
- [Configuração Local](CONFIGURACAO_LOCAL.md) — desenvolvimento sem Docker
- [Contribuindo](../../CONTRIBUTING.md) — convenções de branch, commits e PRs
