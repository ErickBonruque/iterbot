# Deploy

Guias de deploy e configuracao de infraestrutura.

## Guias

| Arquivo | Descricao |
|---------|-----------|
| [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md) | Guia completo de deploy |
| [EMAIL_RUNBOOK.md](EMAIL_RUNBOOK.md) | Runbook operacional do email Resend (rotacao, revogacao, troubleshooting) |
| [BACKUP_S3.md](BACKUP_S3.md) | Backup para S3 |
| [SECURITY_GROUPS.md](SECURITY_GROUPS.md) | Grupos de seguranca AWS |
| [SES_SANDBOX_EXIT.md](SES_SANDBOX_EXIT.md) | Sair do sandbox SES |
| [COST-COMPARISON.md](COST-COMPARISON.md) | Comparativo de custos de hospedagem |

## Infraestrutura

- **Plataforma:** AWS EC2 (t3.small)
- **Container:** Docker Compose
- **Proxy:** Traefik v3.6
- **Dominio:** sslip.io (producao — Let's Encrypt TLS)
- **Custo mensal estimado:** ~$16.30 (ver [COST-COMPARISON.md](COST-COMPARISON.md))

## Production Deployment Guide

### Requisitos

- EC2 instance (t3.small, us-east-1)
- AWS CLI configurado com IAM Role ou credenciais
- Docker e Docker Compose instalados

### Passo a passo

1. **Provisionar EC2:**
   ```bash
   sudo bash deployment/scripts/setup-ec2.sh
   ```

2. **Configurar secrets:**
   ```bash
   bash deployment/scripts/setup_secrets.sh
   bash deployment/scripts/setup-htpasswd.sh
   ```

3. **Configurar .env:**
   ```bash
   cp .env.production.example .env
   # Editar .env com valores reais
   ```

4. **Validar ambiente:**
   ```bash
   bash deployment/scripts/validate_environment.sh --ec2
   ```

5. **Subir servicos:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
   ```

6. **Verificar deploy:**
   ```bash
   bash deployment/scripts/smoke-check.sh SEU-IP.sslip.io
   ```

## Security Hardening

### BasicAuth (Traefik)

O WAHA Dashboard e Django Admin/Portal sao protegidos por BasicAuth via Traefik middleware:

- **WAHA Dashboard:** `https://waha.${DOMAIN}/dashboard` — requer `waha-auth`
- **Django Admin/Portal:** `https://${DOMAIN}/admin/` e `https://${DOMAIN}/portal/` — requer `admin-auth`

Para configurar usuarios BasicAuth:
```bash
bash deployment/scripts/setup-htpasswd.sh
```

### Security Group

O Security Group da EC2 deve permitir apenas as portas 22, 80 e 443:

```bash
bash deployment/scripts/harden-security-group.sh
```

Este script remove as portas 3000, 8000 e 8080 do acesso publico de forma idempotente.

## Backup & Restore

- **Backup diario:** crontab as 02:00 — `backup-postgres.sh`
- **Backup check:** crontab as 03:00 — `check-backup.sh` (alerta via SES se falhar)
- **Disk check:** crontab a cada 6h — `check-disk-space.sh` (alerta via SES se >80%)
- **Restore test mensal:** crontab dia 1 as 04:00 — `restore-test.sh`
- **Retencao:** S3 lifecycle policy — 30 dias para `daily/`, 90 dias para `weekly/`

Aplicar lifecycle policy:
```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket iterbot-utfpr-backups \
  --lifecycle-configuration file://deployment/config/s3-lifecycle.json
```

## Monitoring & Alerts

Os alertas sao enviados pelo provider de e-mail configurado em `EMAIL_PROVIDER` (Resend, Brevo, AWS SES, SMTP) — ver `infra/email/factory.py` e [EMAIL_RUNBOOK.md](EMAIL_RUNBOOK.md). Scripts shell de alerta no host usam SMTP via SES por padrao quando `EMAIL_PROVIDER=ses`.

| Alerta | Script | Frequencia | Condicao |
|--------|--------|------------|----------|
| Backup falhou | `check-backup.sh` | Diario (03:00) | Backup nao encontrado em S3 ou tamanho suspeito |
| Disco cheio | `check-disk-space.sh` | A cada 6h | Uso de disco acima de 80% (configuravel via `DISK_THRESHOLD`) |

## CI/CD Pipeline

### Deploy Workflow (`.github/workflows/deploy.yml`)

O deploy workflow tem dois gates obrigatorios:

1. **CI Gate** — lint (ruff check), format check (ruff format --check), e testes (pytest)
2. **Deploy** — so executa apos CI passar (`needs: ci`)

### Rollback

Para fazer rollback via GitHub Actions:
1. Ir em Actions > Deploy > Run workflow
2. Marcar `rollback = true`
3. Opcionalmente informar o commit hash

Ou manualmente na EC2:
```bash
bash deployment/scripts/rollback.sh [--commit HASH]
```

O rollback faz checkout do commit, rebuild dos containers, e executa smoke-check.

## Cost

Ver [COST-COMPARISON.md](COST-COMPARISON.md) para comparativo detalhado.

**Resumo:** EC2 t3.small on-demand ~$16.30/mo. Reserved Instance 1yr ~$10.79/mo.

## Troubleshooting

| Problema | Solucao |
|----------|---------|
| WAHA sem resposta | Verificar container: `docker compose ps waha` |
| SSL cert expirado | Verificar logs Traefik: `make logs-traefik` |
| Backup falhou | Verificar log: `tail /var/log/iterbot-backup.log` |
| Disco cheio | Verificar uso: `df -h` e `docker system df` |
| Deploy falhou | Verificar CI logs no GitHub Actions |
| Rollback necessario | `bash deployment/scripts/rollback.sh` |