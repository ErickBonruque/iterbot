# Deploy

Guias de deploy e configuracao de infraestrutura.

## Guias

| Arquivo | Descricao |
|---------|-----------|
| [MIGRACAO-GOSH-UTFPR.md](MIGRACAO-GOSH-UTFPR.md) | **Plano vigente** — migração para a VM própria da UTFPR (`gosh`) |
| [MIGRACAO-DOMINIO-FIXO.md](MIGRACAO-DOMINIO-FIXO.md) | (histórico/supersedido) plano de host compartilhado |
| [EMAIL_RUNBOOK.md](EMAIL_RUNBOOK.md) | Runbook operacional do e-mail (rotação, revogação, troubleshooting) |

> ℹ️ O deploy original em AWS EC2 foi **descomissionado** (ver
> [ADR-004](../architecture/adr/adr-004-ec2-docker-compose.md) e
> [ADR-005](../architecture/adr/adr-005-migracao-host-gosh-utfpr.md)). Os guias
> específicos de AWS (S3, Security Groups, SES sandbox) foram removidos do
> repositório; scripts legados de AWS ainda existem em `deployment/scripts/`
> mas não fazem parte do fluxo atual.

## Infraestrutura

- **Plataforma:** VM UTFPR `gosh.sh.utfpr.edu.br` (Ubuntu 22.04, 1 vCPU / 1.8 GB RAM / 19 GB disco), gerida pela COGETI via Ansible
- **Container:** Docker Compose
- **Proxy:** Traefik v3.6 (TLS Let's Encrypt + BasicAuth)
- **Dominio:** `gosh.sh.utfpr.edu.br` (producao)
- **Rede:** SSH (22) filtrado de fora da UTFPR — deploy exige campus ou VPN institucional; 80/443 públicas
- **Custo:** hospedagem institucional (sem custo AWS)

## Guia de Deploy em Producao

### Requisitos

- VM com Docker Engine + Docker Compose instalados
- Acesso SSH ao host (na rede da UTFPR ou via VPN institucional)
- Domínio com registro A apontando para o host (para o TLS via Let's Encrypt)

### Passo a passo

1. **Clonar o repositório no host:**
   ```bash
   git clone https://github.com/ErickBonruque/iterbot.git && cd iterbot
   ```

2. **Configurar secrets:**
   ```bash
   bash deployment/scripts/setup_secrets.sh
   bash deployment/scripts/setup-htpasswd.sh
   ```

3. **Configurar .env:**
   ```bash
   cp .env.production.example .env
   # Editar .env com valores reais (DOMAIN, ALLOWED_HOSTS, PORTAL_BASE_URL, e-mail)
   ```

4. **Validar ambiente:**
   ```bash
   bash deployment/scripts/validate_environment.sh
   ```

5. **Subir servicos e semear dados:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
   docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py migrate
   docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend python manage.py seed_courses
   ```

6. **Verificar deploy:**
   ```bash
   bash deployment/scripts/smoke-check.sh gosh.sh.utfpr.edu.br
   ```

Para o passo a passo completo da migração (limites de memória, pareamento do
WhatsApp, TLS), ver [MIGRACAO-GOSH-UTFPR.md](MIGRACAO-GOSH-UTFPR.md).

## Hardening de Segurança

### BasicAuth (Traefik)

O Django Admin/Portal e protegido por BasicAuth via Traefik middleware:

- **Django Admin/Portal:** `https://${DOMAIN}/admin/` e `https://${DOMAIN}/portal/` — requer `admin-auth`
- **WAHA Dashboard:** servico interno, sem rota publica — acesso via tunel SSH:
  `ssh -L 3000:localhost:3000 <usuario>@<host>` e abrir `http://localhost:3000/dashboard`

Para configurar usuarios BasicAuth:
```bash
bash deployment/scripts/setup-htpasswd.sh
```

### Rede do host

A rede é gerida pela COGETI/UTFPR: apenas as portas 80/443 são públicas; a
porta 22 (SSH) é filtrada de fora da rede institucional. Não há Security Group
para configurar (diferente do deploy AWS antigo).

## Backup e Restauração

- **Backup diario:** `backup-postgres.sh` (dump local do PostgreSQL via crontab)
- **Disk check:** `check-disk-space.sh` (alerta por e-mail se uso >80%)
- Os scripts de backup/restore para S3 (`check-backup.sh`, `restore-test.sh`,
  `restore-postgres.sh`) pertencem ao deploy AWS antigo e exigem adaptação
  antes de uso no host atual.

## Monitoramento e Alertas

Os alertas sao enviados pelo provider de e-mail configurado em `EMAIL_PROVIDER`
(Resend, Brevo, AWS SES, SMTP) — ver `infra/email/factory.py` e
[EMAIL_RUNBOOK.md](EMAIL_RUNBOOK.md). O destinatário dos alertas é definido em
`ALERT_EMAIL` (fallback: `DEFAULT_FROM_EMAIL`).

## CI/CD

O repositório mantém CI no GitHub Actions (`.github/workflows/ci.yml`): lint
(ruff), testes (pytest + coverage) e varredura de segurança (pip-audit +
Trivy) em cada PR e push.

**Deploy é manual**: como o SSH do host é filtrado de fora da UTFPR, o GitHub
Actions não alcança a porta 22. Opções registradas em
[MIGRACAO-GOSH-UTFPR.md](MIGRACAO-GOSH-UTFPR.md): self-hosted runner na rede
institucional, deploy manual no campus ou VPN. O workflow antigo de deploy
para AWS (via SSM) foi removido junto com a EC2.

### Rollback

No host:
```bash
bash deployment/scripts/rollback.sh [--commit HASH]
```

O rollback faz checkout do commit, rebuild dos containers, e executa smoke-check.

## Solução de Problemas

| Problema | Solucao |
|----------|---------|
| WAHA sem resposta | Verificar container: `docker compose ps waha` |
| SSL cert expirado | Verificar logs Traefik: `make logs-traefik` |
| Backup falhou | Verificar log: `tail /var/log/iterbot-backup.log` |
| Disco cheio | Verificar uso: `df -h` e `docker system df` |
| Rollback necessario | `bash deployment/scripts/rollback.sh` |
