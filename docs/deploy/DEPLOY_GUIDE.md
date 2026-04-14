# CapyVagas - Guia Completo de Deploy na AWS EC2

Este guia reune todos os passos para colocar o CapyVagas em producao na AWS.

## 1. Pre-requisitos AWS

- Conta AWS com creditos disponiveis
- Instancia EC2 **t3.small** (Ubuntu 22.04 LTS) com chave SSH (.pem)
- Security group configurado (ver [SECURITY_GROUPS.md](./SECURITY_GROUPS.md))
- IAM Role com policy de S3 para backups (ver [BACKUP_S3.md](./BACKUP_S3.md))
- Bucket S3 criado para backups: `aws s3 mb s3://capyvagas-backups`

## 2. Provisionamento EC2

```bash
# Conectar via SSH
ssh -i sua-chave.pem ubuntu@SEU-IP-EC2

# Clonar repositorio (ou o setup-ec2.sh faz isso)
git clone https://github.com/ErickBonruque/CapyVagas-UTFPR.git /home/ubuntu/waha_capyvaga
cd /home/ubuntu/waha_capyvaga

# Executar script de provisionamento
sudo ./deployment/scripts/setup-ec2.sh

# Re-logar para aplicar grupo docker
exit
ssh -i sua-chave.pem ubuntu@SEU-IP-EC2
```

O `setup-ec2.sh` instala: Docker + Compose Plugin, AWS CLI v2, configura log rotation e crontab de backup.

## 3. Configurar Ambiente

```bash
cd /home/ubuntu/waha_capyvaga

# Copiar template de producao
cp .env.production.example .env

# Editar com seus valores reais
nano .env
```

**Valores obrigatorios para editar no `.env`:**

| Variavel | O que colocar |
|----------|---------------|
| `DOMAIN` | `SEU-IP-COM-HIFENS.sslip.io` (ex: `54-123-45-67.sslip.io`) |
| `ALLOWED_HOSTS` | `${DOMAIN},www.${DOMAIN},waha.${DOMAIN}` |
| `WAHA_API_KEY` | Gerar senha segura |
| `WAHA_DASHBOARD_PASSWORD` | Gerar senha segura |
| `EMAIL_HOST_USER` | SMTP username do SES (passo 6) |

```bash
# Gerar secrets seguros
./deployment/scripts/setup_secrets.sh

# Validar ambiente
./deployment/scripts/validate_environment.sh --ec2
```

## 4. Primeiro Deploy

```bash
# Subir todos os servicos
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# Aguardar health checks (1-2 min)
sleep 90

# Verificar status dos containers
docker compose ps

# Executar smoke check
./deployment/scripts/smoke-check.sh SEU-IP-COM-HIFENS.sslip.io
```

## 5. Configurar CI/CD (GitHub Actions)

O workflow `.github/workflows/deploy.yml` faz deploy automatico a cada push na branch `main`.

**Configurar GitHub Secrets no repositorio:**

1. Acesse: Settings -> Secrets and variables -> Actions
2. Adicione:
   - `EC2_HOST`: IP publico da EC2 (ex: `54.123.45.67`)
   - `EC2_USER`: `ubuntu`
   - `EC2_SSH_KEY`: Conteudo completo da chave privada SSH (`.pem`)

**Testar:** Faca um push em `main` e acompanhe em Actions.

## 6. Configurar AWS SES

Siga o guia completo em [SES_SANDBOX_EXIT.md](./SES_SANDBOX_EXIT.md):

1. Verificar email remetente no console SES
2. Solicitar saida do sandbox
3. Gerar credenciais SMTP
4. Atualizar `.env` e `secrets/email_password.txt`
5. Testar envio de email

## 7. Verificar Backup

```bash
# Executar backup manual para testar
./deployment/scripts/backup-postgres.sh

# Verificar no S3
aws s3 ls s3://capyvagas-backups/weekly/ --human-readable
```

O crontab ja esta configurado para backup semanal (domingo 02:00).
Detalhes completos em [BACKUP_S3.md](./BACKUP_S3.md).

## 8. Checklist Final

- [ ] Todos os containers rodando (`docker compose ps`)
- [ ] HTTPS funcional (`curl https://DOMAIN`)
- [ ] HTTP redireciona para HTTPS (`curl -I http://DOMAIN`)
- [ ] GitHub Actions deploy funcional (push em main)
- [ ] Backup S3 testado (`aws s3 ls s3://capyvagas-backups/weekly/`)
- [ ] SES fora do sandbox (ou em processo de aprovacao)
- [ ] Log rotation configurado (`docker inspect capyvagas_backend | grep max-size`)
- [ ] Security groups corretos (portas 22, 80, 443 apenas)

## Documentacao Relacionada

- [SECURITY_GROUPS.md](./SECURITY_GROUPS.md) — Regras de security groups EC2
- [BACKUP_S3.md](./BACKUP_S3.md) — Backup PostgreSQL para S3 e IAM Role
- [SES_SANDBOX_EXIT.md](./SES_SANDBOX_EXIT.md) — Processo de saida do sandbox SES
- `.env.production.example` — Template de variaveis de ambiente
- `deployment/scripts/setup-ec2.sh` — Provisionamento EC2
- `deployment/scripts/setup_secrets.sh` — Geracao de secrets
- `deployment/scripts/validate_environment.sh` — Validacao de ambiente
- `deployment/scripts/smoke-check.sh` — Smoke check pos-deploy
- `deployment/scripts/backup-postgres.sh` — Backup PostgreSQL
- `deployment/scripts/restore-postgres.sh` — Restauracao de backup
