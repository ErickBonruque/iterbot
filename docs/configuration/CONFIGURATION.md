<!-- generated-by: gsd-doc-writer -->

# Configuração do IterBot UTFPR

Este documento descreve todas as variáveis de ambiente, arquivos de configuração, valores padrão e overrides por ambiente do IterBot.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Docker Secrets](#docker-secrets)
- [Arquivo .env](#arquivo-env)
- [Configuração do Traefik](#configuração-do-traefik)
- [Campos Criptografados](#campos-criptografados)
- [Configurações Obrigatórias vs Opcionais](#configurações-obrigatórias-vs-opcionais)
- [Valores Padrão](#valores-padrão)
- [Overrides por Ambiente](#overrides-por-ambiente)
- [Configuração do Celery Beat](#configuração-do-celery-beat)
- [Configuração do Logging](#configuração-do-logging)

---

## Visão Geral

O IterBot utiliza **django-environ** para carregar configurações, com a seguinte ordem de precedência (maior para menor):

1. **Docker Secrets** — arquivos em `/run/secrets/` (produção)
2. **Variáveis de ambiente** — `os.environ`
3. **Arquivo `.env`** — carregado automaticamente por `django-environ`
4. **Valores padrão** — definidos em `config/env.py`

A configuração é centralizada no módulo `config/env.py`, que define dataclasses para cada grupo de configuração (`DjangoSettings`, `DatabaseSettings`, `WahaSettings`, etc.) e consolida tudo em `AppConfig`.

---

## Variáveis de Ambiente

### Django

| Variável | Obrigatória | Descrição | Docker Secret |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Sim (prod) | Chave secreta para sessões e assinatura criptográfica do Django. Em produção, usar Docker Secret. | `django_secret_key` |
| `DEBUG` | Não | Modo debug. **Nunca usar `True` em produção.** | — |
| `ALLOWED_HOSTS` | Não | Hostnames permitidos, separados por vírgula. Ex: `localhost,127.0.0.1,meudominio.com` | — |
| `DOMAIN` | Não | Domínio principal da aplicação. Usado pelo Traefik para roteamento. | — |
| `PORTAL_BASE_URL` | Sim (prod) | URL completa do portal de empresas (com protocolo). Obrigatória quando `DEBUG=False`. | — |

### Banco de Dados (PostgreSQL)

| Variável | Obrigatória | Descrição | Docker Secret |
|---|---|---|---|
| `DATABASE_URL` | Condicional | URL de conexão PostgreSQL. Ignorada se `postgres_password` secret existir. | — |
| `POSTGRES_DB` | Não | Nome do banco de dados. | — |
| `POSTGRES_USER` | Não | Usuário do banco de dados. | — |
| `POSTGRES_HOST` | Não | Host do PostgreSQL. | — |
| `POSTGRES_PORT` | Não | Porta do PostgreSQL. | — |
| — | — | Senha do PostgreSQL. Lida exclusivamente do Docker Secret. | `postgres_password` |

> **Nota:** Quando o Docker Secret `postgres_password` está disponível, a `DATABASE_URL` é construída automaticamente a partir de `POSTGRES_USER`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` e o secret. Caso contrário, usa `DATABASE_URL` diretamente.

### Redis

| Variável | Obrigatória | Descrição | Docker Secret |
|---|---|---|---|
| `REDIS_URL` | Não | URL de conexão Redis. Usada como broker do Celery e cache em produção. | — |

### WAHA (WhatsApp HTTP API)

| Variável | Obrigatória | Descrição | Docker Secret |
|---|---|---|---|
| `WAHA_URL` | Não | URL base da API WAHA. | — |
| `WAHA_API_KEY` | Não | Chave de autenticação da API WAHA. | `waha_api_key` |
| `WAHA_SESSION_NAME` | Não | Nome da sessão WhatsApp no WAHA. Cada sessão representa um número diferente. | — |
| `WAHA_TIMEOUT_SECONDS` | Não | Timeout em segundos para requisições à API WAHA. | — |
| `WAHA_DASHBOARD_USERNAME` | Não | Usuário para o dashboard do WAHA. | — |
| `WAHA_DASHBOARD_PASSWORD` | Não | Senha para o dashboard do WAHA. | `waha_dashboard_password` |
| `WHATSAPP_SWAGGER_USERNAME` | Não | Usuário para a documentação Swagger do WAHA. | — |
| `WHATSAPP_SWAGGER_PASSWORD` | Não | Senha para a documentação Swagger do WAHA. | `waha_swagger_password` |

### Credenciais da Aplicação

| Variável | Obrigatória | Descrição | Docker Secret |
|---|---|---|---|
| `BOT_DASHBOARD_USERNAME` | Não | Usuário para o dashboard do bot (Django admin). | — |
| `BOT_DASHBOARD_PASSWORD` | Não | Senha para o dashboard do bot. | — |
| `DJANGO_ADMIN_USERNAME` | Não | Usuário administrativo do Django. | — |
| `DJANGO_ADMIN_PASSWORD` | Não | Senha administrativa do Django. | — |

### Email

| Variável | Obrigatória | Descrição | Docker Secret |
|---|---|---|---|
| `EMAIL_BACKEND` | Não | Backend de email do Django. | — |
| `EMAIL_HOST` | Não | Host do servidor SMTP. | — |
| `EMAIL_PORT` | Não | Porta do servidor SMTP. | — |
| `EMAIL_USE_TLS` | Não | Habilitar TLS para SMTP. | — |
| `EMAIL_HOST_USER` | Não | Usuário SMTP. | — |
| `EMAIL_HOST_PASSWORD` | Não | Senha SMTP. | `email_password` |
| `DEFAULT_FROM_EMAIL` | Não | Email remetente padrão. | — |

> **Nota:** Quando `AWS_ACCESS_KEY_ID` e `AWS_SECRET_ACCESS_KEY` estão configurados, o backend de email muda automaticamente para `django_ses.SESBackend` (AWS SES), ignorando as configurações SMTP.

### AWS

| Variável | Obrigatória | Descrição | Docker Secret |
|---|---|---|---|
| `AWS_ACCESS_KEY_ID` | Não | Access key da AWS IAM. | — <!-- VERIFY: Docker Secret não definido no docker-compose.yml --> |
| `AWS_SECRET_ACCESS_KEY` | Não | Secret key da AWS IAM. | — <!-- VERIFY: Docker Secret não definido no docker-compose.yml --> |
| `AWS_DEFAULT_REGION` | Não | Região padrão da AWS. | — |

---

## Docker Secrets

O IterBot usa Docker Secrets para gerenciar credenciais sensíveis em produção. Os secrets são montados como arquivos em `/run/secrets/` dentro dos containers.

### Estrutura de Arquivos

Os secrets são armazenados no diretório `secrets/` na raiz do projeto:

```
secrets/
├── django_secret_key.txt        # Chave secreta do Django
├── postgres_password.txt         # Senha do PostgreSQL
├── waha_api_key.txt              # API key do WAHA
├── waha_dashboard_password.txt   # Senha do dashboard WAHA
├── waha_swagger_password.txt     # Senha do Swagger WAHA
├── email_password.txt            # Senha do servidor SMTP
└── .gitignore                    # Ignora arquivos .txt, mantém .txt.example
```

### Configuração Inicial

```bash
# Copiar templates de exemplo
cp secrets/django_secret_key.txt.example secrets/django_secret_key.txt
cp secrets/postgres_password.txt.example secrets/postgres_password.txt
cp secrets/waha_api_key.txt.example secrets/waha_api_key.txt
cp secrets/waha_dashboard_password.txt.example secrets/waha_dashboard_password.txt
cp secrets/waha_swagger_password.txt.example secrets/waha_swagger_password.txt

# Gerar valores seguros
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' > secrets/django_secret_key.txt
openssl rand -base64 32 > secrets/postgres_password.txt
openssl rand -base64 32 > secrets/waha_api_key.txt
openssl rand -base64 32 > secrets/waha_dashboard_password.txt
openssl rand -base64 32 > secrets/waha_swagger_password.txt
```

### Mapeamento Docker Compose

| Secret | Arquivo | Container |
|---|---|---|
| `django_secret_key` | `./secrets/django_secret_key.txt` | backend |
| `postgres_password` | `./secrets/postgres_password.txt` | db, backend |
| `waha_api_key` | `./secrets/waha_api_key.txt` | <!-- VERIFY: container mounting varies by deployment --> |
| `waha_dashboard_password` | `./secrets/waha_dashboard_password.txt` | waha (via env) |
| `waha_swagger_password` | `./secrets/waha_swagger_password.txt` | waha (via env) |
| `email_password` | `./secrets/email_password.txt` | backend |

### Ordem de Resolução

A função `_get_secret_or_env()` em `config/env.py` resolve cada valor na seguinte ordem:

1. Docker Secret (`/run/secrets/{nome}`) — se o arquivo existir
2. Variável de ambiente (`os.environ`)
3. Valor padrão — definido no código

---

## Arquivo .env

O projeto fornece dois templates:

- **`.env.example`** — Template completo com descrições e exemplos. Use como referência.
- **`.env.local`** — Template mínimo para desenvolvimento local com Docker Compose.
- **`.env.production.example`** — Template para produção em EC2.

### Uso

```bash
# Desenvolvimento local
cp .env.local .env
# Edite .env conforme necessário

# Produção
cp .env.production.example .env
# Preencha com valores reais
```

O `django-environ` carrega automaticamente o arquivo `.env` na raiz do projeto (`config/env.py:44`).

---

## Configuração do Traefik

O Traefik atua como proxy reverso com TLS (Let's Encrypt) e BasicAuth.

### Arquivo Principal

`infra/traefik/traefik.yml` — Configuração estática do Traefik:

- **Entry points:** `web` (porta 80) e `websecure` (porta 443)
- **TLS:** CertResolver `letsencrypt` com HTTP challenge
- **Logging:** JSON format, nível INFO
- **Docker provider:** rede `web`, containers não expostos por padrão (`exposedByDefault: false`)

> **Nota:** O email do Let's Encrypt em `traefik.yml` (`admin@iterbot.example.com`) deve ser alterado para o email real de produção. <!-- VERIFY: Email do Let's Encrypt deve ser configurado para o domínio real de produção -->

### Middlewares Dinâmicos

`infra/traefik/dynamic/middlewares.yml` define:

| Middleware | Tipo | Descrição |
|---|---|---|
| `security-headers` | Headers | HSTS, XSS filter, content-type nosniff, frame deny, SSL redirect, custom frame options |
| `rate-limit` | RateLimit | 100 req/s com burst de 50 |
| `waha-auth` | BasicAuth | Protege o dashboard WAHA (`/etc/traefik/users/waha-users.txt`) |
| `admin-auth` | BasicAuth | Protege o admin Django e portal (`/etc/traefik/users/admin-users.txt`) |

### Arquivos htpasswd

Configurados via `deployment/scripts/setup-htpasswd.sh`:

- `secrets/users/waha-users.txt` — Credenciais do WAHA dashboard
- `secrets/users/admin-users.txt` — Credenciais do admin/portal

---

## Campos Criptografados

O módulo `infra/security/` implementa criptografia simétrica (Fernet) para campos sensíveis no banco de dados:

- **`EncryptedCharField`** — `models.CharField` com criptografia automática
- **`EncryptedTextField`** — `models.TextField` com criptografia automática

A chave de criptografia é derivada dos primeiros 32 bytes do `DJANGO_SECRET_KEY`, com padding de zeros (`ljust(32, b"0")`) quando a chave é menor que 32 bytes. Modelos que usam campos criptografados (em `apps/bot/models.py`):

| Modelo | Campo | Tipo |
|---|---|---|
| `BotConfiguration` | `waha_api_key` | `EncryptedCharField` |
| `BotConfiguration` | `dashboard_password` | `EncryptedCharField` |
| `BotConfiguration` | `admin_password` | `EncryptedCharField` |

> **Atenção:** Se o `DJANGO_SECRET_KEY` for alterado, os dados criptografados existentes se tornarão ilegíveis. Faça backup antes de rotacionar a chave.

---

## Configurações Obrigatórias vs Opcionais

### Obrigatórias em Produção (`DEBUG=False`)

| Configuração | Motivo |
|---|---|
| `DJANGO_SECRET_KEY` | Sessões e assinatura criptográfica. Falha com valor inseguro. |
| `PORTAL_BASE_URL` | Geração de links no bot. Deve começar com `http://` ou `https://`. O app falha ao iniciar sem ela em produção. |
| `ALLOWED_HOSTS` | Segurança do Django. Não usar `*` em produção. |
| Docker Secrets (`postgres_password`, etc.) | Credenciais de produção não podem estar em variáveis de ambiente. |

### Opcionais com Padrão Seguro

| Configuração | Valor Padrão | Nota |
|---|---|---|
| `DEBUG` | `False` | Seguro por padrão |
| `REDIS_URL` | `redis://redis:6379/0` | Funciona com Docker Compose |
| `WAHA_URL` | `http://waha:3000` | Nome do container Docker |
| `WAHA_API_KEY` | `dev-api-key` | Apenas para desenvolvimento |
| `WAHA_SESSION_NAME` | `default` | Sessão padrão do WAHA |
| `WAHA_TIMEOUT_SECONDS` | `5` | Timeout de 5 segundos |
| `DATABASE_URL` | `sqlite:///{BASE_DIR}/db.sqlite3` (caminho absoluto) | `str` |

---

## Valores Padrão

Os valores padrão são definidos em `config/env.py` com resolução em cascata: `environ.Env()` define defaults iniciais, `_get_secret_or_env()` aplica Docker secrets quando disponíveis, e dataclasses definem defaults efetivos para desenvolvimento local:

| Variável | Valor Padrão | Tipo |
|---|---|---|
| `DEBUG` | `False` | `bool` |
| `DJANGO_SECRET_KEY` | `"dev-secret-key-change-in-production"` | `str` |
| `ALLOWED_HOSTS` | `"*"` | `str` |
| `DATABASE_URL` | `""` (string vazia) | `str` |
| `REDIS_URL` | `"redis://redis:6379/0"` | `str` |
| `WAHA_URL` | `"http://waha:3000"` | `str` |
| `WAHA_API_KEY` | `"dev-api-key"` | `str` |
| `WAHA_SESSION_NAME` | `"default"` | `str` |
| `WAHA_TIMEOUT_SECONDS` | `5` | `int` |
| `BOT_DASHBOARD_USERNAME` | `"admin"` | `str` |
| `BOT_DASHBOARD_PASSWORD` | `"password"` | `str` |
| `DJANGO_ADMIN_USERNAME` | `"admin"` | `str` |
| `DJANGO_ADMIN_PASSWORD` | `"admin"` | `str` |
| `DOMAIN` | `"localhost"` | `str` |
| `PORTAL_BASE_URL` | `""` (string vazia) | `str` |
| `EMAIL_BACKEND` | `"django.core.mail.backends.console.EmailBackend"` | `str` |
| `EMAIL_HOST` | `""` (string vazia) | `str` |
| `EMAIL_PORT` | `587` | `int` |
| `EMAIL_USE_TLS` | `True` | `bool` |
| `EMAIL_HOST_USER` | `""` (string vazia) | `str` |
| `EMAIL_HOST_PASSWORD` | `""` (string vazia) | `str` |
| `DEFAULT_FROM_EMAIL` | `"bonrqueruck@gmail.com"` | `str` |
| `AWS_ACCESS_KEY_ID` | `""` (string vazia) | `str` |
| `AWS_SECRET_ACCESS_KEY` | `""` (string vazia) | `str` |
| `AWS_DEFAULT_REGION` | `"us-east-1"` | `str` |
| `WAHA_DASHBOARD_USERNAME` | `"admin"` | `str` |
| `WAHA_DASHBOARD_PASSWORD` | `"password"` | `str` |
| `WHATSAPP_SWAGGER_USERNAME` | `"swagger"` | `str` |
| `WHATSAPP_SWAGGER_PASSWORD` | `"password"` | `str` |
| `POSTGRES_DB` | `"iterbot"` | `str` |
| `POSTGRES_USER` | `"iterbot_user"` | `str` |
| `POSTGRES_HOST` | `"db"` | `str` |
| `POSTGRES_PORT` | `"5432"` | `str` |

> **Nota:** O fallback para `DATABASE_URL` é `sqlite:///{BASE_DIR}/db.sqlite3`, usado apenas quando não há Docker Secret `postgres_password` e `DATABASE_URL` não está configurada.

### Valores Padrão Adicionais do Django (`settings.py`)

| Configuração | Valor |
|---|---|
| `LANGUAGE_CODE` | `"pt-br"` |
| `TIME_ZONE` | `"America/Sao_Paulo"` |
| `USE_I18N` | `True` |
| `USE_TZ` | `True` |
| `DEFAULT_AUTO_FIELD` | `"django.db.models.BigAutoField"` |
| `WSGI_APPLICATION` | `"waha_bot.wsgi.application"` |
| `ROOT_URLCONF` | `"waha_bot.urls"` |
| `SITE_ID` | `1` |
| `STATIC_URL` | `"/static/"` |
| `STATIC_ROOT` | `BASE_DIR / "staticfiles"` |
| `STATICFILES_STORAGE` | `"whitenoise.storage.CompressedManifestStaticFilesStorage"` |
| `KEY_PREFIX` (em `CACHES`) | `"iterbot"` |
| `CELERY_TASK_SERIALIZER` | `"json"` |
| `CELERY_RESULT_SERIALIZER` | `"json"` |
| `CELERY_ACCEPT_CONTENT` | `["json"]` |

---

## Overrides por Ambiente

### Desenvolvimento Local

Use `.env.local` como base:

```bash
cp .env.local .env
```

Configurações-chave para desenvolvimento:

| Variável | Valor Recomendado | Motivo |
|---|---|---|
| `DEBUG` | `True` | Páginas de erro detalhadas |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,backend` | Hostnames locais |
| `DOMAIN` | `localhost` | Domínio local |
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` | Emails no terminal |
| `REDIS_URL` | `redis://redis:6379/0` | Container Docker |

**Cache em desenvolvimento:** Usa `LocMemCache` com location `iterbot-dev-cache` automaticamente quando `DEBUG=True`.

**Banco de dados em desenvolvimento:** Se não houver Docker Secret `postgres_password` e `DATABASE_URL` não estiver definida, o Django usará SQLite automaticamente.

### Produção (EC2)

Use `.env.production.example` como base:

```bash
cp .env.production.example .env
# Preencha com valores reais de produção
```

Configurações obrigatórias para produção:

| Variável | Valor | Motivo |
|---|---|---|
| `DEBUG` | `False` | Segurança |
| `ALLOWED_HOSTS` | `${DOMAIN},www.${DOMAIN}` | Apenas domínios de produção |
| `PORTAL_BASE_URL` | `https://${DOMAIN}` | Links HTTPS no bot |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` | Envio real de emails |
| `EMAIL_HOST` | `email-smtp.us-east-1.amazonaws.com` | AWS SES <!-- VERIFY: Host SMTP do SES varia por região --> |

> **Nota:** Em produção, se `AWS_ACCESS_KEY_ID` e `AWS_SECRET_ACCESS_KEY` estiverem presentes, o backend de email muda automaticamente para `django_ses.SESBackend` — não é necessário configurar `EMAIL_BACKEND` manualmente.

**Configurações de segurança ativadas automaticamente em produção** (`DEBUG=False`):

- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
- `SECURE_SSL_REDIRECT = True`
- `SECURE_REDIRECT_EXEMPT = [r"^webhook/$"]` (webhook WAHA usa HTTP interno)
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `SECURE_BROWSER_XSS_FILTER = True`
- `SECURE_CONTENT_TYPE_NOSNIFF = True`
- `X_FRAME_OPTIONS = "DENY"`
- `SECURE_HSTS_SECONDS = 31536000` (1 ano)
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- `SECURE_HSTS_PRELOAD = True`

**Cache em produção:** Usa `RedisCache` com a `REDIS_URL` configurada.

**BasicAuth do Traefik:** Protege rotas sensíveis (WAHA dashboard, Django admin) com camada adicional de autenticação além do Django auth. Configurado via `deployment/scripts/setup-htpasswd.sh`.

<!-- VERIFY: O Security Group da EC2 deve permitir apenas portas 22, 80, 443 em produção -->

---

## Configuração do Celery Beat

As tarefas agendadas são configuradas em `waha_bot/settings.py`:

| Tarefa | Cron | Descrição |
|---|---|---|
| `send-weekly-job-review` | Toda segunda-feira às 08:00 | Envio semanal de review de vagas |
| `check-waha-health` | A cada 5 minutos | Health check da sessão WAHA |
| `clean-old-health-checks` | Todo domingo às 02:00 | Limpeza de registros antigos |

O timezone do Celery é `America/Sao_Paulo` (herdado de `TIME_ZONE`).

---

## Configuração do Logging

O IterBot usa **structlog** com renderer JSON para logs estruturados. Configurado em `waha_bot/settings.py`:

| Logger | Nível (dev) | Nível (prod) |
|---|---|---|
| `django` | `INFO` | `INFO` |
| `apps` | `DEBUG` | `INFO` |
| `root` | `INFO` | `INFO` |

Processadores structlog (em ordem):

1. `merge_contextvars` — Contexto do Correlation ID
2. `filter_by_level` — Filtro por nível
3. `TimeStamper(fmt="iso")` — Timestamps ISO 8601
4. `add_logger_name` — Nome do logger
5. `add_log_level` — Nível do log
6. `PositionalArgumentsFormatter` — Formatação de argumentos
7. `StackInfoRenderer` — Stack traces
8. `format_exc_info` — Exceções formatadas
9. `UnicodeDecoder` — Decodificação Unicode
10. `JSONRenderer` — Saída em JSON

### Middlewares de Logging

| Middleware | Arquivo | Função |
|---|---|---|
| `CorrelationIdMiddleware` | `infra/middleware/correlation_id.py` | Adiciona `X-Correlation-ID` a cada request/response e ao contexto structlog |
| `StructuredLoggingMiddleware` | `infra/middleware/structured_logging.py` | Log JSON de requests/responses com duração, método, path e status |

---

## Configuração do Docker Compose

### Serviços

| Serviço | Imagem | Porta | Descrição |
|---|---|---|---|
| `traefik` | `traefik:v3.6` | 80, 443 (8080 apenas em dev) <!-- VERIFY: porta 8080 removida em produção --> | Proxy reverso com TLS |
| `db` | `postgres:15-alpine` | 5432 (interno) | Banco de dados PostgreSQL |
| `redis` | `redis:7-alpine` | 6379 (interno) | Cache e broker Celery |
| `backend` | Build local (Python 3.11) | 8000 | Django + Gunicorn |
| `waha` | `devlikeapro/waha` | 3000 | WhatsApp HTTP API |

### Redis

O Redis é configurado com:

- `appendonly yes` — Persistência AOF
- `maxmemory 256mb` — Limite de memória
- `maxmemory-policy allkeys-lru` — Evicção LRU

### Volumes

| Volume | Descrição |
|---|---|
| `postgres_data` | Dados do PostgreSQL |
| `redis_data` | Dados do Redis |
| `waha_sessions` | Sessões do WAHA |
| `traefik_certs` | Certificados Let's Encrypt |

### Rede

Todos os serviços estão na rede `web` (bridge, subnet `172.20.0.0/16`).

---

## Validação de Ambiente

Para validar a configuração antes de iniciar os serviços:

```bash
make validate
# ou
bash deployment/scripts/validate_environment.sh
```

Para configuração inicial completa (secrets + validação):

```bash
make setup
```