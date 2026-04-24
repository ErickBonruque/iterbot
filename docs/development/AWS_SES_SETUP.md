# Configuração AWS SES para Envio de E-mails

Este guia descreve como configurar o Amazon Simple Email Service (SES) para envio de e-mails de confirmação e recuperação de senha em produção.

## Pré-requisitos

- Conta AWS ativa
- Acesso ao console AWS
- Domínio configurado (opcional, mas recomendado)

## Passo 1: Criar Usuário IAM para SES

1. Acesse o **IAM Console** da AWS
2. Vá em **Users** → **Add user**
3. Nome: `iterbot-ses-smtp`
4. Marque **Programmatic access**
5. Em **Permissions**, selecione **Attach existing policies directly**
6. Anexe a policy: `AmazonSESFullAccess`
7. Complete a criação e **salve as credenciais**:
   - Access Key ID
   - Secret Access Key

## Passo 2: Verificar E-mail Remetente

### Opção A: Verificar E-mail Individual (Sandbox)

1. Acesse o **Amazon SES Console**
2. Vá em **Email Addresses** → **Verify a New Email Address**
3. Digite: `***REMOVED***` (ou outro e-mail remetente desejado)
4. Acesse a caixa de entrada do e-mail e clique no link de verificação

### Opção B: Verificar Domínio Completo (Recomendado)

1. Acesse o **Amazon SES Console**
2. Vá em **Domains** → **Verify a New Domain**
3. Digite: `iterbot.utfpr.edu.br`
4. Marque **Generate DKIM Settings**
5. Copie os registros DNS fornecidos
6. Adicione os registros TXT e CNAME no gerenciador de DNS do domínio
7. Aguarde propagação (pode levar até 72h)

## Passo 3: Sair do Sandbox (Produção)

Por padrão, contas SES ficam em **sandbox mode**, que permite enviar apenas para e-mails verificados.

1. Acesse o **Amazon SES Console**
2. Vá em **Account Dashboard**
3. Clique em **Request Production Access**
4. Preencha o formulário:
   - **Mail Type**: Transactional
   - **Website URL**: URL do sistema IterBot
   - **Use case description**:
     ```
     Sistema acadêmico para divulgação de vagas de estágio da UTFPR.
     E-mails transacionais:
     - Confirmação de cadastro de alunos (@alunos.utfpr.edu.br)
     - Recuperação de senha
     - Notificações de vagas

     Volume estimado: 500 e-mails/dia
     ```
   - **Process bounces**: Yes
   - **Compliance**: Sim, todos os destinatários optaram por receber
5. Envie a solicitação
6. Aguarde aprovação (geralmente 24-48h)

## Passo 4: Obter Credenciais SMTP

1. Acesse o **Amazon SES Console**
2. Vá em **SMTP Settings**
3. Clique em **Create My SMTP Credentials**
4. Salve o **SMTP Username** e **SMTP Password** gerados

**Região e Endpoint:**
- Região: `us-east-1` (ou a região escolhida)
- SMTP Endpoint: `email-smtp.us-east-1.amazonaws.com`
- Porta: `587` (TLS) ou `465` (SSL)

## Passo 5: Configurar Variáveis de Ambiente

### Desenvolvimento Local

Em desenvolvimento, mantenha o console backend (padrão):

```bash
# .env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### Produção (Docker)

Atualize as variáveis de ambiente no servidor:

```bash
# .env (produção)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<SMTP_USERNAME>
EMAIL_HOST_PASSWORD=<SMTP_PASSWORD>
DEFAULT_FROM_EMAIL=***REMOVED***
```

**Importante:** Use Docker Secrets para `EMAIL_HOST_PASSWORD`:

```bash
# No servidor
echo "sua_senha_smtp" | docker secret create email_password -

# docker-compose.yml já está configurado para ler secrets
```

## Passo 6: Testar Envio

### Via Django Shell

```bash
docker-compose exec web python manage.py shell
```

```python
from django.core.mail import send_mail

send_mail(
    'Teste IterBot',
    'E-mail de teste do sistema.',
    '***REMOVED***',
    ['seu.email@alunos.utfpr.edu.br'],
    fail_silently=False,
)
```

### Via Cadastro Real

1. Acesse `/accounts/signup/`
2. Cadastre-se com um e-mail válido @alunos.utfpr.edu.br
3. Verifique se o e-mail de confirmação chegou

## Monitoramento

### Métricas no SES Console

- **Sending Statistics**: Taxa de envio, bounces, complaints
- **Reputation Dashboard**: Reputação do remetente
- **Suppression List**: E-mails bloqueados

### Configurar SNS para Bounces (Opcional)

1. Crie um tópico SNS para notificações
2. Configure feedback em **Email Feedback**
3. Vincule bounces e complaints ao tópico

## Troubleshooting

### E-mails não chegam

1. Verifique se o e-mail remetente está verificado
2. Confirme que saiu do sandbox mode
3. Confira se as credenciais SMTP estão corretas
4. Verifique os logs do Django:
   ```bash
   docker-compose logs web | grep mail
   ```

### Erro: "Email address is not verified"

- O e-mail remetente (`DEFAULT_FROM_EMAIL`) precisa estar verificado no SES
- Se estiver no sandbox, o destinatário também precisa estar verificado

### Taxa de rejeição alta

- Verifique DKIM e SPF do domínio
- Revise conteúdo dos e-mails (evite spam triggers)
- Monitore a suppression list

## Custos

- **Primeiros 62.000 e-mails/mês**: Gratuitos (com EC2)
- **Após limite**: $0.10 por 1.000 e-mails

Para um sistema com ~500 alunos cadastrando/mês, o custo será **$0**.

## Segurança

✅ **Boas práticas implementadas:**
- Credenciais via variáveis de ambiente (não hardcoded)
- Docker Secrets para senhas em produção
- TLS/SSL para conexão SMTP
- Remetente verificado no SES (identidade de e-mail ou dominio)

---

**Última atualização:** 2026-04-12
**Responsável:** Fase 2 - Autenticação de Alunos
