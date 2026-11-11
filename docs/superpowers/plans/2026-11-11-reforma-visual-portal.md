# Reforma visual do portal — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar a direção visual B ("Painel") a todas as páginas web fora do admin, com painel novo da empresa, página pública de vaga e as correções de comportamento decididas em 11/11.

**Architecture:** Um `base.html` mínimo + três layouts (`layouts/entrada.html`, `layouts/portal.html`, `layouts/simples.html`) e um único `static/css/portal.css` com tokens. Lógica nova fica no `CompaniesService` e em template tags (`apps/companies/templatetags/portal.py`); a página pública de vaga ganha `apps/jobs/views.py` + `apps/jobs/urls.py`.

**Tech Stack:** Django 5.2, django-allauth, Bootstrap 5.3.2 (CDN, já em uso), Public Sans auto-hospedada, WhiteNoise, pytest.

**Spec:** `docs/superpowers/specs/2026-11-11-reforma-visual-portal-design.md`

## Global Constraints

- Bootstrap 5.3.2 do CDN atual; nenhum framework/lib nova de front.
- Paleta: `#FFD100`, `#000`, `#FFF` (+ neutros/estados da tabela de tokens do spec, valores exatos de lá).
- Logo UTFPR: `static/img/logo-utfpr.png` em fundo claro, `logo-utfpr-branco.png` em fundo escuro, sempre `height:auto`; **obrigatório** em `/empresas/login/` e `/empresas/signup/`; uma vez por tela.
- Sem emoji em títulos/ícones de status (vira quadradinho); ícones em SVG inline ou CSS.
- Nenhum `style="..."` nem `<style>` em templates — tudo em `static/css/portal.css`.
- Textos em português com acento, frase em caixa normal (sem CAIXA ALTA em rótulos).
- Testes: `REDIS_URL=redis://localhost:6379/0 poetry run pytest <alvo> --no-cov -q` (sem Redis a suíte parece travada).
- Commits: Conventional Commits em português, **sem** linha `Co-Authored-By` (repo público).
- Limpar código morto da área tocada no mesmo task (preferência do usuário).

## Review Focus

- Empresa `pending` ou `blocked` abrindo o painel: vê o aviso no topo, "Publicar nova vaga" desabilitado com explicação, números zerados sem erro (Task 5).
- Editar vaga e salvar **sem alterar nada**: status não muda (Task 4).
- WhatsApp que não é telefone (`123@lid`, vazio, `None`) ou número antigo de 8 dígitos: nada de link quebrado (Task 2).
- Empresa sem nenhuma vaga/candidatura: painel com estados vazios e contagens 0 (Task 5).
- Página pública de vaga não aprovada (`pending`, `rejected`, `removed`, `expired`) ou inexistente: 404, sem vazar dados (Task 9).

---

### Task 1: Base visual (tokens, fonte, mascote, layouts, alertas)

**Files:**
- Create: `static/css/portal.css`, `static/fonts/public-sans-latin-wght-normal.woff2`, `static/fonts/OFL.txt`, `static/img/mascote.png`
- Create: `templates/layouts/entrada.html`, `templates/layouts/portal.html`, `templates/layouts/simples.html`, `templates/includes/mensagens.html`, `templates/includes/logo_utfpr.html`
- Modify: `templates/base.html` (reescrito)
- Delete: `static/img/logo-icon.png`
- Test: `apps/core/tests/test_layouts.py`

**Interfaces:**
- Produces: blocos de `base.html`: `title`, `body_class`, `body`, `extra_js`. `layouts/entrada.html`: `entrada_titulo`, `entrada_texto`, `entrada_conteudo`. `layouts/portal.html`: `portal_titulo`, `portal_acoes` (botões do cabeçalho), `portal_conteudo`; marca item ativo por `request.resolver_match.url_name` (`dashboard`, `applications`, `profile`). `layouts/simples.html`: `simples_conteudo`. `includes/logo_utfpr.html` recebe `variante` (`"claro"`|`"escuro"`) e `classe`.
- Classes CSS que os próximos tasks usam: `.bloco`, `.bloco-titulo`, `.linha`, `.meta`, `.st` + `.st-ok`/`.st-analise`/`.st-recusada`/`.st-nova`/`.st-neutro`, `.motivo`, `.numeros`/`.numero`/`.numero.destaque`, `.btn-primary` (amarelo, texto preto), `.btn-leve`, `.wa`, `.vazio` (estado vazio). Valores e medidas: os de `.claude/ui-review/mockups/b.css` (referência visual aprovada).

- [ ] **Step 1: Write the failing test** — `apps/core/tests/test_layouts.py` renderiza cada layout com `render_to_string` + `RequestFactory`:
  - `test_base_usa_portal_css_e_mascote`: HTML contém `css/portal.css` e `img/mascote.png`; não contém `logo-icon.png` nem `<style`.
  - `test_mensagens_renderizadas_uma_vez`: com uma mensagem `messages.success(...)` na request, o texto aparece exatamente 1 vez em `layouts/portal.html`.
  - `test_mensagem_error_vira_alert_danger`: tag `error` → classe `alert-danger`.
- [ ] **Step 2: Run** `REDIS_URL=redis://localhost:6379/0 poetry run pytest apps/core/tests/test_layouts.py --no-cov -q` — Expected: FAIL (templates não existem).
- [ ] **Step 3: Assets.** Copiar `.claude/ui-review/mockups/mascote.png` → `static/img/mascote.png`. Baixar o woff2 variável latino da Public Sans do pacote `@fontsource-variable/public-sans` (jsdelivr, versão fixa ≥ 2 semanas) para `static/fonts/` e o `OFL.txt` da fonte. `git rm static/img/logo-icon.png` e trocar toda referência a ele.
- [ ] **Step 4: Implement** `portal.css` (`@font-face` com `font-display: swap`, tokens do spec em `:root`, re-tema de `.btn-primary`, `.form-control`/`.form-select` com foco amarelo, componentes listados acima, menu lateral 248 px + offcanvas no celular, login dividido com formulário acima da dobra no celular), `base.html` (head, Bootstrap CSS/JS do CDN, `<link rel="icon">` = mascote, include de mensagens **uma única vez**), os três layouts e os dois includes. `mensagens.html` mapeia `error`→`danger`.
- [ ] **Step 5: Run** o teste do Step 2 — Expected: PASS.
- [ ] **Step 6: Commit** `feat(portal): base visual com tokens, Public Sans e layouts`

### Task 2: Template tags do portal (WhatsApp, selos, contador)

**Files:**
- Create: `apps/companies/templatetags/__init__.py`, `apps/companies/templatetags/portal.py`
- Test: `apps/companies/tests/test_portal_tags.py`

**Interfaces:**
- Produces (carregar com `{% load portal %}`):
  - filtro `whatsapp_display(phone_number: str | None) -> str`
  - filtro `whatsapp_link(phone_number: str | None) -> str` (`""` quando não é telefone)
  - `simple_tag selo_vaga(status: str) -> dict` com chaves `rotulo`, `classe`
  - `simple_tag selo_candidatura(status: str) -> dict` com chaves `rotulo`, `classe`
  - `simple_tag(takes_context=True) candidaturas_novas(context) -> int` (candidaturas `pending` da empresa do usuário logado; 0 sem empresa)

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("raw, shown, link", [
    ("5545999990000@c.us", "(45) 99999-0000", "https://wa.me/5545999990000"),
    ("554599990000@c.us", "(45) 9999-0000", "https://wa.me/554599990000"),
    ("5545999990000", "(45) 99999-0000", "https://wa.me/5545999990000"),
    ("123456789012345@lid", "", ""),
    ("", "", ""),
    (None, "", ""),
    ("14155550000@c.us", "", ""),   # não é +55: não inventa formato
])
def test_whatsapp(raw, shown, link):
    assert whatsapp_display(raw) == shown
    assert whatsapp_link(raw) == link

def test_selo_vaga():
    assert selo_vaga("pending") == {"rotulo": "Em análise", "classe": "st-analise"}
    assert selo_vaga("approved") == {"rotulo": "Publicada", "classe": "st-ok"}
    assert selo_vaga("rejected") == {"rotulo": "Recusada", "classe": "st-recusada"}
    assert selo_vaga("expired")["rotulo"] == "Expirada"

def test_selo_candidatura():
    assert selo_candidatura("pending") == {"rotulo": "Nova", "classe": "st-nova"}
    assert selo_candidatura("contatado")["classe"] == "st-ok"
```
  Mais `test_candidaturas_novas_conta_so_pending_da_empresa` (TestCase com 2 empresas; usar `apps/jobs/tests/factories.py`).
- [ ] **Step 2: Run** `... pytest apps/companies/tests/test_portal_tags.py --no-cov -q` — Expected: FAIL (ImportError).
- [ ] **Step 3: Implement.** Regra do telefone: tira o sufixo `@c.us`; só dígitos; precisa começar com `55` e ter 12 ou 13 dígitos; DDD = dígitos 3–4; resto com 9 dígitos → `XXXXX-XXXX`, com 8 → `XXXX-XXXX`; link `https://wa.me/<dígitos>`. Fora disso → `""`. Selos: `draft`→`Rascunho`/`st-neutro`, `expired`→`Expirada`/`st-neutro`, `removed`→`Removida`/`st-neutro`; candidatura `vista`→`Vista`/`st-neutro`, `rejeitada`→`Recusada`/`st-recusada`; status desconhecido → rótulo cru + `st-neutro`.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(portal): tags de WhatsApp formatado, selos de status e contador`

### Task 3: "Tipo da vaga" com rótulos

**Files:**
- Modify: `apps/companies/forms.py` (`JobForm.TIPO_CHOICES`, widget `form-select`), `apps/companies/tests/test_forms.py` (`"estagio"` → `"Estágio"`)
- Create: `apps/jobs/migrations/0011_job_tipo_rotulos.py`
- Test: `apps/jobs/tests/test_tipo_migration.py`

**Interfaces:**
- Produces: `JobForm.TIPO_CHOICES = [("Estágio","Estágio"), ("CLT","CLT"), ("PJ","PJ"), ("Temporário","Temporário")]`; widget `forms.Select(attrs={"class": "form-select"})`.

- [ ] **Step 1: Write the failing tests:** `test_jobform_aceita_rotulo_estagio` (form válido com `tipo="Estágio"`), `test_jobform_rejeita_slug_antigo` (`tipo="estagio"` inválido), e o teste da migração com `django_test_migrations` **se** já estiver nas dependências; senão, testar a função `converter_tipos(apps, schema_editor)` importando o módulo da migração e chamando-a contra o modelo real: `estagio`→`Estágio`, `clt`→`CLT`, `pj`→`PJ`, `temporario`→`Temporário`, valor já rotulado/livre fica igual.
- [ ] **Step 2: Run** `... pytest apps/companies/tests/test_forms.py apps/jobs/tests/test_tipo_migration.py --no-cov -q` — Expected: FAIL.
- [ ] **Step 3: Implement** choices + `RunPython(converter_tipos, desfazer_tipos)` (reverso mapeia de volta). No `job_form.html`, só trocar os `value` das `<option>` escritas à mão para os rótulos (o Task 6 substitui o bloco por `{{ form.tipo }}`).
- [ ] **Step 4: Run** — Expected: PASS; `poetry run python manage.py makemigrations --check --dry-run` sem mudanças pendentes.
- [ ] **Step 5: Commit** `fix(vagas): tipo da vaga gravado com o rótulo (Estágio, CLT, PJ, Temporário)`

### Task 4: Editar vaga devolve para análise

**Files:**
- Modify: `apps/companies/services.py`, `apps/companies/views.py` (`JobUpdateView.form_valid`)
- Test: `apps/companies/tests/test_views.py` (classe de testes de edição existente)

**Interfaces:**
- Produces: `CompaniesService.prepare_job_for_update(job: Job, changed: bool) -> bool` — se `changed` e `job.status in {APPROVED, REJECTED}`: `status = PENDING`, `rejection_reason = None`, retorna `True` (voltou para análise); senão não mexe e retorna `False`.

- [ ] **Step 1: Write the failing tests:** `test_editar_vaga_aprovada_volta_para_analise`, `test_editar_vaga_recusada_volta_para_analise_e_limpa_motivo`, `test_editar_vaga_pendente_continua_pendente`, `test_salvar_sem_alterar_nao_muda_status` (POST com os mesmos valores da vaga aprovada → continua `approved`), `test_mensagem_de_reenvio` (mensagem de sucesso contém "voltou para análise" quando reenviada).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** — `form_valid` chama `prepare_job_for_update(form.instance, form.has_changed())` antes do `super().form_valid`; mensagem: `"Vaga atualizada. Ela voltou para análise da UTFPR."` quando retornou `True`, senão `"Vaga atualizada."`. Corrigir de passagem os textos sem acento do `services.py` ("Você não tem permissão para editar esta vaga." etc.).
- [ ] **Step 4: Run** `... pytest apps/companies --no-cov -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(vagas): editar vaga aprovada ou recusada devolve para análise`

### Task 5: Painel da empresa

**Files:**
- Modify: `apps/companies/services.py`, `apps/companies/views.py`, `apps/companies/urls.py`, `apps/companies/mixins.py`, `apps/users/adapters.py`, `apps/users/views.py` (`ConfirmEmailView` + ramo com empresa do `success_page`), `apps/bot/handlers/menu.py` (`send_company_portal_link`), `apps/bot/proactive.py`
- Create: `templates/companies/dashboard.html`
- Modify tests: `apps/companies/tests/test_mixins.py`, `apps/companies/tests/test_views.py`, `apps/users/tests/test_views.py` (destinos `/empresas/perfil/` → `/empresas/painel/` onde for redirecionamento pós-login/ação)
- Test: `apps/companies/tests/test_dashboard.py`

**Interfaces:**
- Consumes: tags do Task 2; layout portal do Task 1.
- Produces:
  - `@dataclass DashboardSummary(new_applications: int, jobs_pending: int, jobs_rejected: int, jobs_approved: int, jobs: QuerySet[Job], recent_applications: list[JobApplication])` em `apps/companies/services.py`; `jobs` = `list_company_jobs(company)` anotado com `num_applications`; `recent_applications` = 5 mais recentes com `select_related("user", "job")`.
  - `CompaniesService.dashboard_summary(company: Company) -> DashboardSummary`
  - `CompanyDashboardView` (`LoginRequiredMixin`, `TemplateView`), rota `path("painel/", ..., name="dashboard")`; sem empresa → redirect `/empresas/criar/`.
  - Destino padrão pós-login/ação da empresa: `reverse("companies:dashboard")` = `/empresas/painel/`.

- [ ] **Step 1: Write the failing tests** (`test_dashboard.py`):
  - `test_resumo_conta_por_status` — 1 aprovada, 1 pendente, 1 recusada, 1 removida, 2 candidaturas (1 `pending`, 1 `vista`) → `(new_applications, jobs_pending, jobs_rejected, jobs_approved) == (1, 1, 1, 1)`; removida fora de `jobs`.
  - `test_num_applications_por_vaga` e `test_resumo_sem_n_mais_1` (`assertNumQueries` constante com 1 e 5 vagas).
  - `test_resumo_vazio` — empresa sem vagas → zeros, `jobs` vazio, `recent_applications == []`.
  - `test_painel_mostra_motivo_da_recusa` — GET `/empresas/painel/` contém `Recusada`, o texto do `rejection_reason` e "Editar e reenviar".
  - `test_painel_mostra_whatsapp_com_link` — contém `https://wa.me/`.
  - `test_painel_empresa_pendente_mostra_aviso_e_desabilita_publicar` — contém "aguardando aprovação" e o botão sem `href` de nova vaga.
  - `test_painel_sem_empresa_redireciona_para_criar`; `test_painel_anonimo_redireciona_para_login`.
  - `test_login_empresa_vai_para_painel`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** serviço, view, rota e `dashboard.html` (estrutura do mockup B: cabeçalho "Olá, {{ company.contato_nome }}" + nome da empresa + "Publicar nova vaga"; 4 números; "Minhas vagas" e "Candidaturas recentes" com estados vazios). Trocar os destinos: `CompanyLoginView.get_success_url`, `success_url` de `JobCreateView`/`JobUpdateView`/`JobDeleteView`, `ApprovedCompanyRequiredMixin`, `CompanyCreateView`, adapter, `ConfirmEmailView`, `success_page` (ramo com empresa), bot (`menu.py`, `proactive.py`) — todos para `/empresas/painel/`. `CompanyProfileView` continua em `/empresas/perfil/`, só sem a lista de vagas (sai `context["jobs"]`). Em `layouts/portal.html`, item "Candidaturas" ganha o contador (`{% load portal %}{% candidaturas_novas as n %}`, só aparece se `n > 0`).
- [ ] **Step 4: Atualizar** os testes existentes que esperavam `/empresas/perfil/` como destino (lista em **Files**) e as mensagens do bot nos testes de `apps/bot/tests` que citam a URL.
- [ ] **Step 5: Run** `... pytest apps/companies apps/users apps/bot --no-cov -q` — Expected: PASS.
- [ ] **Step 6: Commit** `feat(portal): painel da empresa com resumo, vagas e candidaturas recentes`

### Task 6: Demais páginas logadas da empresa

**Files:**
- Modify: `templates/companies/profile.html`, `applications.html`, `job_form.html`, `job_confirm_delete.html`, `company_create.html`
- Delete: `templates/companies/base_company.html` (substituído por `layouts/portal.html`)
- Test: `apps/companies/tests/test_application_views.py`, `apps/companies/tests/test_views.py`

- [ ] **Step 1: Write the failing tests:** `test_candidaturas_whatsapp_formatado_com_link` (contém `(45) 99999-0000` e `https://wa.me/5545999990000`, não contém `@c.us`), `test_candidaturas_email_mailto`, `test_candidaturas_mostra_nome_do_snapshot`, `test_form_vaga_tipo_e_select` (contém `class="form-select"` no `id_tipo`), `test_form_edicao_avisa_volta_para_analise` (edição de vaga aprovada contém "volta para análise"), `test_perfil_nao_lista_vagas`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** os templates no layout portal: candidaturas com data `d/m/Y \à\s H:i` legível no cabeçalho claro; formulário de vaga com `{{ form.tipo }}`, áreas em grade (`.areas-grade`, 2–3 colunas) e botões "Cancelar"/"Enviar para análise" (nova) ou "Salvar e reenviar" (edição de aprovada/recusada); remover com botão `btn-danger`; perfil só com o formulário de dados.
- [ ] **Step 4: Run** `... pytest apps/companies --no-cov -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(portal): candidaturas, formulário de vaga e dados da empresa no visual novo`

### Task 7: Telas de entrada (empresa)

**Files:**
- Modify: `templates/companies/login.html`, `templates/companies/signup.html`, `templates/account/password_reset.html`, `password_reset_done.html`, `password_reset_from_key.html`, `password_reset_from_key_done.html`, `verification_sent.html`, `email_confirm.html`, `logout.html`
- Modify: `apps/companies/views.py` (`CompanyLoginView.get_context_data` adiciona `whatsapp_url = bot_whatsapp_url()`)
- Test: `apps/companies/tests/test_views.py`, `apps/users/tests/test_views.py`

- [ ] **Step 1: Write the failing tests:** `test_login_e_cadastro_tem_logo_utfpr` (exigência INPI: `/empresas/login/` e `/empresas/signup/` contêm `img/logo-utfpr.png`), `test_login_tem_linha_para_aluno` (com `bot_whatsapp_url` mockado → contém "É aluno da UTFPR?" e o link; mock retornando `None` → texto sem link), `test_reset_de_senha_volta_para_login_da_empresa` (GET `/accounts/password/reset/` e a página "done" contêm `/empresas/login/` e não contêm `/accounts/login/`).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** no layout entrada. Cadastro agrupado em "Empresa", "Responsável", "Acesso". Todos os "voltar para login" → `{% url 'companies:login' %}`.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(portal): telas de entrada da empresa no visual novo`

### Task 8: Fim do login/cadastro de aluno com senha + telas do aluno

**Files:**
- Modify: `waha_bot/urls.py`, `waha_bot/settings/base.py` (`ACCOUNT_LOGOUT_REDIRECT_URL = "/empresas/login/"`), `templates/account/success.html`, `templates/account/email_confirmed.html`
- Delete: `templates/account/login.html`, `templates/account/signup.html`, `apps/users/templates/users/email_confirmed.html` (sem uso)
- Modify tests: `apps/users/tests/test_auth_flow.py` (apagar `test_signup_with_valid_email`, `test_signup_with_invalid_email`, `test_email_confirmation_sent`, `test_login_success`, `test_login_unverified_email`; manter logout e reset de senha), `apps/users/tests/test_views.py:49`
- Test: `apps/users/tests/test_student_web_routes.py`

**Interfaces:**
- Produces: em `waha_bot/urls.py`, **antes** do `include("allauth.urls")`: `path("accounts/login/", RedirectView(url="/empresas/login/"), name="account_login")` e `path("accounts/signup/", RedirectView(url="/empresas/signup/"), name="account_signup")` — mesmos nomes, para o `reverse` interno do allauth continuar resolvendo.

- [ ] **Step 1: Write the failing tests:** `test_accounts_login_redireciona` (GET e POST → 302 `/empresas/login/`), `test_accounts_signup_redireciona` (→ `/empresas/signup/`; POST não cria `User`), `test_logout_vai_para_login_da_empresa`, `test_sucesso_aluno_sem_emoji_e_com_whatsapp` (logado sem empresa, `bot_whatsapp_url` mockado → contém "Voltar para o WhatsApp" e o link; não contém `🐧`), `test_sucesso_anonimo_leva_ao_login_da_empresa`, `test_link_invalido_mostra_proximo_passo` (GET `/confirmar-email/token-invalido/` → 200, contém "Link expirado ou inválido").
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** rotas, setting, templates no layout simples (ícone de sucesso/erro em SVG inline). Apagar templates e testes listados. Varrer `docs/development/AWS_SES_SETUP.md` (passo com `/accounts/signup/`) e `docs/SECURITY.md` (rate-limit de `/accounts/login`: anotar que a rota agora só redireciona).
- [ ] **Step 4: Run** `... pytest apps/users --no-cov -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(contas): aluno sem login web; telas de confirmação no visual novo`

### Task 9: Página pública de vaga

**Files:**
- Create: `apps/jobs/views.py`, `apps/jobs/urls.py`, `templates/jobs/vaga_publica.html`
- Modify: `waha_bot/urls.py` (`path("vagas/", include("apps.jobs.urls"))`), `apps/jobs/services.py` (`_serialize_local_job`)
- Test: `apps/jobs/tests/test_public_job_view.py`, `apps/jobs/tests/test_services.py`

**Interfaces:**
- Produces: `JobPublicDetailView(DetailView)` com `queryset = Job.objects.filter(status=JobStatus.APPROVED).select_related("company").prefetch_related("areas")`, `app_name = "jobs"`, rota `path("<int:pk>/", ..., name="public_detail")` → `/vagas/<pk>/`; contexto `whatsapp_url = bot_whatsapp_url()` (de `apps.users.views`).

- [ ] **Step 1: Write the failing tests:** `test_vaga_aprovada_200` (contém título, nome da empresa, descrição, "Vagas do meu curso"), parametrizado `test_vaga_nao_aprovada_404` para `pending`, `rejected`, `removed`, `expired`, `draft`, `test_vaga_inexistente_404`, `test_nao_exige_login`, `test_titulo_com_html_escapado` (título `<b>x</b>` aparece escapado), e em `test_services.py`: `test_link_da_vaga_local_aponta_para_pagina_publica` (`job_url` termina com `/vagas/{pk}/` e não contém `/empresas/`).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** view, rotas, template no layout simples (sem dados pessoais; botão "Abrir o IterBot no WhatsApp" quando `whatsapp_url`, instrução sempre visível), e a URL em `_serialize_local_job`. Corrigir a docstring desatualizada de `apps/bot/handlers/local_jobs.py` ("stub em breve" → candidatura implementada).
- [ ] **Step 4: Run** `... pytest apps/jobs --no-cov -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(vagas): página pública da vaga e link correto no resumo semanal`

### Task 10: Páginas de erro

**Files:**
- Create: `templates/403.html`, `templates/404.html`, `templates/500.html`
- Test: `apps/core/tests/test_error_pages.py`

- [ ] **Step 1: Write the failing tests:** com `override_settings(DEBUG=False)`: `test_404_personalizado` (GET `/nao-existe/` → 404 com "Página não encontrada" e `img/mascote.png`), `test_403_personalizado` (empresa tentando editar vaga de outra → 403 com "Acesso negado"), `test_500_renderiza_sem_contexto` (`render_to_string("500.html")` não levanta e contém "Algo deu errado").
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** os três no layout simples; `500.html` não depende de `request`, `user` nem `messages`.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(portal): páginas de erro 403, 404 e 500`

### Task 11: Varredura final, documentação e prints "depois"

**Files:**
- Modify: `CLAUDE.md` (convenção de logotipo: mascote `static/img/mascote.png`, CSS único `static/css/portal.css`, layouts), `.claude/ui-review/shoot.js` (fora do git: incluir `/empresas/painel/`, `/vagas/1/`, `/nao-existe/`)

- [ ] **Step 1:** `grep -rn 'style="' templates/companies templates/account templates/layouts templates/jobs templates/includes` e `grep -rn "<style" templates --include=*.html` (fora `templates/admin` e `templates/unfold`) — Expected: nada. `grep -rn "logo-icon\|base_company\|account/login.html\|users/email_confirmed" apps templates waha_bot docs` — Expected: nada.
- [ ] **Step 2: Run** a suíte inteira `REDIS_URL=redis://localhost:6379/0 poetry run pytest --no-cov -q` e `make ci-check` — Expected: tudo verde.
- [ ] **Step 3:** subir o ambiente (`bash .claude/ui-review/subir-local.sh`), tirar os prints com `OUT=.claude/ui-review/depois node .claude/ui-review/shoot.js` e conferir cada tela contra o mockup B (desktop 1366 e mobile 390). Corrigir o que destoar. Parar com `docker stop iterbot_ui_db` e encerrar o runserver pelo PID (não usar `pkill -f`).
- [ ] **Step 4: Commit** `docs: convenções do visual do portal`
