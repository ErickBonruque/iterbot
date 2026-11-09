# Roteiro de teste ponta a ponta (antes de convidar alunos)

Teste manual do fluxo completo em **produção** (gosh), com um número de WhatsApp
**externo** (não o do bot) e um e-mail **@alunos.utfpr.edu.br real**. Marque cada
passo; se algo falhar, pare e anote o que está em [Se algo falhar](#se-algo-falhar).

Quem executa precisa de: um celular com WhatsApp (o "aluno"), acesso a uma caixa
@alunos, um e-mail qualquer para a "empresa" (pode ser Gmail), e o login do
`/admin` (BasicAuth + superusuário — `docs/CREDENTIALS.local.md`).

## 0. Pré-requisitos (no host, uma vez)

- [ ] Deploy feito com `deployment/scripts/deploy.sh` e smoke-check verde
- [ ] `PRIVACY_CONTACT_EMAIL` definido no `.env` (aparece no texto de privacidade)
- [ ] Coleta de vagas online rodou depois do deploy (admin → Vagas do Dia → botão "Buscar Vagas Agora", ou espera as 07:00)
- [ ] `/admin/status-bot/` mostra a sessão `iterbot` **WORKING**
- [ ] O número do aluno de teste **não** tem perfil antigo (admin → *User profiles* → buscar pelo número; se existir, apague para testar o primeiro contato)

## 1. Empresa e vaga local (navegador)

| # | Ação | Esperado |
|---|---|---|
| 1.1 | Abrir `https://gosh.sh.utfpr.edu.br/empresas/` | Vai direto para a tela de login **sem** pedir usuário/senha do navegador (BasicAuth saiu do portal) |
| 1.2 | "Cadastrar" → criar conta com o e-mail da empresa | Mensagem pedindo confirmação de e-mail |
| 1.3 | Abrir o e-mail de confirmação e clicar no link | Conta confirmada (olhe também o spam) |
| 1.4 | Entrar e preencher os dados da empresa (`/empresas/criar/`) | Empresa criada, aguardando aprovação |
| 1.5 | Tentar `/empresas/vagas/nova/` antes da aprovação | Volta para o perfil com aviso de empresa ainda não aprovada |
| 1.6 | No `/admin` (aqui o navegador **deve** pedir o BasicAuth): Empresas → aprovar | Status APPROVED |
| 1.7 | No portal: criar uma vaga cuja **área** seja a do curso que o aluno vai escolher (ou sem área = todas) | Vaga criada (rascunho) |
| 1.8 | No `/admin`: Vagas → aprovar a vaga | Status APPROVED |
| 1.9 | Errar a senha da empresa 5 vezes seguidas no `/empresas/login/` e depois acertar | 6ª tentativa recusada; volta a funcionar após ~5 min |

## 2. Aluno no WhatsApp

| # | Ação (mensagem enviada ao bot) | Esperado |
|---|---|---|
| 2.1 | `oi` | Texto **🔒 Antes de começar: privacidade** com o e-mail de contato e as opções 1/2 — **não** o menu |
| 2.2 | `quero vagas` | Repete o texto de privacidade |
| 2.3 | `2` | "Tudo bem! Apaguei esta conversa..." — no admin o perfil do número sumiu |
| 2.4 | `oi` de novo, depois `1` | "✅ Obrigado! Seu aceite foi registrado." e o menu (1 Cadastro/Login de aluno, 2 empresa). No admin: perfil com *privacy_consent_at* preenchido |
| 2.5 | `1` | Pede o **RA** |
| 2.6 | o RA (ex.: `a1234567`) | Pede o **e-mail institucional** — **não** pede senha |
| 2.7 | `fulano@gmail.com` | Recusa: só @alunos.utfpr.edu.br |
| 2.8 | o e-mail @alunos real | "📧 Confirmação de E-mail — enviamos um link para ..." |
| 2.9 | `reenviar` | "E-mail de confirmação reenviado!" (chega um 2º e-mail; vale o link mais novo) |
| 2.10 | Abrir o e-mail (olhar spam/quarentena) e clicar no link | Página de e-mail confirmado; o bot manda mensagem avisando que o cadastro foi confirmado |
| 2.11 | `menu` | Menu autenticado com o RA: 1 Buscar Vagas · 2 Ver Review · 3 Vagas do meu curso · 4 Sair · 5 Trocar curso |
| 2.12 | `1` → número do curso → número de um termo | Lista de vagas online daquele termo (região/remoto). Se vier vazio, anote curso e termo |
| 2.13 | `menu` → `2` (Ver Review) | "🔎 Buscando vagas..." e um resumo com vagas locais e online do curso |
| 2.14 | `menu` → `3` (Vagas do meu curso) | A vaga criada no passo 1.7 aparece na lista |
| 2.15 | número da vaga | Detalhe (título, empresa, descrição, requisitos) e "Digite *candidatar*" |
| 2.16 | `candidatar` → período → habilidades → link do LinkedIn (ou `pular`) | Pede os 3 itens do mini-perfil, um por vez |
| 2.17 | `confirmar` | "🎉 Candidatura enviada!" |
| 2.18 | `3` → mesma vaga → `candidatar` | "✅ Você já se candidatou a esta vaga." |
| 2.19 | `parar` / depois `retomar` | "🔕 ... não vai mais receber o resumo semanal" / "🔔 ... voltará a receber" |
| 2.20 | `4` (Sair) e depois `1` → mesmo RA | Entra direto ("Bem-vindo de volta"), sem pedir e-mail |

## 3. Empresa recebe a candidatura

| # | Ação | Esperado |
|---|---|---|
| 3.1 | Caixa de e-mail da empresa | E-mail da candidatura com nome da vaga e mini-perfil do aluno (olhe spam) |
| 3.2 | Portal → **Candidaturas** (`/empresas/candidaturas/`) | O aluno aparece com período, habilidades e link |
| 3.3 | Mudar o status da candidatura | Status salvo |

## 4. Conferências no admin (depois do teste)

- [ ] Logs de Interação do número de teste: **nenhuma** senha em texto (o fluxo de aluno nem pede mais)
- [ ] Perfil do aluno: `email_verified` e autenticado marcados; `privacy_consent_version` preenchido
- [ ] Bot Action Logs sem erros novos (`status=ERROR`) no horário do teste

## Se algo falhar

Anote e me mande:

1. **Número do passo** e a hora exata (com minuto).
2. O que você mandou e o que o bot respondeu (print da conversa).
3. No host (campus/VPN), a saída de:
   ```bash
   cd ~/iterbot
   docker logs --since 15m iterbot_backend 2>&1 | tail -80
   docker logs --since 15m iterbot_celery_worker 2>&1 | tail -80
   ```
   (os logs não têm senhas; se tiver e-mail de aluno, pode mandar mesmo assim ou mascarar).

Não precisa tentar consertar no host — eu corrijo no código, a CI roda e você faz o
`deploy.sh` de novo.
