# Email Runbook — Brevo Migration

Guia operacional para o provider de email do IterBot UTFPR.
Cobre rotação de chave, revogação de emergência, troubleshooting e rollback.

> **Migração ativa:** Em abril/2026 migramos de Resend/SES para **Brevo** (ex-Sendinblue) por causa da ausência de domínio próprio. Brevo permite envio para qualquer destinatário com apenas o *sender* verificado, 300 e-mails/dia grátis. Todo o conteúdo anterior deste runbook referente a Resend permanece válido trocando `resend`→`brevo` e `RESEND_API_KEY`→`BREVO_API_KEY`.
>
> **Caminho unificado:** `apps/users/adapters.py` (UTFPRAccountAdapter) intercepta 100% dos e-mails do allauth (signup, confirmation, password reset) e os envia via `infra/email/factory.py`, que resolve o provider por `EMAIL_PROVIDER`. O mesmo factory é usado pelo bot WhatsApp. Não existe mais caminho que passe direto por `django.core.mail.send_mail` para fluxos de produção.

---

## Sumário

- [Escopo e Providers](#escopo-e-providers)
- [Pre-Checks Operacionais](#pre-checks-operacionais)
- [Walkthrough de Validação E2E](#walkthrough-de-validação-e2e)
- [Rotação de BREVO_API_KEY](#rotação-de-brevo_api_key)
- [Revogação de Chave Comprometida](#revogação-de-chave-comprometida)
- [Troubleshooting](#troubleshooting)
- [Rollback Operacional](#rollback-operacional)

---

## Escopo e Providers

| Variável | Valor Esperado em Produção | Descrição |
|----------|---------------------------|-----------|
| `EMAIL_PROVIDER` | `brevo` | Provider principal (antes: `resend`/`ses`) |
| `EMAIL_FALLBACK_PROVIDER` | vazio ou `console` | Provider de fallback automático |
| `BREVO_API_KEY` | Docker secret `brevo_api_key` (arquivo `secrets/brevo_api_key.txt`) | Chave de API Brevo |
| `DEFAULT_FROM_EMAIL` | Sender verificado no dashboard Brevo | `bonruque@alunos.utfpr.edu.br` (DMARC ok) |

> **Pré-requisito Brevo:** o endereço em `DEFAULT_FROM_EMAIL` precisa estar cadastrado em *Senders, Domains & Dedicated IPs → Senders* no dashboard Brevo e verificado via link. Sem isso, a API devolve `brevo_sender_not_verified`.

### Rotação de BREVO_API_KEY

1. Gere uma nova chave em https://app.brevo.com/settings/keys/api
2. No EC2: `echo "<NOVA_CHAVE>" > /home/ubuntu/iterbot/secrets/brevo_api_key.txt`
3. `sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate backend celery_worker celery_beat`
4. Valide com um envio transacional (ver seção *Walkthrough*).
5. Delete a chave antiga no dashboard Brevo.

Referência completa de variáveis: [CONFIGURATION.md](../configuration/CONFIGURATION.md)

---

## Pre-Checks Operacionais

Execute antes de qualquer walkthrough ou rotação de chave:

```bash
# 1. Confirmar que o componente email está healthy
curl -s https://<dominio>/health/ | python3 -m json.tool | grep -A5 '"email"'

# 2. Confirmar provider ativo nos logs recentes
docker compose logs backend --since 5m 2>&1 | grep "email_send_success\|email_provider"

# 3. Confirmar que a chave está configurada (sem expor o valor)
docker exec backend env | grep -c "RESEND_API_KEY" && echo "chave presente"
```

Resultado esperado de `/health/`:
```json
"email": {
  "status": "healthy",
  "provider": "resend"
}
```

---

## Walkthrough de Validação E2E

Use este checklist para validar os fluxos transacionais em produção.

### Cenário VAL-01: Confirmação de Conta

1. Criar ou usar uma conta `@alunos.utfpr.edu.br` ainda não confirmada
2. Disparar o fluxo de confirmação (via bot WhatsApp ou portal)
3. Confirmar que o email chegou na caixa do destinatário
4. Clicar no link de confirmação e verificar que a conta foi ativada
5. Confirmar log estruturado: `docker compose logs backend 2>&1 | grep "email_send_success"`

### Cenário VAL-02: Recuperação de Conta

1. Usar uma conta UTFPR válida e confirmada
2. Disparar o fluxo de recuperação de senha
3. Confirmar que o email de recuperação chegou
4. Clicar no link e redefinir a senha com sucesso
5. Confirmar log estruturado: `docker compose logs backend 2>&1 | grep "email_send_success"`

### Registro de Evidências

Preencher [43-01-EVIDENCE.md](../../.planning/phases/43-production-validation-runbook/43-01-EVIDENCE.md) com:
- Timestamps de início e fim de cada cenário
- Message-ID recebido (mascarado se necessário)
- Snapshot do componente `email` em `/health/`
- Trecho de log relevante (mascarar destinatários: `j***@domain.com`)

---

## Rotação de RESEND_API_KEY

Use este procedimento durante rotação de rotina (recomendado: a cada 90 dias).

### 1. Gerar nova chave no painel Resend

1. Acessar [resend.com/api-keys](https://resend.com/api-keys)
2. Criar nova chave com escopo mínimo necessário (envio de emails)
3. Copiar a nova chave — ela não será exibida novamente

### 2. Atualizar o secret na EC2

```bash
# Na EC2 — atualizar o arquivo de secret
echo "re_nova_chave_aqui" | sudo tee /run/secrets/resend_api_key > /dev/null
sudo chmod 400 /run/secrets/resend_api_key

# Reiniciar apenas o backend para carregar o novo secret
docker compose restart backend worker
```

### 3. Verificar que a nova chave está funcionando

```bash
# Checar health endpoint
curl -s https://<dominio>/health/ | python3 -m json.tool | grep -A5 '"email"'

# Confirmar log de sucesso após restart
docker compose logs backend --since 2m 2>&1 | grep "email_send_success\|email_health"
```

### 4. Revogar a chave antiga

1. Voltar ao painel Resend
2. Localizar a chave anterior e clicar em **Revoke**
3. Confirmar que `/health/` continua `healthy` com a nova chave

---

## Revogação de Chave Comprometida

Use este procedimento se a `RESEND_API_KEY` foi exposta (log, commit, incidente).

### 1. Revogar imediatamente no painel Resend

1. Acessar [resend.com/api-keys](https://resend.com/api-keys) **agora**
2. Revogar a chave comprometida — o efeito é imediato
3. O sistema passa a usar fallback (`EMAIL_FALLBACK_PROVIDER`) automaticamente

### 2. Confirmar que o fallback está ativo

```bash
# Log de fallback deve aparecer após revogação
docker compose logs backend --since 5m 2>&1 | grep "email_fallback_triggered\|email_fallback_provider_unavailable"

# Health endpoint deve indicar provider primário unhealthy + fallback
curl -s https://<dominio>/health/ | python3 -m json.tool | grep -A10 '"email"'
```

### 3. Gerar e configurar nova chave (seguir procedimento de Rotação acima)

### 4. Pós-incidente

- Verificar em que sistemas/logs a chave comprometida apareceu
- Rotacionar qualquer outro secret que possa ter sido exposto no mesmo contexto
- Registrar o incidente com timestamps e ações tomadas

---

## Troubleshooting

### Email não está sendo entregue

```bash
# 1. Checar status do provider
curl -s https://<dominio>/health/ | python3 -m json.tool

# 2. Checar logs recentes de falha
docker compose logs backend --since 30m 2>&1 | grep "email_send_failure\|email_send_error\|email_fallback"

# 3. Checar se a chave está configurada
docker exec backend env | grep RESEND_API_KEY | wc -c
```

**Se `/health/` retorna `email.status: unhealthy`:**
- Provider principal com problema — verificar painel Resend
- Se `email_fallback_triggered` aparecer nos logs, fallback ativou automaticamente
- Se fallback também falhar, verificar `EMAIL_FALLBACK_PROVIDER` e credenciais SES/SMTP

### Healthcheck retorna `unhealthy` mas emails chegam

O healthcheck faz uma chamada real à API Resend para verificar conectividade. Pode falhar por:
- Rate limiting temporário da API Resend
- Timeout de rede entre EC2 e Resend

Aguardar 1–2 minutos e verificar novamente. Se persistir, seguir fluxo de troubleshooting acima.

### Fallback não está sendo ativado

```bash
# Verificar se EMAIL_FALLBACK_PROVIDER está configurado
docker exec backend env | grep EMAIL_FALLBACK_PROVIDER

# Verificar logs de configuração de fallback
docker compose logs backend --since 10m 2>&1 | grep "email_fallback_provider"
```

Se `EMAIL_FALLBACK_PROVIDER` estiver vazio, o sistema falha graciosamente sem fallback.
Para ativar, configurar a variável e reiniciar: `docker compose restart backend worker`.

### Log `email_fallback_provider_unknown`

Indica que `EMAIL_FALLBACK_PROVIDER` foi configurado com um valor inválido.
Valores aceitos: `resend`, `ses`, `smtp`, `console`.

```bash
# Verificar qual valor está configurado
docker exec backend env | grep EMAIL_FALLBACK_PROVIDER
```

Corrigir o valor e reiniciar o backend.

---

## Rollback Operacional

### Rollback para SES (provider legado)

Se necessário reverter para AWS SES temporariamente:

```bash
# Na EC2 — atualizar variáveis de ambiente
# Editar .env ou secrets conforme estrutura do projeto
# EMAIL_PROVIDER=ses
# EMAIL_BACKEND=django_ses.SESBackend

docker compose restart backend worker

# Verificar
curl -s https://<dominio>/health/ | python3 -m json.tool | grep -A5 '"email"'
```

### Rollback de código (via GitHub Actions)

Para reverter para um commit anterior completo:

```bash
# Via script de rollback
bash deployment/scripts/rollback.sh --commit <HASH>
```

Ou via GitHub Actions > Deploy > Run workflow com `rollback = true`.

Referência: [DEPLOYMENT.md](DEPLOYMENT.md)

---

*Runbook criado: 2026-04-23*
*Milestone: v1.3 Resend Email Migration*
*Requisito: VAL-03*
