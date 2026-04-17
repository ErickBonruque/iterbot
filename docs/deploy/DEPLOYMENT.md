<!-- generated-by: gsd-doc-writer -->

# Implantação (Deployment)

Este documento descreve como implantar o IterBot UTFPR em produção na AWS EC2 usando Docker Compose, incluindo pipeline CI/CD, configuração de ambiente, rollback e monitoramento.

---

## Sumário

- [Alvos de Implantação](#alvos-de-implantação)
- [Pipeline de Build](#pipeline-de-build)
- [Configuração de Ambiente](#configuração-de-ambiente)
- [Procedimento de Rollback](#procedimento-de-rollback)
- [Monitoramento](#monitoramento)

---

## Alvos de Implantação

### EC2 com Docker Compose

O IterBot é implantado em uma única instância AWS EC2 usando Docker Compose com dois arquivos de composição:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

| Recurso | Detalhe |
|---------|---------|
| **Plataforma** | AWS EC2 (Ubuntu 22.04 LTS) |
| **Orquestração** | Docker Compose v2 (plugin) |
| **Proxy reverso** | Traefik v3.6 com TLS (Let's Encrypt) |
| **Banco de dados** | PostgreSQL 15 (container `iterbot_db`) |
| **Cache/Broker** | Redis 7 (container `iterbot_redis`) |
| **Backend** | Django 5.0 + Gunicorn (container `iterbot_backend`) |
| **WhatsApp** | WAHA (container `iterbot_waha`) |
| **Task Queue** | Celery Worker + Beat (containers `iterbot_celery_worker` e `iterbot_celery_beat`) |

<!-- VERIFY: tipo de instância EC2 (t3.small) e região (us-east-1) -->

### Serviços em Produção

O `docker-compose.prod.yml` sobrepõe a configuração de desenvolvimento com:

- **Remoção de portas públicas** do backend (8000) e WAHA (3000) — todo tráfego passa pelo Traefik
- **Remoção do dashboard Traefik** (porta 8080) em produção
- **TLS com Let's Encrypt** via `certResolver` configurado em `traefik.prod.yml`
- **BasicAuth** no WAHA Dashboard (`waha-auth@file`) e Django Admin/Portal (`admin-auth@file`)
- **Security headers** (HSTS, XSS filter, Content-Type nosniff, frame deny)
- **Celery Worker e Beat** para tasks assíncronas e agendadas

### Provisão da EC2

O script `deployment/scripts/setup-ec2.sh` realiza a provisão completa da instância:

1. Atualização de pacotes do sistema
2. Instalação de dependências (git, curl, openssl, jq)
3. Instalação do Docker Engine + Compose Plugin
4. Configuração do usuário `ubuntu` no grupo `docker`
5. Instalação do AWS CLI v2
6. Configuração de log rotation do Docker (`max-size: 10m`, `max-file: 3`)
7. Reinicialização do Docker daemon
8. Clone do repositório em `/home/ubuntu/iterbot`
9. Hardening do Security Group (bloqueio das portas 3000, 8000, 8080)
10. Configuração de crontabs para backup, verificação e monitoramento
11. Geração dos arquivos htpasswd para BasicAuth

```bash
sudo ./deployment/scripts/setup-ec2.sh
```

> Após a execução, faça logout e login para aplicar o grupo `docker`.

### Hardening do Security Group

O script `deployment/scripts/harden-security-group.sh` remove automaticamente o acesso público às portas 3000, 8000 e 8080. Apenas as portas 22 (SSH), 80 (HTTP) e 443 (HTTPS) devem permanecer abertas.

O script detecta automaticamente o ID da instância via IMDSv2 e o Security Group associado.

---

## Pipeline de Build

### CI (Pull Requests e branches feature/fix)

O workflow `.github/workflows/ci.yml` executa em cada PR e push em branches `feature/*` e `fix/*`:

| Job | Descrição |
|-----|-----------|
| **lint** | Ruff check + Ruff format check |
| **test** | pytest com cobertura, PostgreSQL e Redis como serviços |
| **security** | pip-audit ( vulnerabilidades críticas) + Trivy (scan de filesystem) |

### Deploy (push para master)

O workflow `.github/workflows/deploy.yml` executa em push para `master`:

1. **CI Gate** — Mesmos jobs de lint, format check e testes
2. **Deploy via SSM** — Envia comando remoto para a instância EC2 que:
   - Faz `git fetch origin master && git reset --hard origin/master`
   - Faz rebuild e restart dos containers com Docker Compose
   - Executa `smoke-check.sh` para verificar saúde do deploy
   - Aguarda até 10 minutos pelo resultado do comando SSM

O deploy usa AWS SSM (`AWS-RunShellScript`) para executar comandos remotamente na instância EC2, sem necessidade de acesso SSH direto pelo workflow.

> **Note**: O instance ID `***REMOVED***` está hardcoded no workflow. <!-- VERIFY: instance ID correto para a conta AWS -->

### Rollback via GitHub Actions

O mesmo workflow suporta rollback via `workflow_dispatch` com input `rollback=true`:

```yaml
# Exemplo no GitHub Actions
uses: ./.github/workflows/deploy.yml
with:
  rollback: 'true'
  commit: 'abc1234'  # opcional, default é HEAD^
```

### Build do Container Docker

O `docker/django/Dockerfile` usa multi-stage build:

1. **Builder** — Instala dependências Python via Poetry (`poetry install --only main --no-root --no-directory`)
2. **Final** — Copia pacotes instalados, entrypoint e código da aplicação
3. **Entrypoint** — Aguarda o PostgreSQL estar disponível antes de executar
4. **Start command** — `migrate --noinput` → `collectstatic --noinput` → `gunicorn` na porta 8000

---

## Configuração de Ambiente

### Variáveis de Ambiente

Copie `.env.production.example` para `.env` e preencha com valores reais:

```bash
cp .env.production.example .env
# Edite .env com os valores de produção
```

As variáveis essenciais para produção estão documentadas em `.env.example` e `.env.production.example`:

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DOMAIN` | Domínio principal da aplicação | `54-123-45-67.sslip.io` |
| `ALLOWED_HOSTS` | Hosts permitidos (separados por vírgula) | `${DOMAIN},www.${DOMAIN},waha.${DOMAIN},backend` |
| `DEBUG` | Modo debug (**sempre** `False` em produção) | `False` |
| `POSTGRES_DB` | Nome do banco PostgreSQL | `iterbot` <!-- VERIFY: .env.example ainda usa o nome legado `capyvagas`; docker-compose.yml usa `iterbot` como padrão --> |
| `POSTGRES_USER` | Usuário do PostgreSQL | `iterbot_user` <!-- VERIFY: .env.example ainda usa o nome legado `capyvagas_user`; docker-compose.yml usa `iterbot_user` como padrão --> |
| `POSTGRES_HOST` | Host do PostgreSQL | `db` |
| `POSTGRES_PORT` | Porta do PostgreSQL | `5432` |
| `REDIS_URL` | URL de conexão Redis | `redis://redis:6379/0` |
| `WAHA_URL` | URL do WAHA | `http://waha:3000` |
| `WAHA_SESSION_NAME` | Nome da sessão WhatsApp | `default` |
| `WAHA_API_KEY` | API key do WAHA (**Docker Secret**) | — |
| `WAHA_DASHBOARD_USERNAME` | Usuário do dashboard WAHA | `admin` |
| `WAHA_DASHBOARD_PASSWORD` | Senha do dashboard WAHA (**Docker Secret**) | — |
| `WHATSAPP_SWAGGER_USERNAME` | Usuário Swagger WAHA | `swagger` |
| `WHATSAPP_SWAGGER_PASSWORD` | Senha Swagger WAHA (**Docker Secret**) | — |
| `EMAIL_BACKEND` | Backend de email | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | Servidor SMTP (AWS SES) | `email-smtp.us-east-1.amazonaws.com` |
| `EMAIL_PORT` | Porta SMTP | `587` |
| `EMAIL_USE_TLS` | Usar TLS | `True` |
| `EMAIL_HOST_USER` | Usuário SMTP (SES) | — |
| `DEFAULT_FROM_EMAIL` | Email remetente | — |
| `S3_BACKUP_BUCKET` | Bucket S3 para backups | `iterbot-utfpr-backups` |
| `S3_BACKUP_PREFIX` | Prefixo S3 para backups | `daily` |

### Docker Secrets

Credenciais sensíveis são gerenciadas via Docker Secrets (arquivos em `secrets/`):

| Secret | Arquivo | Descrição |
|--------|---------|-----------|
| `django_secret_key` | `secrets/django_secret_key.txt` | Chave secreta do Django |
| `postgres_password` | `secrets/postgres_password.txt` | Senha do PostgreSQL |
| `waha_api_key` | `secrets/waha_api_key.txt` | API key do WAHA |
| `waha_dashboard_password` | `secrets/waha_dashboard_password.txt` | Senha do dashboard WAHA |
| `waha_swagger_password` | `secrets/waha_swagger_password.txt` | Senha do Swagger WAHA |
| `email_password` | `secrets/email_password.txt` | Senha SMTP (SES) |

#### Geração dos Secrets

```bash
# Gerar todos os secrets automaticamente
bash ./deployment/scripts/setup_secrets.sh

# Ou gerar manualmente
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' > secrets/django_secret_key.txt
openssl rand -base64 32 > secrets/postgres_password.txt
openssl rand -base64 32 > secrets/waha_api_key.txt
openssl rand -base64 32 > secrets/waha_dashboard_password.txt
openssl rand -base64 32 > secrets/waha_swagger_password.txt
```

> **Atenção**: O arquivo `secrets/email_password.txt` gerado pelo script é placeholder. Substitua pela senha SMTP real do AWS SES antes de subir em produção.

### BasicAuth (Traefik)

O Traefik protege rotas sensíveis com BasicAuth:

- **WAHA Dashboard** (`waha.${DOMAIN}`) → `waha-auth@file`
- **Django Admin e Portal de Empresas** (`${DOMAIN}/admin`, `${DOMAIN}/portal`) → `admin-auth@file`

Gere os arquivos htpasswd:

```bash
bash ./deployment/scripts/setup-htpasswd.sh
```

Os arquivos são salvos em `secrets/users/waha-users.txt` e `secrets/users/admin-users.txt` com permissão 600.

### Validação do Ambiente

Antes de iniciar os containers, valide a configuração:

```bash
# Validação local
bash ./deployment/scripts/validate_environment.sh

# Validação em EC2 (verifica também IAM Role para S3)
bash ./deployment/scripts/validate_environment.sh --ec2
```

O script verifica: comandos necessários (docker, git, aws), arquivos de secrets, arquivo `.env`, sintaxe do docker-compose, e permissões de executáveis.

---

## Procedimento de Rollback

### Rollback Automático via GitHub Actions

Dispare o workflow `Deploy IterBot to EC2` com `rollback=true`:

1. Acesse **Actions** no repositório
2. Selecione o workflow **Deploy IterBot to EC2**
3. Clique em **Run workflow**
4. Marque `rollback` como `true`
5. (Opcional) Informe o commit hash para o qual deseja retornar (default: `HEAD^`)

O workflow executará `rollback.sh` remotamente via SSM.

### Rollback Manual via SSH

Conecte-se à instância EC2 e execute:

```bash
# Rollback para o commit anterior (HEAD^)
cd /home/ubuntu/iterbot
bash ./deployment/scripts/rollback.sh

# Rollback para um commit específico
bash ./deployment/scripts/rollback.sh --commit abc1234
```

O script `rollback.sh`:

1. Faz `git fetch origin`
2. Cria uma branch temporária (`rollback-YYYYMMDD-HHMMSS`) no commit especificado
3. Faz rebuild e restart dos containers com Docker Compose
4. Executa `smoke-check.sh` para verificar a saúde do deploy revertido

Se o smoke check falhar, o script retorna código de saída 1 e indica que verificação manual é necessária.

### Backup e Restauração do Banco

#### Backup Automatizado (S3)

O backup do PostgreSQL executa diariamente às 02:00 via crontab:

```bash
# Backup manual
bash ./deployment/scripts/backup-postgres.sh

# Verificação de integridade do backup
bash ./deployment/scripts/backup-postgres.sh --verify
```

Backups são comprimidos com gzip e enviados para `s3://iterbot-utfpr-backups/daily/`. A política de lifecycle do S3 (definida em `deployment/config/s3-lifecycle.json`) remove:

- Backups diários após 30 dias
- Backups semanais após 90 dias

<!-- VERIFY: bucket S3 iterbot-utfpr-backups e lifecycle policy aplicados -->

#### Restauração

```bash
# Restaurar de um backup específico do S3
bash ./deployment/scripts/restore-postgres.sh s3://iterbot-utfpr-backups/daily/iterbot_backup_20260417_020000.sql.gz
```

O script solicita confirmação antes de sobrescrever o banco de dados ativo.

#### Teste de Restauração

O script `restore-test.sh` baixa o backup mais recente do S3, restaura em um container PostgreSQL temporário e verifica integridade:

```bash
# Teste com o backup mais recente
bash ./deployment/scripts/restore-test.sh

# Teste com data específica
bash ./deployment/scripts/restore-test.sh --date 20260417
```

Executa mensalmente às 04:00 do dia 1º via crontab configurado pelo `setup-ec2.sh`.

---

## Monitoramento

### Health Checks

Todos os serviços possuem health checks configurados no Docker Compose:

| Serviço | Health Check | Intervalo |
|---------|-------------|-----------|
| **PostgreSQL** | `pg_isready` | 10s (timeout: 5s, retries: 5) |
| **Redis** | `redis-cli ping` | 10s (timeout: 5s, retries: 5) |
| **Backend** | `curl -f http://localhost:8000/health/` | 30s (timeout: 10s, retries: 3, start_period: 40s) |
| **WAHA** | `wget` em `/api/version` com API key | 30s (timeout: 10s, retries: 3, start_period: 60s) |

### Smoke Check

O script `smoke-check.sh` executa verificações pós-deploy:

```bash
bash ./deployment/scripts/smoke-check.sh SEU-DOMINIO.sslip.io
```

Verificações realizadas:

| Código | Categoria | Verificações |
|--------|-----------|-------------|
| DEPL-01 | Serviços Docker | traefik, backend, db, redis, waha |
| DEPL-02 | HTTPS | Resposta HTTPS, redirecionamento HTTP→HTTPS |
| DEPL-04 | Backup S3 | AWS CLI disponível, IAM Role funcional |
| DEPL-05 | DNS | Domínio resolve corretamente |
| DEPL-07 | Log Rotation | Configuração de log do Docker |
| SEC-01 | Security Group | Portas 3000, 8000, 8080 não acessíveis publicamente |
| SEC-02 | BasicAuth | WAHA Dashboard e Django Admin requerem autenticação |
| SEC-03 | HTTPS | Certificado TLS válido, health endpoint responde 200 |

### Alertas por Email (AWS SES)

O monitoramento automatizado usa AWS SES para enviar alertas por email:

| Script | Periodicidade | Alerta |
|--------|--------------|--------|
| `check-backup.sh` | Diário (03:00) | Falta de backup diário no S3 ou backup com tamanho suspeito |
| `check-disk-space.sh` | A cada 6 horas | Uso de disco acima do limiar (default: 80%) |
| `restore-test.sh` | Mensal (dia 1º, 04:00) | Falha no teste de restauração do backup |

<!-- VERIFY: endereços de email para alertas e configuração SES verificada -->

Os emails de alerta são enviados por `aws ses send-email` diretamente da instância EC2, sem necessidade de servidor SMTP adicional.

### Comandos Úteis

```bash
# Verificar saúde dos serviços
make health

# Verificar status dos containers
make status

# Ver logs do backend
make logs-backend

# Ver logs do WAHA
make logs-waha

# Ver logs de todos os serviços
make logs

# Reiniciar apenas o WAHA
make waha-restart

# Backup manual
make backup

# Verificar ambiente
make validate

# Rodar migracoes
make migrate

# Criar superusuario
make createsuperuser
```

### Traefik

Em produção, o Traefik é configurado com:

- **Dashboard desabilitado** (`api.dashboard: false`, `api.insecure: false`)
- **Logs em formato JSON** para structured logging
- **Access logs em formato JSON**
- **Certificados Let's Encrypt** com challenge HTTP (`acme.json` em volume `traefik_certs`)
- **Middlewares dinâmicos** em `infra/traefik/dynamic/middlewares.yml`:
  - `security-headers` — HSTS (1 ano), X-Frame-Options, XSS filter, Content-Type nosniff
  - `rate-limit` — 100 req/s com burst de 50
  - `waha-auth` — BasicAuth para WAHA Dashboard
  - `admin-auth` — BasicAuth para Django Admin/Portal

### Celery

Em produção, dois serviços adicionais são iniciados via `docker-compose.prod.yml`:

- **`iterbot_celery_worker`** — Worker com concorrência 1, sem gossip/mingle
- **`iterbot_celery_beat`** — Scheduler de tasks periódicas com persistência em volume `celerybeat_data`