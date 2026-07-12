<!-- generated-by: gsd-doc-writer -->

# Visão Geral da Arquitetura — IterBot UTFPR

## Visão Geral do Sistema

O IterBot é um assistente WhatsApp que conecta estudantes da UTFPR a oportunidades de estágio e emprego. O sistema opera em duas frentes: (1) busca automática de vagas online via scraping pré-agendado (LinkedIn, Indeed, Glassdoor através do python-jobspy, executado diariamente às 07:00 e armazenado em `DailyJob`) e (2) vagas locais cadastradas por empresas da região por meio de um portal web. Estudantes interagem exclusivamente pelo WhatsApp — autenticam-se com credenciais do portal do aluno, selecionam seu curso e recebem sugestões de vagas em milissegundos (consultando banco local, sem scraping em tempo real) — enquanto empresas utilizam um portal web (`/empresas/*`) para cadastro e gestão de vagas. A arquitetura segue o padrão monolítico Django com filas assíncronas (Celery + Redis) para tarefas em background, integração com WhatsApp via WAHA (WhatsApp HTTP API), proxy reverso (Traefik) com TLS e BasicAuth em produção, e rastreamento completo de ações do bot via `BotActionLog`.

## Diagrama de Componentes

```mermaid
graph TB
    subgraph "Cliente"
        STUDENT[Estudante WhatsApp]
        COMPANY[Empresa Navegador]
        ADMIN[Admin Navegador]
    end

    subgraph "Proxy / Bordas"
        TRAEFIK[Traefik v3.6<br/>TLS + Let's Encrypt<br/>BasicAuth + Security Headers]
    end

    subgraph "Aplicação Django (backend)"
        WEB[Django REST + Templates<br/>:8000]
        API[DRF API<br/>/api/*]
        ADMIN_DJANGO[Django Admin<br/>Unfold]
        WEBHOOK[Webhook WhatsApp<br/>/webhook/]
        BOT_SVC[BotService<br/>Orquestrador]
        AUTH_HNDLR[AuthenticationHandler]
        JOB_HNDLR[JobSearchHandler]
        MENU_HNDLR[MenuHandler]
        REVIEW_HNDLR[JobReviewHandler]
        BOT_LOG[BotActionLog]
        COMPANY_PORTAL[Portal Empresas<br/>/empresas/*]
    end

    subgraph "Celery (Tarefas Assíncronas)"
        WORKER[Celery Worker]
        BEAT[Celery Beat<br/>Scheduler]
    end

    subgraph "Infraestrutura"
        WAHA[WAHA WhatsApp API<br/>:3000]
        DB[(PostgreSQL 15)]
        DAILY_JOB[(DailyJob<br/>PostgreSQL)]
        REDIS[(Redis 7)]
    end

    subgraph "Serviços Externos"
        JOBSAPI[python-jobspy<br/>LinkedIn, Indeed, Glassdoor]
        EMAIL[Provider de E-mail<br/>Resend / Brevo / AWS SES]
    end

    STUDENT -->|Mensagens WhatsApp| WAHA
    WAHA -->|Webhook direto POST /webhook/| WEB
    COMPANY -->|HTTPS| TRAEFIK
    TRAEFIK --> COMPANY_PORTAL
    ADMIN -->|HTTPS + BasicAuth| TRAEFIK

    WEBHOOK --> BOT_SVC
    BOT_SVC --> AUTH_HNDLR
    BOT_SVC --> JOB_HNDLR
    BOT_SVC --> MENU_HNDLR
    BOT_SVC --> REVIEW_HNDLR
    BOT_SVC --> BOT_LOG

    AUTH_HNDLR --> WAHA
    JOB_HNDLR --> WAHA
    JOB_HNDLR --> DAILY_JOB
    MENU_HNDLR --> WAHA
    REVIEW_HNDLR --> WAHA

    WEB --> DB
    WEB --> REDIS
    WORKER --> DB
    WORKER --> REDIS
    BEAT --> REDIS
    WORKER --> WAHA
    WORKER --> EMAIL
    WORKER --> JOBSAPI
    WORKER --> DAILY_JOB
```

## Fluxo de Dados

### 1. Fluxo principal: Estudante busca vagas pelo WhatsApp

1. O estudante envia uma mensagem pelo WhatsApp (ex: "3" para buscar vagas).
2. O WAHA recebe a mensagem e dispara um webhook POST para `/webhook/` no backend Django.
3. A view `webhook()` em `apps/bot/views.py` parseia o payload e delega para `BotService.process_message()`.
4. `BotService` recupera ou cria o `UserProfile` do usuário e identifica a intenção (comando global, ação pendente ou novo comando).
5. Se o fluxo é de busca de vagas, `JobSearchHandler` apresenta a lista de cursos cadastrados (`Course` → `SearchTerm`).
6. O estudante seleciona o curso e depois o termo de busca; `JobSearchHandler.perform_search()` consulta `DailyJob.objects.filter(search_term__in=...)` — resposta em milissegundos, sem scraping em tempo real [ref: apps/bot/handlers/job_search.py]. Se não houver vagas do dia, faz fallback para o dia anterior.
7. Os resultados são formatados e enviados de volta ao estudante via `WahaClient.send_message()`.
8. A ação é registrada em `BotActionLog` (action_type=SEARCH, status=SUCCESS/ERROR, duration_ms) para rastreamento e observabilidade [ref: apps/bot/models/bot_action_log.py].

### 2. Fluxo de autenticação de estudante

1. O estudante digita "1" ou "cadastrar" no WhatsApp.
2. `AuthenticationHandler` inicia o fluxo: RA → senha → e-mail institucional.
3. `UTFPRAuthService.authenticate()` valida as credenciais (atualmente placeholder, aceita qualquer RA exceto "000000").
4. `UTFPRAuthService.link_user()` cria/atualiza o `UserProfile` com RA, senha (criptografada via `EncryptedCharField`) e gera um token de confirmação de e-mail.
5. A task Celery `send_confirmation_email` envia um link de confirmação através do provider de e-mail configurado em `EMAIL_PROVIDER` (Resend por padrão; suporta Brevo, AWS SES, SMTP e console), com fallback opcional via `EMAIL_FALLBACK_PROVIDER`.
6. O estudante clica no link e `ConfirmEmailView` ativa `is_authenticated_utfpr = True`.
7. A partir desse momento, o estudante tem acesso completo ao bot (busca de vagas, review semanal).

### 3. Fluxo de cadastro de empresa (portal web)

1. A empresa acessa `/empresas/signup/` e cria uma conta com qualquer e-mail (django-allauth com `UTFPRAccountAdapter` libera domínio para empresas).
2. Após login, a empresa cadastra seus dados (`Company`) e cria vagas (`Job`) com status `PENDING`.
3. O administrador aprova a vaga via Django Admin, alterando o status para `APPROVED`.
4. Vagas aprovadas tornam-se visíveis no review semanal e buscas.

### 4. Fluxo de coleta automática de vagas (DailyJob)

1. Às 07:00 diariamente, o Celery Beat dispara a task `fetch_daily_jobs` [ref: apps/jobs/tasks.py:L27].
2. A task chama `fetch_and_save_daily_jobs(job_searcher)` — função pura separada da task para testabilidade [ref: apps/jobs/services.py:L133].
3. Itera sobre `SearchTerm.objects.filter(is_default=True)`, chama `JobSearchService.search()` por termo (usando a configuração de cada SearchTerm via `to_search_kwargs()`).
4. Resultados salvos via `DailyJob.objects.bulk_create(ignore_conflicts=True)` — idempotente; duplicatas por `unique_together(search_term, job_url, fetched_date)` são silenciosamente ignoradas [ref: apps/jobs/services.py:L171].
5. Vagas com mais de 7 dias são deletadas no mesmo ciclo [ref: apps/jobs/services.py:L193].
6. A task tem `max_retries=3` e `default_retry_delay=300s` para resiliência contra falhas transitórias.

### 5. Fluxo de review semanal automático

1. Toda segunda-feira às 08:00 (horário de Brasília), o Celery Beat dispara a task `send_weekly_job_review`.
2. A task itera sobre todos os `UserProfile` com curso selecionado e telefone preenchido.
3. Para cada usuário, combina vagas locais aprovadas + vagas do `DailyJob`, deduplica e formata uma mensagem WhatsApp.
4. Cada mensagem é enviada via `WahaClient.send_message()` com intervalo de 1 segundo entre envios.

### 6. Fluxo de monitoramento de saúde do bot

1. A cada 5 minutos, o Celery Beat dispara `check_waha_health`.
2. A task consulta `GET /api/sessions/{session_name}` no WAHA e registra o resultado em `BotHealthCheck`.
3. Se duas verificações consecutivas falharem, o sistema tenta reconexão automática com backoff exponencial (30s, 60s, 120s) e envia alerta por e-mail através do provider configurado (`infra/email/factory.py`). <!-- VERIFY: backoff durations are [30, 60, 120] seconds as defined in RECONNECT_BACKOFF -->

### 7. Monitoramento e Métricas no Admin

1. O Django Admin (`/admin/`) centraliza gestão e monitoramento. Páginas customizadas estão em `/admin/status-bot/`, `/admin/observabilidade/`, `/admin/metricas-negocio/` e `/admin/metricas-tecnicas/`.
2. Todas as páginas são protegidas pelo próprio Django Admin (`is_staff=True`). Usuários não autenticados são redirecionados para `/admin/login/`.
3. As páginas de métricas consomem `DashboardService` (`apps/core/services.py`) que agrega dados de múltiplos modelos (`BotHealthCheck`, `BotActionLog`, `InteractionLog`, `UserProfile`, `JobSearchLog`) via ORM.

## Abstrações Principais

| # | Abstração | Arquivo | Descrição |
|---|-----------|---------|-----------|
| 1 | `BaseHandler` | `apps/bot/handlers/base.py` | Classe abstrata base para handlers de conversação. Define `send_msg()`, `get_text()` e `handle()` — cada handler especializado (auth, busca, menu, review) herda desta classe. |
| 2 | `BotService` | `apps/bot/services.py` | Orquestrador central do bot. Recebe mensagens do webhook, identifica intenções e delega para o handler adequado conforme estado do usuário (`current_action`). |
| 3 | `WahaClient` | `infra/waha/client.py` | Cliente HTTP para a API do WAHA. Encapsula envio de mensagens (`send_message`), início de sessão (`start_session`) e normalização de chat IDs. |
| 4 | `JobSearchService` | `infra/jobspy/service.py` | Serviço de busca de vagas online. Invoca `scrape_jobs` do python-jobspy para LinkedIn, Indeed e Glassdoor e retorna lista de dicts. Usado pela task `fetch_daily_jobs` para pré-busca diária — não chamado diretamente no webhook. |
| 5 | `DailyJob` | `apps/jobs/models/daily_job.py` | Model de vagas pré-fetched. Armazena vagas coletadas diariamente por `SearchTerm` com deduplicação via `unique_together(search_term, job_url, fetched_date)`. Campo `is_manual=True` permite inserção via admin. Dois índices compostos garantem queries sub-segundo no handler de busca. |
| 6 | `BotActionLog` | `apps/bot/models/bot_action_log.py` | Log de ações do bot. Registra cada interação significativa (SEARCH, MENU, AUTH, REVIEW, WAHA_SEND) com status SUCCESS/ERROR/TIMEOUT e campos para debugging (`error_message`, `error_type`, `duration_ms`, `metadata`). Consumido pelo `DashboardService` para métricas de observabilidade. |
| 7 | `UTFPRAuthService` | `apps/users/services.py` | Serviço de autenticação de estudantes. Métodos: `authenticate()`, `link_user()`, `confirm_email()`, `resend_confirmation()`, `logout()`. |
| 8 | `BotHealthMonitor` | `apps/bot/health.py` | Monitor de saúde do WAHA. Verifica status da sessão, calcula uptime/tempo de resposta e gerencia limpeza de registros antigos. |
| 9 | `TimeStampedModel` | `apps/core/models.py` | Modelo abstrato base com campos `created_at` e `updated_at`. Todos os modelos principais (`UserProfile`, `Company`, `Job`, `BotConfiguration`, etc.) herdam desta classe. |
| 10 | `EncryptedCharField` / `EncryptedTextField` | `infra/security/fields.py` | Campos de modelo Django que criptografam dados automaticamente no banco usando Fernet. Chave primária: Docker Secret `encryption_key` / env `ENCRYPTION_KEY`. Usa `MultiFernet` para retrocompatibilidade com dados cifrados pela chave legada (`SECRET_KEY`). |
| 11 | `AppConfig` | `config/env.py` | Dataclass central de configuração. Agrega `DjangoSettings`, `DatabaseSettings`, `RedisSettings`, `WahaSettings`, credenciais e e-mail. Lê de Docker Secrets → env vars → defaults. |
| 12 | `CorrelationIdMiddleware` / `StructuredLoggingMiddleware` | `infra/middleware/correlation_id.py`, `infra/middleware/structured_logging.py` | Middlewares de request que adicionam correlation ID e logging estruturado (JSON via structlog) a todas as requisições HTTP. |

## Racional da Estrutura de Diretórios

| Diretório | Descrição |
|-----------|-----------|
| `apps/` | Aplicações Django discretas, cada uma representando um domínio funcional (bot, jobs, companies, users, courses, core). |
| `apps/bot/` | Lógica do bot WhatsApp: webhook view, serviço orquestrador, handlers de conversação, models de configuração/saúde/logs, tasks Celery e monitoramento. |
| `apps/bot/handlers/` | Handlers especializados de conversação separados por responsabilidade (auth, job_search, menu, job_review), seguindo o padrão Strategy com `BaseHandler` abstrato. |
| `apps/jobs/` | Modelos de domínio de vagas: `Company`, `Job`, `JobApplication`, `JobSearchLog`, `DailyJob` (vagas pré-fetched), validadores (CNPJ), task de coleta diária (`fetch_daily_jobs`) e task de review semanal. |
| `apps/companies/` | Portal web para empresas: views baseadas em classe (signup, login, perfil, CRUD de vagas), forms, mixins de autorização e URLs. |
| `apps/users/` | Model `UserProfile`, serviço de autenticação UTFPR, adapter django-allauth, validação de e-mail institucional, views de confirmação de e-mail e signals. |
| `apps/courses/` | Modelos `Course` e `SearchTerm` que conectam cursos da UTFPR a termos de busca para scraping. |
| `apps/core/` | Modelo abstrato `TimeStampedModel`, views de health check, `build_portal_url()`, admin customizado (`IterBotAdminSite`) com páginas de monitoramento, `DashboardService` (agregador de métricas que consome `BotHealthCheck`, `BotActionLog`, `InteractionLog`, `UserProfile`, `JobSearchLog`). |
| `infra/` | Infraestrutura transversal: cliente WAHA, serviço jobspy, campos criptografados, middlewares de correlation ID e logging estruturado, factory de providers de e-mail, configuração do Traefik. |
| `infra/waha/` | `WahaClient` — cliente HTTP que encapsula toda comunicação com a API do WAHA. |
| `infra/jobspy/` | `JobSearchService` — fachada para o python-jobspy com busca multi-plataforma de vagas. |
| `infra/security/` | `FieldEncryption` (Fernet) e `EncryptedCharField`/`EncryptedTextField` para criptografia transparente de dados sensíveis no banco. |
| `infra/middleware/` | `CorrelationIdMiddleware` e `StructuredLoggingMiddleware` — middlewares Django para tracing distribuído e logs estruturados em JSON. |
| `infra/email/` | Factory de providers de e-mail (`factory.py`), implementações (`providers/resend_provider.py`, `providers/brevo_provider.py`), idempotência (`idempotency.py`) e health checks (`health.py`). Resolve provider por `EMAIL_PROVIDER` com fallback opcional via `EMAIL_FALLBACK_PROVIDER`. |
| `infra/traefik/` | Configuração do Traefik: `traefik.yml` (dev), `traefik.prod.yml` (produção com redirect HTTPS), `dynamic/middlewares.yml` (security headers, rate limiting, BasicAuth). |
| `config/` | Configuração centralizada via `env.py` — dataclasses que leem de Docker Secrets → env vars → defaults. |
| `waha_bot/` | Projeto Django: `settings.py`, `urls.py` (roteamento raiz), `celery.py` (autodiscover), `asgi.py`/`wsgi.py`. |
| `docker/` | Dockerfiles multi-stage (`docker/django/Dockerfile`) e scripts de entrypoint/start. |
| `deployment/` | Scripts operacionais (provisionamento, backup/restore PostgreSQL, smoke check, rollback). |
| `secrets/` | Docker Secrets em arquivo (senhas, API keys, chaves) — **nunca** commitado no git. |
