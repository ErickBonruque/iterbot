# Reforma visual do portal web — desenho

Data: 2026-11-11 · Direção escolhida: **B, "Painel"** (mockups em `.claude/ui-review/mockups/`, fora do git)

## Intenção

A interface do portal já resolve o que precisa tecnicamente. O objetivo é deixá-la agradável e à altura da
UTFPR: identidade única (preto, amarelo `#FFD100`, branco, mascote do IterBot e logo oficial da UTFPR),
um único padrão de cabeçalho, e um painel que mostre primeiro o que a empresa mais usa (vagas e
candidaturas). Junto vêm correções de UX/bugs encontrados na auditoria de 11/11 e a limpeza de código morto
na área tocada.

Público: RH de empresas da região (desktop e celular) e, em telas pontuais, alunos que chegam por links do bot.

## Escopo

**Entra**
- Todas as páginas web fora do admin: `templates/base.html`, `templates/companies/*`, `templates/account/*`,
  páginas de erro (novas) e a página pública de vaga (nova).
- Alertas e avisos: mensagens do Django (`messages`), avisos de cadastro pendente/bloqueado, erros de formulário,
  telas de verificação/confirmação (inclusive a que o aluno vê ao clicar no link enviado pelo WhatsApp).
- Correções de lógica listadas em "Mudanças de comportamento".

**Não entra**
- Django admin (Unfold) — frente 3, com proposta própria a validar.
- E-mails em texto (`templates/account/email/*.txt`) — sem mudança visual.
- README e prints "depois" — frente 2, feita após esta.

## Restrições

- Bootstrap 5.3.2 (CDN atual) continua; nada de framework novo (host: 1 vCPU / 1,8 GB).
- Exigência INPI: logo oficial da UTFPR nas telas de entrada (login e cadastro de empresa), cores e proporções
  preservadas (`static/img/logo-utfpr.png` em fundo claro, `logo-utfpr-branco.png` em fundo escuro; sempre com
  `height:auto`, nunca distorcido); paleta amarelo `#FFD100`, preto e branco.
- Estáticos servidos pelo WhiteNoise (`CompressedManifestStaticFilesStorage`) — todo asset novo vai em `static/`
  e é referenciado por `{% static %}`.
- Commits em Conventional Commits, sem linha de coautoria (repo público).

## Sistema visual (tokens)

Um único arquivo `static/css/portal.css` substitui o `<style>` inline do `base.html` e os `style="..."` espalhados
nos templates. Tokens em `:root`:

| Token | Valor | Uso |
|---|---|---|
| `--amarelo` | `#FFD100` | ação principal, item ativo do menu, destaque do resumo |
| `--amarelo-claro` | `#FFF4BF` | selo "Em análise" |
| `--preto` | `#000` | menu lateral, metade escura do login, texto |
| `--branco` | `#FFF` | superfícies |
| `--cinza-fundo` | `#F1F1EF` | fundo das páginas internas |
| `--cinza-linha` | `#E0E0DC` | bordas de blocos e divisórias |
| `--cinza-texto` | `#555` | texto secundário (contraste ≥ 4.5:1 sobre branco) |
| `--verde` / `--vermelho` | `#17703A` / `#A61B1B` | publicada / recusada, WhatsApp |

- **Tipografia:** Public Sans (OFL), **auto-hospedada** em `static/fonts/` (woff2 variável, pesos 400–800) — sem
  requisição a terceiros (LGPD) e sem depender do Google Fonts. Fallback `system-ui`.
  Escala: títulos de página 1,75 rem/800; títulos de bloco 1,1 rem/700; corpo 1 rem/400; meta 0,9 rem.
- **Componentes:** botão principal amarelo com texto preto (`.btn-primary` do Bootstrap re-tematizado, para
  não reescrever todos os botões); botão secundário branco com borda; selo de status em pílula; bloco branco com
  borda de 1 px e raio 10 px; foco visível com anel amarelo de 3 px em todos os campos e botões.
- **Mascote:** recorte com fundo transparente gerado a partir de `.claude/ui-review/logo-iterbot-recebido.png`
  (script `.claude/ui-review/recortar.js`) e salvo como `static/img/mascote.png` (+ versão pequena para favicon).
  Sobre fundo preto vai num ladrilho amarelo de cantos arredondados. Substitui `static/img/logo-icon.png` (o "i"
  genérico), que é removido.

## Layouts

Três "cascas" (templates base), todas estendendo um `base.html` mínimo (head, CSS, fontes, mensagens, JS):

1. **Entrada (`layout_entrada`)** — login e cadastro de empresa, recuperação/definição de senha, verificação
   enviada, confirmação de e-mail, logout. Desktop: tela dividida — metade preta com mascote grande, título e
   2 bullets curtos; metade branca com logo UTFPR (cores originais) + formulário. Celular: faixa preta curta com
   mascote pequeno e título no topo, **formulário logo abaixo** (acima da dobra), sem os bullets.
2. **Portal (`layout_portal`)** — páginas logadas da empresa. Desktop: menu lateral preto fixo (248 px) com
   mascote + "iterbot", itens Painel / Candidaturas (com contador de novas) / Dados da empresa / Sair e o logo
   UTFPR branco no rodapé do menu. Celular: barra superior preta com mascote e botão que abre o mesmo menu
   (offcanvas do Bootstrap). O botão "Publicar nova vaga" fica no cabeçalho do conteúdo, não no menu.
3. **Avulsa (`layout_simples`)** — telas de resultado e páginas públicas: sucesso do aluno, link inválido,
   página pública de vaga, erros 403/404/500. Barra superior preta fina com mascote + "iterbot", conteúdo
   centralizado em um bloco branco, rodapé com logo UTFPR branco sobre preto.

O logo UTFPR aparece **uma vez por tela** (a duplicação cartão + rodapé acaba).

## Telas

### Empresa (portal)
- **Painel (novo, `/empresas/painel/`)** — landing após login. Cabeçalho "Olá, {contato_nome}" + nome da empresa
  + "Publicar nova vaga". Resumo em 4 números: candidaturas novas (status `pending`), vagas em análise, vagas
  recusadas, vagas publicadas; o número de candidaturas novas é o destacado em amarelo quando > 0. Abaixo, à
  esquerda **Minhas vagas** (todas as não removidas, mais recente primeiro) com selo de status, tipo, contagem
  de candidaturas, e para recusadas o **motivo** (`rejection_reason`) e o botão "Editar e reenviar"; à direita
  **Candidaturas recentes** (5 últimas) com nome, curso/período, selo e WhatsApp formatado com link.
  Avisos de cadastro pendente/bloqueado aparecem no topo do painel. Estados vazios convidam à ação
  ("Publique a primeira vaga").
- **Dados da empresa (`/empresas/perfil/`)** — o formulário atual, sozinho, no layout portal.
- **Candidaturas** — lista em blocos: cabeçalho com vaga + data legível (corrige o cinza-escuro sobre preto),
  candidato (nome do snapshot, RA, e-mail como `mailto:`, WhatsApp formatado `(45) 99999-0000` com link
  `wa.me`), mini-perfil, recado, e o seletor de status. Paginação re-tematizada.
- **Nova vaga / Editar vaga** — `tipo` vira `form-select` real; áreas em grade de 2–3 colunas com checkboxes
  maiores; aviso claro de que a vaga passa pela análise da UTFPR (e, na edição de vaga aprovada/recusada, que
  ela **volta para análise**). Botões "Cancelar" / "Enviar para análise" (criação) e "Salvar e reenviar"
  (edição).
- **Remover vaga** — confirmação no layout portal, botão destrutivo vermelho.
- **Criar empresa (`/empresas/criar/`)** — fallback; mesmo formulário do cadastro no layout portal.

### Empresa (entrada)
- **Login** — mockup B. Linha extra: "É aluno da UTFPR? O IterBot funciona pelo WhatsApp" com link do bot
  (`bot_whatsapp_url()`; se indisponível, só o texto).
- **Cadastro de empresa** — layout entrada; campos agrupados em "Empresa" e "Responsável" e "Acesso".
- **Recuperar senha / e-mail enviado / definir nova senha / senha alterada** — layout entrada; todos os
  "voltar para login" apontam para `/empresas/login/`.
- **Verificação enviada / confirmar e-mail** — layout entrada.
- **Sair** — confirmação no layout entrada.

### Aluno e links do WhatsApp
- **Sucesso após confirmar pelo link do bot (`/accounts/success/`, logado sem empresa)** — layout simples,
  mascote, "Tudo certo, {e-mail} confirmado", botão verde "Voltar para o WhatsApp" (`bot_whatsapp_url()`);
  sem o emoji 🐧 (que vira quadradinho). Ramo anônimo (empresa que confirmou e-mail em outro navegador) leva a
  `/empresas/login/`. Ramo logado com empresa leva ao painel.
- **Link inválido/expirado e confirmação de vínculo da empresa via WhatsApp** (`account/email_confirmed.html`) —
  layout simples, ícone de sucesso/erro desenhado em CSS/SVG (sem emoji), instrução do próximo passo.
- **Página pública de vaga (nova, `/vagas/<id>/`)** — sem login; só vagas `approved` (demais: 404). Título,
  empresa, cidade, tipo, salário, descrição, requisitos, áreas. Ação: "Abrir o IterBot no WhatsApp" + instrução
  "No menu, escolha *Vagas do meu curso* e selecione esta vaga para se candidatar". Sem dados pessoais.
- **Erros 403 / 404 / 500** — layout simples, mascote, mensagem curta e link de volta. `500.html` não depende de
  contexto (só `{% static %}`).

### Alertas
- `messages` do Django: componente único (`includes/mensagens.html`) com borda à esquerda colorida por tipo,
  texto preto, botão fechar; mapeia `error` → `danger`. Uma única renderização (hoje `base.html` e
  `base_company.html` renderizam duas vezes o bloco).
- Erros de formulário: `is-invalid` + texto sob o campo; erros gerais no topo do formulário.

## Mudanças de comportamento (decididas com o usuário em 11/11)

1. **Login/cadastro de aluno com senha saem.** `/accounts/login/` e `/accounts/signup/` redirecionam para
   `/empresas/login/`. `ACCOUNT_LOGOUT_REDIRECT_URL` → `/empresas/login/`. Templates `account/login.html` e
   `account/signup.html` e os testes de fluxo web de aluno com senha (`apps/users/tests/test_auth_flow.py`) são
   removidos/reescritos. As rotas do allauth que as empresas usam (reset de senha, confirmação de e-mail, logout)
   continuam.
2. **Editar vaga devolve para análise.** Qualquer edição salva de vaga `approved` ou `rejected` muda o status para
   `pending` e limpa `rejection_reason`. (Vaga `pending` continua `pending`.) Regra no `CompaniesService`, com
   teste.
3. **Link do resumo semanal corrigido.** `_serialize_local_job` passa a apontar para a página pública
   `/vagas/<id>/` (hoje aponta para `/empresas/vagas/<id>/`, que não existe → 404).
4. **Painel vira a página inicial da empresa.** Login, criação/edição/remoção de vaga, `ApprovedCompanyRequiredMixin`,
   confirmação de e-mail (adapter e `ConfirmEmailView`) e o link do bot (`menu.send_company_portal_link`,
   `proactive.py`) passam a ir para `/empresas/painel/`. `/empresas/perfil/` continua existindo (dados), então
   links antigos no histórico do WhatsApp não quebram.

## Lógica com TDD

- `format_whatsapp(phone_number)` (template filter em `apps/companies/templatetags/`): `5545999990000@c.us` →
  `(45) 99999-0000` e link `https://wa.me/5545999990000`; número fixo de 8 dígitos formatado `(45) 3268-0000`;
  qualquer outro formato (ex.: `@lid`, vazio) → mostra o texto cru sem link.
- `CompaniesService.dashboard_summary(company)`: contagens (candidaturas `pending`, vagas `pending`,
  `rejected`, `approved`; removidas ignoradas), candidaturas recentes (5) e contagem de candidaturas por vaga
  (anotação, sem N+1).
- Regra de reenvio ao editar (item 2 acima).
- Selo de status por vaga, incluindo `rejected` com motivo (teste de view/template).
- Página pública de vaga: 200 para aprovada, 404 para as demais.
- Redirecionamentos do item 1 e o novo destino do item 4.

## Limpeza de código morto (na área tocada)

- `apps/users/templates/users/email_confirmed.html` — sem referência (as views usam `account/email_confirmed.html`).
- `static/img/logo-icon.png` — substituído pelo mascote.
- `account/login.html`, `account/signup.html` (+ JS de senha do signup) — ver item 1.
- `<style>` inline e `style="..."` nos templates → `portal.css`.
- Bloco de `messages` duplicado em `base_company.html`.
- Docstring de `apps/bot/handlers/local_jobs.py` diz que *candidatar* é stub "em breve" — já é a Fase 4; corrigir.
- `TIPO_CHOICES` do `JobForm` grava `estagio`/`clt` e exibe sem acento; o template de vaga reimplementa as opções à
  mão. Valores passam a ser os rótulos (`Estágio`, `CLT`, `PJ`, `Temporário`) com migração de dados das vagas
  existentes — assim painel, bot e admin mostram o mesmo texto.
- Textos sem acento nas mensagens das views ("aprovacao", "Voce nao tem permissao").
- Referência a `/accounts/signup/` em `docs/development/AWS_SES_SETUP.md` e rota em `docs/SECURITY.md`
  (rate-limit de `/accounts/login`) revisadas.

## Decisões minhas (para conferir)

- Public Sans auto-hospedada em vez de Google Fonts.
- Sem página "Minhas vagas" separada: a lista completa fica no painel (menu com 3 itens + Sair).
- Página pública de vaga não tem botão de candidatura direta: o bot não tem comando de link profundo para uma
  vaga; o botão abre o chat e a instrução diz o caminho no menu. Link profundo fica como ideia futura.
- `tipo` com rótulos como valor (migração de dados) em vez de manter slugs e traduzir na exibição.
- Rotas novas: `/empresas/painel/` e `/vagas/<id>/`.

## Fora deste trabalho

Pendências operacionais seguem na memória (`PRIVACY_CONTACT_EMAIL`, `FEEDBACK_FORM_URL`, B2, chave AWS, disco
do host). Deploy só com CI verde, via `deployment/scripts/deploy.sh`, com o usuário no campus/VPN.
