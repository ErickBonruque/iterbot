# Plano de Implementação — Sistema de Vagas & Candidaturas

> **Documento vivo e autossuficiente.** Foi escrito para ser entregue a uma IA (ou pessoa)
> que **não participou do planejamento original**. Ele descreve o objetivo, o estado atual do
> código, as decisões de arquitetura já tomadas, e cada fase com checklist, boas práticas e
> critérios de aceite. À medida que o trabalho avança, **a IA deve atualizar este mesmo arquivo**
> (marcar checkboxes, mudar status, preencher o "Registro de Progresso") para que outro chat
> consiga continuar de onde parou.

---

## 📌 Como usar este documento (LEIA PRIMEIRO — instruções para a IA)

1. **Descubra o estado atual antes de codar.** Não confie cegamente nos checkboxes — eles podem
   estar desatualizados. Para cada item que parece feito, **confirme no código** (procure o
   model/campo/migração/handler citado). Os checkboxes são um guia, o código é a verdade.
2. **Trabalhe uma fase por vez, na ordem de dependência** (ver seção _Ordem e Dependências_).
   Não comece uma fase cujos pré-requisitos não estão concluídos.
3. **Ao concluir cada item**, marque `- [x]`. Ao concluir uma fase inteira, atualize o
   **Painel de Status** no topo e escreva uma entrada no **Registro de Progresso** (data, o que
   foi feito, arquivos tocados, migrações criadas, decisões/desvios).
4. **Toda fase precisa de testes** (o projeto usa pytest — ver `apps/*/tests/`). Não marque uma
   fase como concluída sem testes verdes para ela.
5. **Padrões obrigatórios do projeto** (ver `CLAUDE.md`): Ruff (lint+format), structlog (logging
   JSON, nunca logar dados sensíveis), Conventional Commits (`cz commit`), `EncryptedCharField`
   para dados sensíveis, handlers do bot via `BaseHandler`, mensagens centralizadas em
   `apps/bot/messages.py`. **Sempre responder/documentar em português.**
6. **Migrações:** todo campo novo em model existente entra como nullable/`blank`/com default e,
   quando preciso, com _data migration_ de backfill — nunca quebre dados em produção.
7. Ao final de cada fase rode: `make lint`, `make dev-test` (ou `pytest`), e confira que as
   migrações aplicam limpo (`make migrate`).

---

## 🗂️ Painel de Status

| Fase | Título | Status | Concluída em |
|------|--------|--------|--------------|
| 0 | Fundação: model `Area` | ✅ Concluída | 2026-06-13 |
| 1 | Empresa escolhe a área da vaga | ✅ Concluída | 2026-06-13 |
| 2 | Resumo semanal só local + caso vazio | ✅ Concluída | 2026-06-13 |
| 3 | Menu do aluno: "Vagas do meu curso" | ✅ Concluída | 2026-06-14 |
| 4 | Candidatura com mini-perfil | ✅ Concluída | 2026-06-14 |
| 5 | Busca online: jobspy + ranking + Adzuna | ⬜ Não iniciada | — |
| 6 | Admin de SearchTerm intuitivo/traduzido | ⬜ Não iniciada | — |

**Legenda:** ⬜ Não iniciada · 🟡 Em andamento · ✅ Concluída · ⏸️ Bloqueada

---

## 🎯 Objetivo geral

Evoluir o sistema de vagas do IterBot (bot WhatsApp para estudantes da UTFPR) para:

- Entregar **resumo semanal só de vagas locais**, cobrindo o caso de não haver nenhuma cadastrada.
- Permitir que o aluno veja, pelo menu, **as vagas locais da área do seu curso**.
- Permitir que a **empresa direcione a vaga por área** no cadastro.
- Oferecer um **sistema de candidatura** com **mini-perfil do aluno** coletado no bot.
- Melhorar a **busca de vagas online** (jobspy afinado + ranking de relevância + Adzuna).
- Tornar o **cadastro de termos de busca no Django Admin** intuitivo e 100% em português.

---

## 🧭 Decisões de arquitetura (travadas)

Estas decisões foram tomadas com o requisitante e **não devem ser revertidas sem confirmação**:

1. **Agrupamento por ÁREA, não por curso.** Cria-se o conceito `Area` (ex.: TI, Engenharias,
   Gestão, Saúde). Cada `Course` pertence a 1 área; cada `Job` oferta para 1+ áreas (vazio = todas).
   Vaga "do meu curso" = vaga cuja área bate com a área do curso do aluno. Some a gambiarra atual
   de match por palavra-chave.
2. **Candidatura com mini-perfil do aluno no bot.** Além de registrar interesse, o aluno preenche
   um mini-perfil (período, skills, LinkedIn/CV) reutilizável, que acompanha a candidatura. Empresa
   é notificada por e-mail e vê no portal.
3. **Busca online = jobspy afinado + ranking + Adzuna.** Adicionar site `google` do jobspy,
   ranking de relevância (substituindo o dedup puro) e a API Adzuna como fonte complementar.

---

## 🔍 Diagnóstico do estado atual (baseline — antes da Fase 0)

Levantado em **2026-06-13**. Confirme se ainda vale antes de codar.

- **Resumo semanal** (`send_weekly_reviews`, `apps/jobs/services.py:232`): roda seg. 08:00
  (`waha_bot/settings/celery.py:22`). Hoje **mistura vagas locais + online (jobspy ao vivo)** via
  `build_review_for_user` (`apps/jobs/services.py:125`). **Caso vazio NÃO tratado**: se não há vaga,
  faz `continue` e o aluno **não recebe nada** (`apps/jobs/services.py:255`).
- **Vaga ↔ Curso/Área NÃO existe.** `Job` (`apps/jobs/models/job.py:16`) não tem campo de curso nem
  área. `JobForm` (`apps/companies/forms.py:176`) só tem titulo/descricao/requisitos/salario/tipo.
  O match local hoje é por `titulo__icontains`/`descricao__icontains` (`apps/jobs/services.py:34`).
- **Menu do aluno** (`apps/bot/messages.py:88`): 1=Buscar Vagas, 2=Ver Review, 3=Sair, 4=Trocar
  Curso, 5=Empresa. **Não há** opção de "vagas locais do meu curso". Roteamento em
  `apps/bot/services.py:257` (`_handle_numeric_authenticated`).
- **Candidatura:** model `JobApplication` **existe** (`apps/jobs/models/job_application.py`) com
  unique `(user, job)`, mas **não é usado em nenhum fluxo do bot** — só tem admin de leitura
  (`apps/jobs/admin/job_application.py`). Esqueleto pronto para construir.
- **JobSpy** (`infra/jobspy/service.py`): python-jobspy 1.1.0, sites linkedin/indeed/glassdoor,
  timeout 30s/termo via `ThreadPoolExecutor`. **Não usa site `google`**, sem ranking (só dedup por
  título+empresa em `apps/jobs/services.py:111`). `DailyJob` (`apps/jobs/models/daily_job.py`) é
  pré-buscado diariamente às 07:00 (`fetch_daily_jobs`), TTL 7 dias.
- **Admin SearchTerm** (`apps/courses/admin.py:38`): `help_text` em PT, mas **labels mostram o nome
  cru do campo** (`site_name`, `hours_old`, `country_indeed`...) e **sem tooltip no hover**.
  `SearchTerm` em `apps/courses/models.py:38`.
- **UserProfile.course** existe (`apps/users/models.py:52`, FK → `courses.Course`).

---

## 🧱 Ordem e Dependências

```
Fase 0 (Area) ─┬─> Fase 1 (vaga↔área) ─┬─> Fase 2 (resumo semanal)
               │                        └─> Fase 3 (menu aluno) ──> Fase 4 (candidatura)
               └─> Fase 6 (admin) [independente — pode ir a qualquer momento]
Fase 5 (busca online) [independente das demais — pode paralelizar]
```

**Caminho recomendado:** 0 → 1 → 2 → 3 → 4. Fases 5 e 6 podem ser feitas em paralelo/intercaladas.
Cada fase é **shippável sozinha** com testes verdes.

---

# Fases

## Fase 0 — Fundação: model `Area`

**Status:** ✅ Concluída
**Pré-requisitos:** nenhum.
**Objetivo:** introduzir o conceito de Área e ligá-lo aos cursos, sem quebrar nada existente.

### Checklist
- [x] Criar `class Area(TimeStampedModel)` em `apps/courses/models.py` com campos:
  - [x] `name` (CharField, único, verbose_name "Nome da área")
  - [x] `code` (slug curto, opcional)
  - [x] `description` (TextField, blank)
  - [x] `icon` (CharField curto p/ emoji usado no menu do bot, blank)
  - [x] `is_active` (Boolean, default True)
  - [x] `order` (Integer, default 0)
  - [x] `Meta`: `ordering = ["order", "name"]`, verbose_name "Área", verbose_name_plural "Áreas"
- [x] Adicionar `Course.area = ForeignKey(Area, null=True, blank=True, related_name="courses", on_delete=models.SET_NULL)`
- [x] Criar migração de schema (`0003_area_course_area.py`)
- [x] Criar **data migration** (`0004_seed_areas.py`) que cria as áreas iniciais (Tecnologia da
      Informação, Engenharias, Gestão e Negócios, Saúde, Ciências Agrárias e Biológicas, Outras) e
      associa cada `Course` existente à sua área (map por nome/código; sem match → `null`; reversível)
- [x] Registrar `AreaAdmin` (Unfold `ModelAdmin`) com `list_display`, `list_editable` de `order`,
      `search_fields`
- [x] Adicionar `area` ao `CourseAdmin` (`list_display`, `list_filter`, fieldset, `autocomplete_fields`)
- [x] Testes: criação de Area, associação Course→Area, data migration produz áreas esperadas

### Boas práticas
- `Course.area` **nullable** para a migração não falhar com dados existentes; backfill via data
  migration idempotente.
- Não usar `unique` em `code` se puder vir vazio em vários registros — prefira `null=True` + unique
  condicional, ou deixe sem unique.
- Emoji em `icon` é opcional e meramente cosmético para o menu do bot (Fase 3).

### Critérios de aceite
- `python manage.py migrate` aplica limpo num banco com cursos pré-existentes.
- Admin lista Áreas e permite editar a área de cada curso.
- Todo curso de produção tem área atribuída (ou consciente `null` documentado).

### Arquivos afetados
`apps/courses/models.py`, `apps/courses/admin.py`, `apps/courses/migrations/*`,
`apps/courses/tests/` (criar se não existir).

### Registro de Progresso
> **2026-06-13 — Fase 0 concluída**
> - **O que foi feito:** criado o model `Area` (name único, code slug opcional, description, icon,
>   is_active, order) e a FK `Course.area` (nullable, `on_delete=SET_NULL`). Registrado `AreaAdmin`
>   (com `list_editable=["order"]` e `search_fields`) e adicionado `area` ao `CourseAdmin`
>   (`list_display`, `list_filter`, fieldset, `autocomplete_fields`).
> - **Arquivos tocados:** `apps/courses/models.py`, `apps/courses/admin.py`,
>   `apps/courses/tests/test_area.py` (novo).
> - **Migrações:** `0003_area_course_area.py` (schema) e `0004_seed_areas.py` (data migration
>   reversível: cria 6 áreas iniciais + backfill por nome/código do curso). Aplicam limpo.
> - **Testes:** 7 novos em `test_area.py` (verdes). Suite `apps/courses` completa: 38 passou.
> - **Decisões/desvios:** adicionada a área "Ciências Agrárias e Biológicas" (além das do plano)
>   porque os cursos atuais incluem Agronomia e Ciências Biológicas. `icon` ficou com `max_length=10`
>   para acomodar emojis multi-byte. `code` como `SlugField` (não unique — pode ser null em vários).
> - **Pendências/próximos passos:** Fase 1 (vaga ↔ área). A convenção "areas vazio = todas" será
>   centralizada num helper na Fase 1 conforme o plano.

---

## Fase 1 — Empresa escolhe a área da vaga

**Status:** ✅ Concluída
**Pré-requisitos:** Fase 0.
**Objetivo:** permitir que a empresa direcione cada vaga para uma ou mais áreas no cadastro.

### Checklist
- [x] Adicionar `Job.areas = ManyToManyField(Area, blank=True, related_name="jobs")` em
      `apps/jobs/models/job.py` com `help_text` "Áreas para as quais a vaga é ofertada. Vazio = todas."
- [x] Migração (`0008_job_areas.py`; M2M não exige backfill — vagas antigas = "todas" por convenção)
- [x] `JobForm` (`apps/companies/forms.py`): `areas` como `ModelMultipleChoiceField`
      (`CheckboxSelectMultiple`), label "Áreas de interesse", `required=False`, queryset só áreas ativas
- [x] Renderizar `areas` no template do portal (`templates/companies/job_form.html`)
- [x] `JobAdmin` (`apps/jobs/admin/job.py`): `areas` no fieldset + `filter_horizontal = ("areas",)`
      + `list_filter` por área
- [x] Garantir que o `save` da view persiste o M2M — confirmado por teste de integração
      (`TestJobCreateView::test_create_job_persists_areas_m2m`)
- [x] Testes: criar vaga com 1 área, com várias, sem nenhuma (= todas); form valida; view salva M2M

### Helper centralizado (convenção "vazio = todas")
Criado `JobQuerySet.for_area(area)` em `apps/jobs/models/job.py` (`Job.objects.for_area(area)`):
retorna vagas que incluem `area` **ou** que não têm nenhuma área. `for_area(None)` retorna só as
vagas "para todas". Fases 2 e 3 **devem** reutilizar este helper (não reimplementar a regra).

### Boas práticas
- **Convenção do vazio = todas** deve ser documentada e centralizada num helper (ex.:
  `Job.objects.for_area(area)`), para a Fase 2/3 não reimplementarem a regra.
- M2M exige `form.save_m2m()` se você salvar `instance` com `commit=False`; com CBV padrão isso é
  automático — confirme com teste.
- Não tornar `areas` obrigatório (a empresa pode não saber a área → cai em "todas").

### Critérios de aceite
- Empresa consegue, pelo portal, marcar áreas ao criar/editar vaga.
- Vaga sem área marcada é tratada como "todas as áreas" pelas queries de filtragem.

### Arquivos afetados
`apps/jobs/models/job.py`, `apps/jobs/migrations/*`, `apps/companies/forms.py`,
`apps/companies/views.py`, `apps/jobs/admin/job.py`, `templates/companies/job_form.html`,
testes em `apps/companies/tests/` e `apps/jobs/tests/`.

### Registro de Progresso
> **2026-06-13 — Fase 1 concluída**
> - **O que foi feito:** M2M `Job.areas` (`blank=True`, `related_name="jobs"`); `JobQuerySet.for_area`
>   centralizando a regra "vazio = todas"; `areas` no `JobForm` (checkboxes, só áreas ativas) e no
>   template do portal; `JobAdmin` com `filter_horizontal` + `list_filter` por área.
> - **Arquivos tocados:** `apps/jobs/models/job.py`, `apps/companies/forms.py`,
>   `templates/companies/job_form.html`, `apps/jobs/admin/job.py`,
>   `apps/jobs/tests/test_job_areas.py` (novo), `apps/companies/tests/test_forms.py`,
>   `apps/companies/tests/test_views.py`.
> - **Migrações:** `0008_job_areas.py` (M2M, sem backfill). Aplica limpo.
> - **Testes:** 6 em `test_job_areas.py` (helper `for_area`) + 3 de form + 1 de view (persistência
>   M2M) — todos verdes. Suite `apps/jobs` + `apps/companies`: 102 passou. As 2 falhas restantes
>   (`TestCompanySignupEmailContext`) são ambientais (Celery→Redis indisponível no ambiente local),
>   não relacionadas a esta fase. `make lint` limpo.
> - **Decisões/desvios:** `JobForm.areas.queryset` filtra `is_active=True` (não oferecer áreas
>   desativadas no portal). FK do M2M referenciada como string `"courses.Area"` para evitar import
>   circular.
> - **Pendências/próximos passos:** Fase 2 (resumo semanal só local) reutiliza `Job.objects.for_area`.

---

## Fase 2 — Resumo semanal só local + caso vazio coberto

**Status:** ✅ Concluída
**Pré-requisitos:** Fase 0, Fase 1.
**Objetivo:** resumo semanal passa a conter **apenas vagas locais** filtradas pela área do curso do
aluno, e **sempre envia algo** — inclusive quando não há vagas.

### Checklist
- [x] Criar helper `get_local_jobs_for_area(area, limit=5)` em `apps/jobs/services.py`: reutiliza
      `Job.objects.for_area(area)` (Fase 1) + `status=APPROVED`, ordenado por `-created_at`
- [x] Criar `build_weekly_local_review(course)` que usa `course.area` e **não chama jobspy**
- [x] Ajustar `send_weekly_reviews`:
  - [x] usar a review **só local** (`build_weekly_local_review`)
  - [x] quando **vazio**, enviar mensagem amigável (`weekly_no_local_jobs`) em vez de `continue`
  - [x] remover a chamada ao jobspy do caminho semanal (param `job_searcher` removido da assinatura
        e da task wrapper `send_weekly_job_review`)
- [x] Adicionar mensagens em `apps/bot/messages.py` (`ReviewMessages`):
  - [x] `weekly_no_local_jobs`
  - [x] `weekly_local_header` / `weekly_local_summary` (variantes "vagas locais") — ver desvio abaixo
- [x] Criar `format_weekly_local_review_message` (variante só-local; `format_review_message` mantida
      intacta para o review sob demanda local+online)
- [x] Renomear a stat `no_jobs` → `empty_notice` (agora envia aviso, não é mais skip)
- [x] Testes: usuário com vagas locais recebe lista; sem vagas recebe aviso; jobspy não é chamado
      no caminho semanal (asserção `search_with_config.assert_not_called`)

> **Desvio do plano:** o plano sugeria reescrever `weekly_header`/`weekly_summary`. Mas essas
> mensagens são **compartilhadas** com o review sob demanda (`JobReviewHandler` →
> `format_review_message`), que continua local+online. Para não mudar a semântica do on-demand, criei
> templates dedicados `weekly_local_header`/`weekly_local_summary` + `format_weekly_local_review_message`,
> deixando os antigos intactos. Os 3 novos templates foram registrados em `BotMessage.KEY_CHOICES`.

### Boas práticas
- Manter `send_weekly_reviews` com **injeção de dependência** (já recebe `message_sender`); nos
  testes, injete fakes (não bata em WAHA/jobspy de verdade).
- `interval_seconds` entre envios continua válido para não floodar o WAHA.
- Logar com structlog: `weekly_review_sent` / `weekly_review_empty_notice` com `user_id` e `area`.

### Critérios de aceite
- Resumo semanal não contém nenhuma vaga online (jobspy não é chamado).
- Aluno sem vagas locais **recebe** a mensagem amigável (não fica sem resposta).
- Performance do envio melhora (sem scraping ao vivo no loop).

### Arquivos afetados
`apps/jobs/services.py`, `apps/bot/messages.py`, `apps/jobs/tests/test_services.py`,
`apps/jobs/tests/test_tasks.py`.

### Registro de Progresso
> **2026-06-13 — Fase 2 concluída**
> - **O que foi feito:** caminho semanal agora é **local-only** e **sempre envia algo**. Helpers
>   `get_local_jobs_for_area` e `build_weekly_local_review` (reusam `Job.objects.for_area`);
>   `send_weekly_reviews` reescrita (stats `sent`/`empty_notice`/`errors`), `job_searcher` removido;
>   task wrapper não constrói mais `JobSearchService`. Extraído `_serialize_local_job` e
>   `_format_job_lines` para reduzir duplicação. Novos templates de mensagem + variante
>   `format_weekly_local_review_message`.
> - **Arquivos tocados:** `apps/jobs/services.py`, `apps/jobs/tasks.py`, `apps/bot/messages.py`,
>   `apps/bot/models/bot_message.py`, `apps/jobs/tests/test_services.py`,
>   `apps/jobs/tests/test_tasks.py`.
> - **Migrações:** nenhuma (mudança só de serviço/mensagens).
> - **Testes:** 5 novos em `test_services.py` (helpers de área + formatter) + tasks atualizados
>   (inclui asserção de que jobspy não é chamado). `apps/jobs` + `test_messages`: 70 passou.
>   `make lint` limpo.
> - **Decisões/desvios:** ver bloco "Desvio do plano" acima (templates locais dedicados em vez de
>   mutar os compartilhados). Stat `no_jobs` renomeada para `empty_notice`.
> - **Pendências/próximos passos:** Fase 3 (menu do aluno "Vagas do meu curso") — reutiliza
>   `get_local_jobs_for_area`/`Job.objects.for_area`.

---

## Fase 3 — Menu do aluno: "Vagas do meu curso"

**Status:** ✅ Concluída
**Pré-requisitos:** Fase 0, Fase 1. (Independe da Fase 2.)
**Objetivo:** nova opção de menu que lista as vagas locais da **área do curso do aluno**, com
navegação para o detalhe da vaga (porta de entrada da candidatura na Fase 4).

### Checklist
- [x] Atualizar menu autenticado em `apps/bot/messages.py` (`menu.main_authenticated`) incluindo a
      nova opção e **renumerando** com cuidado. Implementado:
      `1 Buscar Vagas · 2 Ver Review · 3 Vagas do meu curso · 4 Sair · 5 Trocar Curso · 6 Empresa`
- [x] Criar handler (novo `LocalJobsHandler` em `apps/bot/handlers/local_jobs.py`) que:
  - [x] exige autenticação (`is_authenticated_utfpr`) — segue o gate de `JobReviewHandler`
  - [x] resolve a área do curso do aluno (`user.course.area`); trata curso/área ausente
  - [x] lista `Job` aprovadas da área (via `get_local_jobs_queryset_for_area`, que reusa
        `Job.objects.for_area`), numeradas
  - [x] abre o **detalhe** da vaga ao receber o número (título, empresa, descrição, requisitos,
        salário, tipo) + instrução "Digite *candidatar* para se candidatar". `candidatar` responde
        com stub "em breve" (a candidatura completa é a Fase 4)
- [x] Adicionar estados em `apps/bot/state_machine.py` (`STATE_LOCAL_JOBS_LIST`,
      `STATE_LOCAL_JOB_DETAIL`), rota `ROUTE_LOCAL_JOBS`/`LOCAL_JOBS_ROUTE_STATES` e transições na
      `ConversationFlowStateMachine`
- [x] Registrar o handler em `apps/bot/services.py` (`BotService.__init__`), rotear a opção `3`
      em `_handle_numeric_authenticated` (renumerando 4=Sair, 5=Trocar Curso, 6=Empresa), adicionar
      `_ALIAS_LOCAL_JOBS` ("minhas vagas", "vagas do curso", "vagas do meu curso") em
      `_handle_text_alias` e o `handle()` em `_handle_pending_action`
- [x] Mensagens novas em `apps/bot/messages.py` (`LocalJobsMessages`: sem curso, lista, vazio,
      seleção inválida, vaga indisponível, detalhe, candidatura em breve) + chaves em
      `BotMessage.KEY_CHOICES`
- [x] Testes: aluno autenticado vê vagas da sua área; área sem vagas → mensagem adequada; aluno sem
      curso → orientação; números inválidos tratados; vaga de outra área excluída; vaga sem área =
      todas; detalhe; stub de candidatura; `menu` escapa o fluxo

### Boas práticas
- **Renumeração de menu é arriscada:** revise todos os `_handle_numeric_*` em
  `apps/bot/services.py` e os testes de menu (`apps/bot/tests/test_menu_handler.py`) para os números
  baterem com a nova ordem. Considere manter aliases de texto para reduzir dependência do número.
- Reusar o helper de query da Fase 2 (não duplicar a regra "vazio = todas").
- Mensagens **sempre** via `apps/bot/messages.py` + `resolve_message` (permite override via
  `BotMessage` no admin).

### Critérios de aceite
- Aluno consegue, pelo menu, ver e abrir vagas locais da área do seu curso.
- Fluxo encadeia para a candidatura (Fase 4) sem retrabalho.

### Arquivos afetados
`apps/bot/messages.py`, `apps/bot/handlers/` (novo), `apps/bot/handlers/__init__.py`,
`apps/bot/state_machine.py`, `apps/bot/services.py`, `apps/bot/tests/`.

### Registro de Progresso
> **2026-06-14 — Fase 3 concluída**
> - **O que foi feito:** nova opção de menu *3 — Vagas do meu curso*. `LocalJobsHandler`
>   (`apps/bot/handlers/local_jobs.py`) lista vagas locais aprovadas da **área do curso do aluno**
>   (`user.course.area`), numeradas, e abre o detalhe (título, empresa, salário, tipo, descrição,
>   requisitos). Comando `candidatar` no detalhe responde com stub "em breve" (Fase 4). Estados
>   `STATE_LOCAL_JOBS_LIST`/`STATE_LOCAL_JOB_DETAIL` + rota `ROUTE_LOCAL_JOBS`; IDs das vagas
>   listadas guardados em `flow_data["local_job_ids"]` para o detalhe. Menu renumerado
>   (4=Sair, 5=Trocar Curso, 6=Empresa) com `switch_empresa` ajustado para 6️⃣. Alias de texto
>   `_ALIAS_LOCAL_JOBS`. Comandos globais (`menu`/`cancelar`/`voltar`/`sair`) continuam escapando o
>   fluxo (são tratados antes do `_handle_pending_action`).
> - **Arquivos tocados:** `apps/bot/handlers/local_jobs.py` (novo),
>   `apps/bot/handlers/__init__.py`, `apps/bot/state_machine.py`, `apps/bot/services.py`,
>   `apps/bot/messages.py`, `apps/bot/models/bot_message.py`, `apps/bot/handlers/menu.py`,
>   `apps/jobs/services.py` (helper `get_local_jobs_queryset_for_area`),
>   `apps/bot/tests/test_local_jobs_handler.py` (novo), `apps/bot/tests/test_bot_service.py` e
>   `apps/bot/tests/test_state_machine.py` (ajustes da renumeração/contrato de estados).
> - **Migrações:** `apps/bot/migrations/0007_alter_botmessage_key.py` (apenas `choices` de
>   `BotMessage.key` — captura também drift pré-existente das chaves pontuadas/Fase 2; no-op no
>   banco). Aplica limpo; `makemigrations --check` sem pendências.
> - **Testes:** 12 novos em `test_local_jobs_handler.py` (verdes). Suite `apps/bot`+`apps/jobs`+
>   `apps/courses`: 305 passou, cobertura 72.32% (acima do gate de 70%). `ruff check apps/` limpo.
> - **Decisões/desvios:** (1) a área vem de `user.course.area` (curso preferido persistente), como
>   o plano pede, e não de `conversation_state.selected_course`. (2) Em vez de reusar
>   `get_local_jobs_for_area` (que serializa dicts sem descrição/requisitos), criei
>   `get_local_jobs_queryset_for_area` em `apps/jobs/services.py` — fonte única do queryset que
>   ainda reusa `Job.objects.for_area` (regra "vazio = todas" não duplicada); `get_local_jobs_for_area`
>   foi refatorada para chamá-la. (3) `candidatar` é stub até a Fase 4.
> - **Pendências/próximos passos:** Fase 4 (candidatura com mini-perfil) liga-se ao detalhe da vaga
>   já implementado — substituir o stub `apply_coming_soon` pelo fluxo real.

---

## Fase 4 — Candidatura com mini-perfil

**Status:** ✅ Concluída
**Pré-requisitos:** Fase 3.
**Objetivo:** ciclo completo de candidatura — aluno preenche mini-perfil (reutilizável), candidata-se
a uma vaga local, empresa é notificada e acompanha pelo portal.

### Checklist — Models
- [x] Mini-perfil do aluno: criado `StudentProfile(OneToOne→UserProfile)` em `apps/users/models.py`.
      Campos:
  - [x] `periodo` (CharField — semestre atual)
  - [x] `skills` (TextField)
  - [x] `linkedin_url` (URLField, blank)
  - [x] `cv_url` (URLField, blank — link; upload de arquivo via WhatsApp fica para versão futura)
  - [x] `bio` (TextField, blank — não coletado no bot ainda; reservado p/ futuro)
- [x] Estender `JobApplication` (`apps/jobs/models/job_application.py`):
  - [x] `status` (TextChoices `ApplicationStatus`: `pending`/`vista`/`contatado`/`rejeitada`, default `pending`)
  - [x] `message` (TextField, blank — recado opcional do aluno)
  - [x] `profile_snapshot` (JSONField — congela o perfil no momento da candidatura, p/ histórico)
- [x] Migrações (`users/0008_studentprofile`, `jobs/0009_jobapplication_message_and_more`;
      campos novos com default, sem quebrar dados)

### Checklist — Fluxo no bot
- [x] Estados novos em `apps/bot/state_machine.py`: coleta de perfil
      (`STATE_PROFILE_PERIODO` → `STATE_PROFILE_SKILLS` → `STATE_PROFILE_LINK`) e
      `STATE_CONFIRM_APPLICATION` (+ rota `ROUTE_APPLICATION` e transições na state machine)
- [x] No detalhe da vaga (Fase 3), comando "candidatar" (encadeado via `LocalJobsHandler`):
  - [x] se aluno **já tem** mini-perfil completo → pula coleta, vai direto à confirmação
  - [x] se **não tem** → coleta passo a passo, valida (URL no link, "pular" opcional) e salva no perfil
- [x] Criar `JobApplication` (respeitando o unique `(user, job)`; duplicata → "você já se candidatou";
      `IntegrityError` em corrida também tratado)
- [x] Gravar `profile_snapshot` no momento da candidatura (via `StudentProfile.to_snapshot()`)
- [x] Confirmar para o aluno (mensagem de sucesso)
- [x] Mensagens novas em `apps/bot/messages.py` (`ApplicationMessages`) + chaves em `BotMessage.KEY_CHOICES`

### Checklist — Notificação e portal da empresa
- [x] Enviar **e-mail** à empresa em nova candidatura, via `infra/email` (reusa
      `send_transactional_email`). Conteúdo: vaga, dados do aluno (RA, e-mail, telefone), mini-perfil, recado.
  - [x] idempotência por candidatura (`build_email_idempotency_key` com o id da `JobApplication`)
  - [x] dispatch assíncrono via task Celery `send_job_application_email`; falha de broker **não**
        derruba o fluxo (candidatura ainda é criada — degradação graciosa)
- [x] Página no portal (`apps/companies/`) "Candidaturas" (`JobApplicationsListView`): lista as
      candidaturas das vagas da empresa, mostra mini-perfil e permite mudar `status`
      (`JobApplicationStatusUpdateView`). Protegidas por `ApprovedCompanyRequiredMixin` + checagem de posse.
- [x] Atualizar `JobApplicationAdmin` com `status` (list_display/list_filter/list_editable),
      `profile_snapshot` readonly e ações "Marcar como Vista/Contatado"
- [x] Testes: coleta completa e salva; reuso de perfil; criação de candidatura; bloqueio de duplicata;
      link inválido/pular; cancelar aborta; e-mail disparado (mock) + falha de broker não quebra;
      portal lista/filtra por empresa e muda status (com bloqueio de empresa alheia → 403)

### Boas práticas
- **Não logar dados pessoais** do aluno em texto (structlog: usar IDs, não conteúdo). Atenção à LGPD.
- Se algum dado for sensível, considerar `EncryptedCharField` (padrão do projeto).
- E-mail à empresa deve degradar graciosamente: se o envio falhar, a candidatura **ainda é criada**
  (a empresa vê no portal). Logar a falha, não derrubar o fluxo do bot.
- Coleta de perfil: validar entradas (URL de LinkedIn/CV), permitir "pular" campos opcionais e
  "cancelar" (o bot já trata `cancelar`/`voltar` em `apps/bot/services.py:140`).
- `profile_snapshot` evita que edição futura do perfil reescreva o histórico da candidatura.

### Critérios de aceite
- Aluno se candidata a uma vaga local e recebe confirmação.
- Mini-perfil é coletado uma vez e reutilizado nas próximas candidaturas.
- Empresa recebe e-mail e enxerga a candidatura + perfil no portal, podendo mudar o status.
- Candidatura duplicada é bloqueada com mensagem clara.

### Arquivos afetados
`apps/users/models.py` (ou novo `StudentProfile`), `apps/jobs/models/job_application.py`,
`apps/bot/state_machine.py`, `apps/bot/handlers/`, `apps/bot/services.py`, `apps/bot/messages.py`,
`apps/companies/views.py` + `urls.py` + templates, `apps/jobs/admin/job_application.py`,
`infra/email/*` (uso), migrações, testes em `apps/bot/`, `apps/companies/`, `apps/jobs/`.

### Registro de Progresso
> **2026-06-14 — Fase 4 concluída**
> - **O que foi feito:** ciclo completo de candidatura. Model `StudentProfile` (OneToOne→UserProfile,
>   `is_complete`/`to_snapshot`); `JobApplication` ganhou `status` (`ApplicationStatus`), `message` e
>   `profile_snapshot`. Novo `ApplicationHandler` (`apps/bot/handlers/application.py`): a partir do
>   detalhe da vaga (Fase 3), `candidatar` inicia a coleta período→skills→link (ou pula se o perfil já
>   está completo), valida o link (URL ou "pular"), mostra resumo, e ao "confirmar" cria a
>   `JobApplication` com snapshot e notifica a empresa por e-mail. Estados `STATE_PROFILE_*`/
>   `STATE_CONFIRM_APPLICATION` + rota `ROUTE_APPLICATION`. E-mail via `send_job_application_email_to_company`
>   (reusa `send_transactional_email` + idempotência por candidatura), disparado pela task Celery
>   `send_job_application_email` com try/except no dispatch (broker fora do ar não derruba a candidatura).
>   Portal: `JobApplicationsListView`/`JobApplicationStatusUpdateView` + template `applications.html` +
>   link na navbar; `JobApplicationAdmin` com status/filtros/ações.
> - **Arquivos tocados:** `apps/users/models.py`, `apps/jobs/models/job_application.py`,
>   `apps/jobs/models/__init__.py`, `apps/bot/state_machine.py`, `apps/bot/messages.py`,
>   `apps/bot/models/bot_message.py`, `apps/bot/handlers/application.py` (novo),
>   `apps/bot/handlers/local_jobs.py`, `apps/bot/handlers/__init__.py`, `apps/bot/services.py`,
>   `apps/bot/email_service.py`, `apps/bot/tasks.py`, `apps/companies/services.py`,
>   `apps/companies/views.py`, `apps/companies/urls.py`, `apps/jobs/admin/job_application.py`,
>   `templates/companies/applications.html` (novo), `templates/companies/base_company.html`, e testes.
> - **Migrações:** `users/0008_studentprofile`, `jobs/0009_jobapplication_message_and_more`,
>   `bot/0008_alter_botmessage_key` (choices). Aplicam limpo; `makemigrations --check` sem pendências.
> - **Testes:** 7 (fluxo bot) + 6 (model/StudentProfile/e-mail) + 5 (portal) novos, todos verdes.
>   Suite completa `apps/bot`+`apps/jobs`+`apps/companies`+`apps/courses`: 365 passou, cobertura 73.24%
>   (acima do gate). As 2 falhas restantes (`TestCompanySignupEmailContext`) são ambientais
>   (confirmação de e-mail dispara task Celery→Redis indisponível local) e **não** se relacionam a
>   esta fase. `ruff check apps/` limpo.
> - **Decisões/desvios:** (1) `StudentProfile` separado (não campos no `UserProfile`) — perfil é
>   preocupação distinta e facilita o "tem mini-perfil?". (2) Dados do mini-perfil **não** usam
>   `EncryptedCharField`: são compartilhados com a empresa por design (portal/e-mail); LGPD tratada
>   evitando logar conteúdo (structlog só com IDs). (3) `message` (recado) existe no model mas **não**
>   é coletado no fluxo do bot ainda (mantém os 4 estados do plano enxutos) — fica para iteração futura.
>   (4) `process_message` passou a propagar o texto **bruto** (sem `.lower()`) só para o
>   `ApplicationHandler`, preservando a grafia de skills/período/link (o resto do pipeline segue com
>   texto normalizado). (5) `_handle_pending_action` refatorado (loop de handlers + helper de
>   onboarding) para respeitar o limite de complexidade do ruff.
> - **Pendências/próximos passos:** Fases 5 (busca online: jobspy+ranking+Adzuna) e 6 (admin de
>   SearchTerm) — independentes. Futuro: coletar `message`/`bio` e upload de CV via WhatsApp.

---

## Fase 5 — Busca online: jobspy + ranking + Adzuna

**Status:** ⬜ Não iniciada
**Pré-requisitos:** nenhum (independente). **Recomendado: spike antes** (validar credenciais Adzuna
e qualidade real do site `google` do jobspy com termos reais).
**Objetivo:** vagas online mais relevantes e com fonte redundante/confiável.

### Checklist — JobSpy + ranking
- [ ] Adicionar suporte ao site `google` do jobspy em `infra/jobspy/service.py`
      (jobspy usa `google_search_term` — montar uma query bem-formada)
- [ ] Adicionar campo `google_search_term` em `SearchTerm` (opcional) **ou** derivá-lo
      automaticamente de `term` + `location` + `job_type`
- [ ] Melhorar a montagem da query de busca (incluir sinônimos/qualificadores quando útil)
- [ ] Substituir o dedup puro (`apps/jobs/services.py:111` `deduplicate_jobs`) por **dedup + score
      de relevância**: termo no título (peso alto) > na descrição, recência (`date_posted`/
      `hours_old`), match de localização. Ordenar por score antes de cortar.
- [ ] Persistir o score: adicionar `relevance_score` em `DailyJob` (`apps/jobs/models/daily_job.py`)

### Checklist — Adzuna
- [ ] Criar `infra/adzuna/service.py`: client da API Adzuna (Brasil), retornando o mesmo formato de
      dict que o `JobSearchService.search` (title, company, location, job_type, job_url, date_posted,
      description, salary)
- [ ] Credenciais `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` via Docker Secrets/env (ver `config/env.py` e
      `secrets/`) — **nunca hardcode**
- [ ] Adicionar campo `source` em `DailyJob` (linkedin/indeed/glassdoor/google/adzuna)
- [ ] `fetch_and_save_daily_jobs` (`apps/jobs/services.py:133`): mesclar resultados jobspy + Adzuna
      na mesma pipeline de persistência (respeitar o `unique_together` de `DailyJob`)
- [ ] Testes: ranking ordena corretamente; Adzuna client parseia resposta (mockar HTTP); merge não
      duplica; `source` preenchido

### Boas práticas
- **Spike primeiro** (descartável): confirmar que a Adzuna tem cobertura útil para Curitiba/Brasil e
  que o site `google` do jobspy retorna resultados melhores. Só então codar a integração definitiva.
- Manter o **timeout por fonte** (jobspy já usa `ThreadPoolExecutor` com 30s) e tratar falha de uma
  fonte sem derrubar as outras (degradação graciosa — padrão já presente em
  `infra/jobspy/service.py`).
- Centralizar o "formato canônico de vaga" (dict de campos) para jobspy e Adzuna produzirem o mesmo
  shape — evita `if source == ...` espalhado.
- Respeitar limites de rate da API Adzuna; cachear/limitar `results_wanted`.

### Critérios de aceite
- `fetch_daily_jobs` popula `DailyJob` com vagas de jobspy **e** Adzuna, marcando `source`.
- Resultados exibidos ao aluno estão ordenados por relevância (não ordem arbitrária).
- Falha de uma fonte não impede as demais.

### Arquivos afetados
`infra/jobspy/service.py`, `infra/adzuna/` (novo), `apps/courses/models.py` (campo
`google_search_term`), `apps/jobs/models/daily_job.py` (`source`, `relevance_score`),
`apps/jobs/services.py`, `config/env.py`, `secrets/`, migrações, testes em `infra/` e `apps/jobs/`.

### Registro de Progresso
> _(preencher ao executar)_

---

## Fase 6 — Admin de SearchTerm intuitivo e traduzido

**Status:** ⬜ Não iniciada
**Pré-requisitos:** nenhum (independente). _Obs.: se a Fase 5 adicionar `google_search_term`,
incluir esse campo aqui também._
**Objetivo:** tornar o cadastro de termos de busca no Django Admin claro, 100% em português e com
ajuda no hover.

### Checklist
- [ ] Adicionar `verbose_name` em **todos** os campos de `SearchTerm` (`apps/courses/models.py:38`):
  - [ ] `term` → "Termo de busca"
  - [ ] `site_name` → "Sites de busca"
  - [ ] `location` → "Localização"
  - [ ] `distance` → "Distância (milhas)"
  - [ ] `job_type` → "Tipo de vaga"
  - [ ] `is_remote` → "Apenas remotas"
  - [ ] `results_wanted` → "Qtde. de vagas por termo"
  - [ ] `hours_old` → "Publicadas nas últimas (horas)"
  - [ ] `country_indeed` → "País (Indeed/Glassdoor)"
  - [ ] `linkedin_fetch_description` → "Buscar descrição completa (LinkedIn)"
  - [ ] `linkedin_company_ids` → "IDs de empresas (LinkedIn)"
  - [ ] `offset` → "Deslocamento (paginação)"
  - [ ] `priority` → "Prioridade"
  - [ ] `is_default` → "Ativo"
- [ ] Revisar/encurtar todos os `help_text` (já em PT) para explicação direta
- [ ] Tooltip no **hover**: aplicar `title=` nos widgets via um `ModelForm` no admin (atributo HTML
      `title` aparece como tooltip nativo do navegador), ou usar recurso de ajuda do Unfold
- [ ] Reorganizar fieldsets em `apps/courses/admin.py` (`SearchTermAdmin`):
  - [ ] **"Básico"** (sempre visível): curso, termo, localização, tipo de vaga, ativo, prioridade
  - [ ] **"Avançado"** (colapsado, `classes: ("collapse",)`): sites, distance, is_remote,
        results_wanted, hours_old, country_indeed, LinkedIn (fetch_description, company_ids), offset
- [ ] Manter o botão "Testar busca" funcionando (`apps/courses/admin.py:78`)
- [ ] Testes: form do admin renderiza labels PT; campos têm `title`; "Testar busca" segue ok

### Boas práticas
- `verbose_name` no **model** beneficia admin, forms e mensagens de erro — preferível a só renomear
  no admin.
- Tooltip de hover é `title=` no widget (simples e nativo); evite JS custom se Unfold já resolver.
- Não alterar nomes de **campos** (apenas `verbose_name`/`help_text`) para não exigir migração de
  dados nem quebrar `to_search_kwargs` (`apps/courses/models.py:138`).
- Agrupar campos avançados colapsados reduz a carga cognitiva do admin no dia a dia.

### Critérios de aceite
- Todos os rótulos do formulário de SearchTerm aparecem em português.
- Passar o mouse sobre um campo mostra explicação (tooltip).
- Campos avançados ficam recolhidos por padrão; o essencial fica à vista.

### Arquivos afetados
`apps/courses/models.py`, `apps/courses/admin.py`,
`templates/admin/courses/searchterm/change_form.html` (se necessário), testes em `apps/courses/`.

### Registro de Progresso
> _(preencher ao executar)_

---

## 🗒️ Registro de Progresso global

> Entrada nova **no topo**. Formato sugerido por entrada:
>
> ```
> ### AAAA-MM-DD — Fase X — <resumo>
> - O que foi feito: ...
> - Arquivos tocados: ...
> - Migrações: ...
> - Testes: <verdes/quais>
> - Decisões/desvios em relação ao plano: ...
> - Pendências/próximos passos: ...
> ```

### 2026-06-14 — Fase 4 — Candidatura com mini-perfil
- O que foi feito: ciclo completo de candidatura. `StudentProfile` (mini-perfil reutilizável) + `JobApplication.status/message/profile_snapshot`. `ApplicationHandler` no bot (coleta período→skills→link ou reusa perfil → confirma → cria candidatura + snapshot + e-mail à empresa). Portal de candidaturas (lista/muda status) + admin atualizado.
- Arquivos tocados: `apps/users/models.py`, `apps/jobs/models/job_application.py`, `apps/bot/handlers/application.py` (novo), `apps/bot/handlers/local_jobs.py`, `apps/bot/services.py`, `apps/bot/messages.py`, `apps/bot/email_service.py`, `apps/bot/tasks.py`, `apps/companies/{services,views,urls}.py`, `apps/jobs/admin/job_application.py`, `templates/companies/applications.html` (novo), testes.
- Migrações: `users/0008_studentprofile`, `jobs/0009_jobapplication_message_and_more`, `bot/0008_alter_botmessage_key`.
- Testes: 18 novos verdes; suite completa 365 passou; cobertura 73.24%; lint limpo. 2 falhas ambientais (Celery→Redis em confirmação de e-mail) não relacionadas.
- Decisões/desvios: `StudentProfile` separado; mini-perfil não criptografado (compartilhado por design, sem logar conteúdo); `message`/`bio` não coletados no bot ainda; texto bruto propagado só ao ApplicationHandler para preservar grafia; `_handle_pending_action` refatorado.
- Pendências/próximos passos: Fases 5 e 6 (independentes). Futuro: recado/bio e upload de CV.

### 2026-06-14 — Fase 3 — Menu do aluno: "Vagas do meu curso"
- O que foi feito: opção *3 — Vagas do meu curso* com `LocalJobsHandler` (lista vagas locais aprovadas da área do curso + detalhe da vaga); `candidatar` = stub "em breve" (Fase 4). Estados/rota `local_jobs_*`, menu renumerado (4=Sair, 5=Trocar Curso, 6=Empresa), alias de texto.
- Arquivos tocados: `apps/bot/handlers/local_jobs.py` (novo), `apps/bot/handlers/__init__.py`, `apps/bot/state_machine.py`, `apps/bot/services.py`, `apps/bot/messages.py`, `apps/bot/models/bot_message.py`, `apps/bot/handlers/menu.py`, `apps/jobs/services.py`, testes em `apps/bot`.
- Migrações: `bot/0007_alter_botmessage_key` (choices, no-op no banco).
- Testes: 12 novos verdes; 305 passou em `apps/bot`+`apps/jobs`+`apps/courses`; cobertura 72.32%; lint limpo.
- Decisões/desvios: área via `user.course.area`; novo helper `get_local_jobs_queryset_for_area` (reusa `Job.objects.for_area`, não duplica regra); candidatura é stub até Fase 4.
- Pendências/próximos passos: Fase 4 — candidatura liga-se ao detalhe já pronto (trocar o stub pelo fluxo real).

### 2026-06-13 — Fase 2 — Resumo semanal só local + caso vazio
- O que foi feito: caminho semanal local-only (sem jobspy) e sempre envia algo (aviso quando vazio); helpers `get_local_jobs_for_area`/`build_weekly_local_review`; stats `empty_notice`.
- Arquivos tocados: `apps/jobs/services.py`, `apps/jobs/tasks.py`, `apps/bot/messages.py`, `apps/bot/models/bot_message.py`, testes em `apps/jobs`.
- Migrações: nenhuma.
- Testes: 5 novos verdes; 70 passou em `apps/jobs`+`test_messages`; lint limpo.
- Decisões/desvios: templates locais dedicados (não mutar os compartilhados com on-demand); `no_jobs`→`empty_notice`.
- Pendências/próximos passos: Fase 3 — menu "Vagas do meu curso".

### 2026-06-13 — Fase 1 — Empresa escolhe a área da vaga
- O que foi feito: M2M `Job.areas` + helper `Job.objects.for_area` (regra "vazio = todas"); form/portal/admin.
- Arquivos tocados: `apps/jobs/models/job.py`, `apps/companies/forms.py`, `templates/companies/job_form.html`, `apps/jobs/admin/job.py`, testes em `apps/jobs` e `apps/companies`.
- Migrações: `0008_job_areas` (M2M, sem backfill).
- Testes: 10 novos verdes; 102 passou em `apps/jobs`+`apps/companies`; 2 falhas ambientais (Redis) não relacionadas; lint limpo.
- Decisões/desvios: queryset do form só áreas ativas; FK como string `"courses.Area"`.
- Pendências/próximos passos: Fase 2 — resumo semanal só local, reutilizando `for_area`.

### 2026-06-13 — Fase 0 — Fundação: model `Area`
- O que foi feito: model `Area` + FK `Course.area` (SET_NULL, nullable); `AreaAdmin` e ajustes no `CourseAdmin`.
- Arquivos tocados: `apps/courses/models.py`, `apps/courses/admin.py`, `apps/courses/tests/test_area.py`.
- Migrações: `0003_area_course_area` (schema), `0004_seed_areas` (data, reversível — 6 áreas + backfill).
- Testes: 7 novos verdes; suite `apps/courses` com 38 passando; `make lint` limpo.
- Decisões/desvios: +1 área "Ciências Agrárias e Biológicas" (cursos atuais: Agronomia, Ciências Biológicas).
- Pendências/próximos passos: Fase 1 — `Job.areas` (M2M) + helper "vazio = todas".

---

## ⚠️ Riscos e notas transversais

- **Renumeração do menu (Fase 3)** é o ponto mais propenso a regressão — revise todos os
  `_handle_numeric_*` em `apps/bot/services.py` e os testes de menu.
- **LGPD/privacidade (Fase 4)**: dados pessoais do aluno trafegam para a empresa; não logar
  conteúdo, considerar criptografia, e ter clareza no consentimento ao se candidatar.
- **Dependência externa (Fase 5)**: Adzuna e scraping podem falhar/mudar — degradação graciosa é
  obrigatória; nada no caminho do bot deve travar por causa de fonte externa.
- **Convenção "areas vazio = todas"**: centralize num único helper para evitar divergência entre
  resumo semanal, menu do aluno e admin.
- **Deploy**: o projeto usa CI/CD com gates (lint + testes). Migrações precisam aplicar limpo em
  produção (EC2/Docker Compose). Ver `CLAUDE.md` e `deployment/`.
