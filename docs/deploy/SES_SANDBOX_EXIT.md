# AWS SES - Saida do Sandbox

## O que e o Sandbox?

Contas AWS novas tem o SES em modo sandbox. Nesse modo:
- E-mails so podem ser enviados para enderecos previamente VERIFICADOS no console AWS
- Limite de 1 e-mail por segundo e 200 e-mails por dia
- E-mails de confirmacao de registro de alunos NAO funcionam (enderecos nao verificados)

## Pre-requisitos

1. Aplicacao rodando na EC2 com HTTPS funcional (sslip.io)
2. Pelo menos um endereco de e-mail remetente verificado no SES
3. Uma URL publica acessivel (sera solicitada no formulario)

## Passo 1: Verificar E-mail Remetente

1. Acessar console AWS -> SES -> Verified identities
2. Clicar "Create identity"
3. Selecionar "Email address"
4. Inserir: `bonrqueruck@gmail.com` (ou o email remetente desejado)
5. Confirmar via link recebido no email

## Passo 2: Solicitar Saida do Sandbox

Checklist bloqueante antes do submit:
- [ ] `DEFAULT_FROM_EMAIL` na EC2 esta igual a identidade SES verificada desta fase (`bonrqueruck@gmail.com`)
- [ ] Regiao ativa do SES conferida como `us-east-1`
- [ ] `EMAIL_HOST_USER` e `secrets/email_password.txt` preparados para receber as credenciais SMTP reais

1. Acessar console AWS -> SES -> Account dashboard
2. Clicar "Request production access"
3. Preencher:
   - **Mail type:** Transactional
   - **Website URL:** `https://SEU-IP.sslip.io`
   - **Use case description:**
     ```
     Sistema academico de vagas de estagio para alunos da UTFPR
     (Universidade Tecnologica Federal do Parana). Os e-mails sao
     transacionais: confirmacao de registro, recuperacao de senha
     e notificacoes de vagas. Volume estimado: menos de 100 e-mails
     por dia. Todos os destinatarios sao alunos que se registraram
     voluntariamente no sistema.
     ```
   - **Additional contacts:** seu email pessoal
4. Submeter e aguardar resposta (ate 24h)

## Passo 3: Gerar Credenciais SMTP

1. Console AWS -> SES -> SMTP settings
2. Clicar "Create SMTP credentials"
3. Nome do usuario IAM: `iterbot-ses-smtp`
4. Anotar o SMTP username e password gerados
5. Atualizar na EC2:
   - `secrets/email_password.txt` com o SMTP password
   - `.env` com `EMAIL_HOST_USER=<SMTP username>`

## Passo 4: Testar

Na EC2, com a aplicacao rodando:

```bash
docker compose exec backend python manage.py shell -c "
from django.core.mail import send_mail
send_mail('Teste SES', 'Email de teste IterBot', None, ['seu-email@gmail.com'])
print('Email enviado!')
"
```

## Configuracao Django (.env)

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<SMTP username gerado no passo 3>
DEFAULT_FROM_EMAIL=bonrqueruck@gmail.com
```

O `EMAIL_HOST_PASSWORD` e lido de `secrets/email_password.txt`.

## Checklist pos-aprovacao

- [ ] Confirmar `ProductionAccessEnabled=true` e `SendingEnabled=true` no `sesv2 get-account` em `us-east-1`
- [ ] Atualizar `secrets/email_password.txt` com a senha SMTP real do SES (nunca commitar)
- [ ] Reiniciar `backend`, `celery_worker` e `celery_beat` apos atualizar credenciais SMTP
- [ ] Executar testes E2E (SMTP externo, confirmacao de conta, alerta offline)
- [ ] Registrar evidencias em `.planning/phases/11-aws-ses-saida-sandbox/evidence/`

## Troubleshooting

| Problema | Causa | Solucao |
|----------|-------|---------|
| "Email address is not verified" | Sandbox ativo | Aguardar aprovacao ou verificar destinatario |
| "Throttling" | Limite de envio | Aguardar aprovacao de producao |
| "Authentication failed" | Credenciais SMTP erradas | Regerar credenciais no console SES |
| "Connection refused" | Security group bloqueando | Verificar outbound permite porta 587 |
