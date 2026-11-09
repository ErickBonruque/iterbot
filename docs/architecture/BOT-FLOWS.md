# Fluxos do Bot — IterBot UTFPR

## Visão Geral

`BotService.process_message()` é o entry point de todas as mensagens recebidas via webhook. Ele recebe `chat_id`, `message` e `from_me`, descarta mensagens próprias, cria ou busca o `UserProfile` pelo número de telefone, e roteia a mensagem para o handler correto com base no texto recebido e no estado atual da conversa.

Referência principal: `apps/bot/services.py:BotService`

### Portão de privacidade (LGPD)

Antes de qualquer roteamento, `_dispatch()` verifica `PrivacyConsentHandler.needs_consent(user)` — `apps/bot/handlers/privacy_consent.py`:

1. Quem ainda não aceitou recebe o texto `auth.privacy_consent` (editável no admin; `{contact_email}` vem de `PRIVACY_CONTACT_EMAIL`) e a conversa vai para o estado `privacy_consent`.
2. Só **depois** do texto exibido, *1* / *aceito* / *sim* registram `privacy_consent_at` e `privacy_consent_version` (hash curto do texto exato) e mostram o menu. Um "1" mandado antes do texto não conta.
3. *2* / *não aceito* responde `auth.privacy_consent_declined` e **apaga o perfil** (cascata em conversa e `InteractionLog`); a pessoa pode recomeçar com *oi*.
4. Qualquer outra resposta repete o texto. Vale para todo usuário sem aceite, inclusive os que já existiam.

Comandos globais depois do aceite: *parar* / *retomar* desligam/religam o resumo semanal.

---

## 1. Fluxo de Autenticação por E-mail

Estudantes que ainda não têm `is_authenticated_utfpr=True` precisam passar por este fluxo antes de acessar busca de vagas ou review.

### Diagrama

```mermaid
sequenceDiagram
    participant Estudante
    participant WAHA
    participant Webhook
    participant BotService
    participant AuthHandler as AuthenticationHandler
    participant UTFPRAuth as UTFPRAuthService
    participant Email as EmailDispatcher
    participant ConfirmView as ConfirmEmailView (web)

    Estudante->>WAHA: "cadastrar" / "1"
    WAHA->>Webhook: POST /webhook/
    Webhook->>BotService: process_message(chat_id, "cadastrar")
    BotService->>AuthHandler: start_login_flow(user, chat_id)
    AuthHandler-->>Estudante: Solicita RA

    Estudante->>WAHA: "123456"
    WAHA->>BotService: process_message(chat_id, "123456")
    BotService->>AuthHandler: handle_login_ra(user, chat_id, "123456")
    AuthHandler-->>Estudante: Solicita e-mail @alunos.utfpr.edu.br

    Estudante->>WAHA: "aluno@alunos.utfpr.edu.br"
    WAHA->>BotService: process_message(chat_id, "aluno@alunos.utfpr.edu.br")
    BotService->>AuthHandler: handle_login_email(user, chat_id, email)
    AuthHandler->>UTFPRAuth: link_user(chat_id, ra, email)
    UTFPRAuth-->>AuthHandler: UserProfile criado/atualizado
    AuthHandler->>Email: dispatch_confirmation_email(user_id)
    AuthHandler-->>Estudante: "Aguardando confirmação — verifique seu e-mail"

    Estudante->>ConfirmView: Clica no link do e-mail
    ConfirmView-->>Estudante: is_authenticated_utfpr=True; acesso liberado
```

### Passos

1. Estudante envia "cadastrar", "login", "entrar" ou "1" (menu não autenticado) — `BotService._handle_text_alias()` / `_handle_numeric_unauthenticated()` em `apps/bot/services.py`
2. `BotService` chama `AuthenticationHandler.start_login_flow()` — `apps/bot/handlers/authentication.py`
3. Se `user.is_authenticated_utfpr`, informa que já está cadastrado e retorna
4. Transição para `STATE_LOGIN_STEP_RA` e pedido do RA
5. `handle_login_ra()` valida o RA (mínimo 5 caracteres)
6. **Re-login:** se o número já tem e-mail verificado, `link_user()` autentica direto e o estado volta para `STATE_IDLE` (sem pedir e-mail de novo)
7. Primeiro cadastro: RA vai para `flow_data["temp_ra"]` e o estado avança para `STATE_LOGIN_STEP_EMAIL`
8. `handle_login_email()` valida o domínio `@alunos.utfpr.edu.br` via `validate_utfpr_email()`
9. `link_user(chat_id, ra, email)` cria/associa o `UserProfile` com um token novo
10. Estado avança para `STATE_LOGIN_STEP_WAITING_CONFIRMATION`; `dispatch_confirmation_email()` envia o link
11. Estudante clica no link; `ConfirmEmailView` seta `email_verified=True` e `is_authenticated_utfpr=True` — `apps/users/views.py`

> **Não há senha.** O bot não pede nem guarda senha do aluno — a prova de que a
> pessoa é aluna é o link enviado ao e-mail `@alunos`. Até nov/2026 havia um
> passo de senha (sugerindo a do Portal do Aluno) que não validava nada e
> deixava a senha em texto puro no `InteractionLog`; ele foi removido e a
> migração `bot.0009` apagou o que tinha sido coletado. Estados antigos
> `login_step_password`/`waiting_password` caem no passo de e-mail.
>
> No login de **empresa** pelo WhatsApp (que pede a senha do portal), a mensagem
> com a senha é gravada no `InteractionLog` como `[conteúdo sensível omitido]`
> (`SENSITIVE_INPUT_STATES` em `apps/bot/services.py`).

**Re-login:** Qualquer mensagem enquanto em `STATE_LOGIN_STEP_WAITING_CONFIRMATION` é tratada por `handle_login_waiting_confirmation()` — `apps/bot/handlers/authentication.py:L284`. O estudante pode digitar "reenviar" para receber o e-mail novamente.

---

## 2. Fluxo do Menu Principal

Disparado por qualquer saudação ("oi", "menu", "inicio") ou por um comando não reconhecido no fluxo atual.

### Diagrama

```mermaid
sequenceDiagram
    participant Estudante
    participant WAHA
    participant BotService
    participant MenuHandler

    Estudante->>WAHA: "oi" / "menu" / "inicio"
    WAHA->>BotService: process_message(chat_id, "oi")
    BotService->>BotService: _reset_state(user) — volta para STATE_IDLE
    BotService->>MenuHandler: send_menu(user, chat_id)

    alt Estudante autenticado (is_authenticated_utfpr=True)
        MenuHandler-->>Estudante: Menu autenticado\n1 - Buscar Vagas\n2 - Review\n3 - Logout\n4 - Trocar Curso
    else Não autenticado
        MenuHandler-->>Estudante: Menu não autenticado\n1 - Cadastrar/Login\n2 - Sou Empresa\n3 - Buscar Vagas
    end
```

### Passos

1. `BotService.process_message()` detecta saudação no conjunto de palavras-chave — `apps/bot/services.py:L80`
2. `_reset_state(user)` aplica transição para `STATE_IDLE` e limpa `flow_data` — `apps/bot/services.py:L266`
3. `MenuHandler.send_menu()` verifica `user.is_authenticated_utfpr` — `apps/bot/handlers/menu.py:L21`
4. Se autenticado: envia menu com opções 1=Buscar, 2=Review, 3=Logout, 4=Trocar Curso — `apps/bot/handlers/menu.py:L23`
5. Se não autenticado: envia menu com opções 1=Cadastrar/Login, 2=Empresa, 3=Buscar (com gate de autenticação) — `apps/bot/handlers/menu.py:L29`
6. Comandos de texto "cancelar" ou "voltar" também resetam o estado e exibem o menu — `apps/bot/services.py:L95`
7. "sair" realiza logout completo antes de resetar — `apps/bot/services.py:L96`
8. Comando não reconhecido aciona `send_unknown_command()` — `apps/bot/handlers/menu.py:L84`

**Roteamento de fluxos ativos:** Se `has_active_flow(current_action)` for True, `_handle_pending_action()` despacha para `auth_handler.handle()` ou `job_handler.handle()` antes de chegar ao menu — `apps/bot/services.py:L110`

---

## 3. Fluxo de Busca de Vagas

Acesso via opção "1" (menu autenticado) ou alias "vagas", "buscar", "cursos".

### Diagrama

```mermaid
sequenceDiagram
    participant Estudante
    participant WAHA
    participant BotService
    participant JobHandler as JobSearchHandler
    participant DB as Banco de Dados

    Estudante->>WAHA: "1" ou "vagas"
    WAHA->>BotService: process_message(chat_id, "1")
    BotService->>JobHandler: start_course_selection(user, chat_id)

    alt user.course já salvo (preferência persistente)
        JobHandler->>JobHandler: Sincroniza selected_course com user.course
        JobHandler->>JobHandler: start_term_selection(user, chat_id)
        JobHandler-->>Estudante: Lista de termos de busca do curso
    else Primeiro acesso ou sem preferência salva
        JobHandler->>DB: Course.objects.filter(is_active=True)
        JobHandler-->>Estudante: Lista de cursos ativos
        Estudante->>WAHA: "2" (seleciona curso)
        WAHA->>BotService: process_message(chat_id, "2")
        BotService->>JobHandler: handle_course_selection(user, chat_id, "2")
        JobHandler->>DB: user.course = courses[1]; user.save()
        JobHandler-->>Estudante: "Preferência salva: [Curso]"
        JobHandler->>JobHandler: start_term_selection(user, chat_id)
        JobHandler-->>Estudante: Lista de termos de busca do curso
    end

    Estudante->>WAHA: "1" (seleciona termo)
    WAHA->>BotService: process_message(chat_id, "1")
    BotService->>JobHandler: handle_term_selection(user, chat_id, "1")
    JobHandler->>JobHandler: perform_search(user, chat_id, [term], term_name)
    JobHandler->>DB: DailyJob.objects.filter(search_term__in=terms, fetched_date=hoje)
    DB-->>JobHandler: Lista de vagas pré-fetched
    JobHandler-->>Estudante: Vagas formatadas (máx. 5 por termo)
```

### Passos

1. `start_course_selection()` verifica autenticação; não autenticado recebe mensagem de bloqueio — `apps/bot/handlers/job_search.py:L48`
2. Se `user.course is not None` (preferência salva): sincroniza `selected_course` na sessão e pula direto para `start_term_selection()` — `apps/bot/handlers/job_search.py:L61`
3. Sem preferência: consulta `Course.objects.filter(is_active=True)` e exibe menu numerado — `apps/bot/handlers/job_search.py:L74`
4. Estado avança para `STATE_COURSE_SELECTION` — `apps/bot/handlers/job_search.py:L93`
5. Próxima mensagem: `handle_course_selection()` valida índice, salva `user.course` via `user.save(update_fields=["course"])` — `apps/bot/handlers/job_search.py:L153` e `L183`
6. `is_first_time` detectado **antes** do save — `apps/bot/handlers/job_search.py:L179`; na 1ª vez exibe mensagem de "preferência salva", nas trocas exibe "preferência atualizada"
7. `start_term_selection()` busca `SearchTerm.objects.filter(is_default=True)` associados ao curso — `apps/bot/handlers/job_search.py:L220`
8. Estado avança para `STATE_TERM_SELECTION`; estudante escolhe o termo
9. `handle_term_selection()` salva `selected_term` e chama `perform_search()` — `apps/bot/handlers/job_search.py:L270` e `L318`
10. `perform_search()` consulta `DailyJob.objects.filter(search_term__in=search_terms, fetched_date=hoje)` — NÃO chama jobspy diretamente (elimina timeout silencioso, BOT-03) — `apps/bot/handlers/job_search.py:L325`
11. Fallback automático: se não há vagas hoje, busca a data mais recente disponível — `apps/bot/handlers/job_search.py:L363`
12. Cria `JobSearchLog` por SearchTerm para rastreabilidade — `apps/bot/handlers/job_search.py:L370`
13. Retorna até `BOT_RESULTS_PER_TERM = 5` vagas por termo formatadas com título, empresa e link — `apps/bot/handlers/job_search.py:L323`

**DailyJob** é populado diariamente às 07:00 pela task `fetch_daily_jobs` — ver Seção 5.

---

## 4. Fluxo de Review de Vagas (Sob Demanda)

Acesso via opção "2" (menu autenticado) ou aliases "review", "vagas da semana".

### Diagrama

```mermaid
sequenceDiagram
    participant Estudante
    participant WAHA
    participant BotService
    participant ReviewHandler as JobReviewHandler
    participant JobsService as jobs/services.py
    participant DB as Banco de Dados

    Estudante->>WAHA: "2" ou "review"
    WAHA->>BotService: process_message(chat_id, "2")
    BotService->>ReviewHandler: send_review(user, chat_id)
    ReviewHandler->>ReviewHandler: Verifica is_authenticated_utfpr
    ReviewHandler->>ReviewHandler: Verifica selected_course na sessão
    ReviewHandler->>JobsService: build_review_for_user(selected_course)
    JobsService->>DB: Job aprovadas da área do curso — empresas parceiras
    JobsService->>DB: DailyJob da última coleta do curso — vagas online já filtradas
    JobsService->>JobsService: dedupe(parceiras + online)
    JobsService-->>ReviewHandler: Top 5 vagas combinadas
    ReviewHandler->>JobsService: format_review_message(course_name, jobs)
    ReviewHandler-->>Estudante: Mensagem formatada com até 5 vagas
```

### Passos

1. `send_review()` verifica `user.is_authenticated_utfpr`; bloqueia se não autenticado — `apps/bot/handlers/job_review.py`
2. Verifica `selected_course` na sessão; se ausente, solicita que o estudante faça uma busca primeiro
3. Envia "buscando review..." e chama `build_review_for_user(selected_course)`
4. `build_review_for_user()` junta as vagas de empresas parceiras da área do curso (`get_local_jobs_for_area`) com as vagas online da última coleta (`get_latest_daily_jobs`), já filtradas por relevância — `apps/jobs/services.py`
5. `dedupe()` remove a mesma vaga vinda de dois termos/sites — `apps/jobs/relevance.py`
6. Retorna as 5 primeiras; `format_review_message()` monta a mensagem

**Nota:** sem scraping na conversa — até nov/2026 o review rodava o jobspy ao vivo para todos os termos do curso, com o aluno esperando.

---

## 5. Task de Review Semanal Automático

Disparada toda segunda-feira às 08:00 (horário de Brasília) via Celery Beat e enviada **em lotes**, num ritmo conservador para o número não ser bloqueado pelo WhatsApp por cara de spam.

### Diagrama

```mermaid
sequenceDiagram
    participant CeleryBeat as Celery Beat (segunda, 08:00 BRT)
    participant Task as send_weekly_job_review task
    participant Service as send_weekly_reviews()
    participant DB as Banco de Dados
    participant WAHA

    CeleryBeat->>Task: Dispara send_weekly_job_review
    Task->>Service: send_weekly_reviews(min/max intervalo, max_per_run)
    Service->>DB: weekly_review_audience()[:max_per_run]
    loop Para cada aluno do lote
        Service->>Service: pausa aleatória (8–20 s) — não antes do 1º
        Service->>WAHA: send_message(vagas locais da área ou aviso amigável)
        alt WAHA aceitou
            Service->>DB: weekly_review_sent_at = agora
        else WAHA recusou (False) ou exceção
            Service->>Service: errors += 1 (aluno continua pendente)
        end
    end
    Service-->>Task: {sent, empty_notice, errors, remaining}
    opt remaining > 0 e o lote teve algum envio
        Task->>Task: apply_async(countdown=30 min) — próximo lote
    end
```

### Regras

1. **Público** (`weekly_review_audience()` em `apps/jobs/services.py`): aceitou o texto de privacidade (`privacy_consent_at`), não pediu *parar* (`weekly_review_opt_out=False`), tem curso escolhido e não recebeu nos últimos 6 dias (`weekly_review_sent_at`).
2. **Conteúdo:** só vagas locais da área do curso (`build_weekly_local_review()`, sem jobspy). Sem vaga nova, **sempre envia** o aviso `review.weekly_no_local_jobs`.
3. **Ritmo:** no máximo `WEEKLY_REVIEW_MAX_PER_RUN` (40) mensagens por execução, com pausa aleatória entre `WEEKLY_REVIEW_MIN_INTERVAL_SECONDS` (8 s) e `WEEKLY_REVIEW_MAX_INTERVAL_SECONDS` (20 s). Se sobrar público, a task reagenda a si mesma após `WEEKLY_REVIEW_BATCH_PAUSE_SECONDS` (30 min). Ex.: 200 alunos ≈ 5 lotes ≈ 3 h.
4. **Sem repetição:** `weekly_review_sent_at` é gravado a cada envio aceito; se a task rodar de novo no mesmo dia, ninguém recebe duas vezes.
5. **Falha:** `send_message` devolvendo `False` (HTTP não-2xx do WAHA) conta como erro e o aluno fica pendente. Um lote sem nenhum envio bem-sucedido **não** reagenda (evita laço com o WAHA fora do ar); a próxima segunda tenta de novo.
6. O aluno desliga/religa o resumo com *parar* / *retomar* (`BotService._set_weekly_review_opt_out`).

---

## 6. Fluxo de Autenticação de Empresa via WhatsApp

Empresas cadastradas no portal podem vincular seu número WhatsApp à conta do portal. Após o vínculo, o bot exibe um menu próprio de empresa (leitura).

### Diagrama — Primeiro Login

```mermaid
sequenceDiagram
    participant Empresa
    participant WAHA
    participant BotService
    participant CompanyAuthHandler
    participant CompanyAuthService
    participant Email

    Empresa->>WAHA: "empresa"
    WAHA->>BotService: process_message(chat_id, "empresa")
    BotService->>BotService: _start_company_onboarding()
    Note over BotService: company=None → mostra onboarding
    BotService-->>Empresa: Menu: 1=Criar conta / 2=Já tenho conta

    Empresa->>WAHA: "2"
    WAHA->>BotService: process_message(chat_id, "2")
    BotService->>CompanyAuthHandler: start_company_login_flow()
    CompanyAuthHandler-->>Empresa: "Digite o e-mail da empresa"
    Note over CompanyAuthHandler: STATE_COMPANY_LOGIN_EMAIL

    Empresa->>WAHA: "empresa@exemplo.com"
    WAHA->>BotService: process_message(chat_id, "empresa@exemplo.com")
    BotService->>CompanyAuthHandler: handle_company_login_email()
    CompanyAuthHandler->>CompanyAuthService: link_company_by_email(phone, email)
    CompanyAuthService-->>CompanyAuthHandler: UserProfile com token e company linkada
    CompanyAuthHandler->>Email: dispatch_company_confirmation_email(user_id)
    CompanyAuthHandler-->>Empresa: "Link enviado para empresa@exemplo.com"
    Note over CompanyAuthHandler: STATE_COMPANY_WAITING_CONFIRMATION

    Empresa->>Web: Clica no link /confirmar-empresa/<token>/
    Web->>CompanyAuthService: confirm_company_email(token)
    CompanyAuthService-->>Web: is_company_authenticated=True

    Empresa->>WAHA: "menu" (qualquer mensagem)
    WAHA->>BotService: process_message(chat_id, "menu")
    BotService->>MenuHandler: send_menu() — detecta is_company_authenticated=True
    MenuHandler-->>Empresa: Menu Empresa (vagas / portal / nova vaga / sair)
```

### Diagrama — Re-login (empresa já vinculada)

```mermaid
sequenceDiagram
    participant Empresa
    participant WAHA
    participant BotService
    participant CompanyAuthService

    Empresa->>WAHA: "empresa"
    WAHA->>BotService: process_message(chat_id, "empresa")
    BotService->>BotService: _start_company_onboarding()
    Note over BotService: company != None → reauth automático
    BotService->>CompanyAuthService: reauth_company(phone)
    BotService->>MenuHandler: send_menu()
    MenuHandler-->>Empresa: Menu Empresa direto (sem e-mail)
```

### Menu Empresa (opções)

| Opção | Ação |
|-------|------|
| 1 | Ver vagas cadastradas (leitura — `Job.objects.filter(company=...)`) |
| 2 | Link portal da empresa (`/empresas/perfil/`) |
| 3 | Link para cadastrar nova vaga (`/empresas/vagas/nova/`) |
| 0 | Sair da conta empresa (`is_company_authenticated=False`) |

### Switch entre modos (aluno + empresa no mesmo número)

- Usuário com ambas as contas autenticadas: empresa tem prioridade no menu.
- Digitar `aluno` → `_handle_switch_to_student()` → desloga empresa temporariamente → mostra menu aluno.
- Digitar `empresa` em modo aluno → re-autentica empresa → mostra menu empresa.
- Opção `5` no menu aluno aparece quando `user.company is not None`.

### Passos (primeiro login)

1. "empresa" → `_start_company_onboarding()` verifica `is_company_authenticated` e `company` — `apps/bot/services.py`
2. Se não vinculado: `STATE_COMPANY_ONBOARDING_SELECTION` → exibe opções — `apps/bot/handlers/menu.py:send_company_onboarding_menu()`
3. "2" (já tenho conta) → `CompanyAuthHandler.start_company_login_flow()` — `apps/bot/handlers/company_auth.py:L33`; avança para `STATE_COMPANY_LOGIN_EMAIL`
4. Empresa digita e-mail → `handle_company_login_email()` chama `CompanyAuthService.link_company_by_email()` — `apps/companies/company_auth_service.py:L17`
5. Token gerado → `UserProfile.company` setado (pending) + `company_confirmation_token` gerado
6. Email enviado via `dispatch_company_confirmation_email()` → task Celery `send_company_confirmation_email` — `apps/bot/tasks.py`
7. Estado avança para `STATE_COMPANY_WAITING_CONFIRMATION`
8. Empresa clica link `/confirmar-empresa/<token>/` → `ConfirmCompanyEmailView` → `CompanyAuthService.confirm_company_email()` seta `is_company_authenticated=True` — `apps/users/views.py`
9. Próxima mensagem → `send_menu()` detecta `is_company_authenticated=True` → menu empresa

---

## 7. Task de Pré-fetching Diário de Vagas

Executada todos os dias às 07:00 (horário de Brasília). Popula a tabela `DailyJob` para consulta sub-segundo pelo bot.

### Diagrama

```mermaid
sequenceDiagram
    participant CeleryBeat as Celery Beat (diário, 07:00 BRT)
    participant Task as fetch_daily_jobs task
    participant Service as fetch_and_save_daily_jobs()
    participant DB as Banco de Dados
    participant JobSpy as JobSearchService (python-jobspy)

    CeleryBeat->>Task: Dispara fetch_daily_jobs (todo dia, 07:00 BRT)
    Task->>Service: fetch_and_save_daily_jobs(job_searcher=searcher)
    Service->>DB: SearchTerm.objects.filter(is_default=True).select_related("course")
    DB-->>Service: Lista de termos ativos

    loop Para cada SearchTerm
        Service->>JobSpy: job_searcher.search(terms=[term.term], **kwargs)
        JobSpy-->>Service: Lista de vagas brutas
        Service->>DB: DailyJob.objects.bulk_create(to_create, ignore_conflicts=True)
        Service->>DB: JobSearchLog.objects.create(user=None, ...)
    end

    Service->>DB: DailyJob.objects.filter(fetched_date__lt=hoje-7dias).delete()
    Service-->>Task: stats = {terms_processed, jobs_saved, jobs_skipped, errors}
```

### Passos

1. Celery Beat dispara `fetch_daily_jobs` todo dia às 07:00 BRT — `waha_bot/settings/celery.py:L29` (`crontab(hour=7, minute=0)`)
2. Task thin instancia `JobSearchService` e delega para `fetch_and_save_daily_jobs()` — `apps/jobs/tasks.py:L26`
3. `fetch_and_save_daily_jobs()` busca todos os `SearchTerm.objects.filter(is_default=True)` com `select_related("course")` — `apps/jobs/services.py:L145`
4. Para cada termo: chama `job_searcher.search()` usando `term.to_search_kwargs()` como configuração (LinkedIn, Indeed, Glassdoor via jobspy; Adzuna via API) — `apps/jobs/services.py:L154`
5. Resultados salvos via `DailyJob.objects.bulk_create(to_create, ignore_conflicts=True)` — idempotente por `unique_together` — `apps/jobs/services.py:L171`
6. Apenas resultados com URL válida são persistidos: `if r.get("job_url") or r.get("job_url_direct")` — `apps/jobs/services.py:L168`
7. Vagas com mais de 7 dias são deletadas automaticamente — `apps/jobs/services.py:L193`
8. Task tem `max_retries=3` e `default_retry_delay=300s` para resiliência — `apps/jobs/tasks.py:L26`
