# Migração para o host próprio da UTFPR — `gosh.sh.utfpr.edu.br`

> Plano **vigente** de migração. Substitui [`MIGRACAO-DOMINIO-FIXO.md`](MIGRACAO-DOMINIO-FIXO.md)
> (host compartilhado, nunca executado). Decisão registrada em
> [ADR-005](../architecture/adr/adr-005-migracao-host-gosh-utfpr.md).

## Resumo da decisão

Migrar o IterBot da EC2 AWS para uma **VM dedicada da UTFPR**:

| Item | Valor |
|------|-------|
| Host | `gosh.sh.utfpr.edu.br` / `200.134.22.219` |
| SO | Ubuntu 22.04 LTS (kernel 5.15) |
| Recurso | **1 vCPU / 1.8 GB RAM** (+3.8 GB swap) / **19 GB disco** |
| Gestão | COGETI/UTFPR via Ansible |
| Acesso | SSH `<usuario-institucional>@200.134.22.219` (senha, grupo sudo) |
| Domínio | `gosh.sh.utfpr.edu.br` (1 registro A) |
| Dedicado? | Sim — **não** compartilhado com outro bot |

## Decisões travadas

1. **Host dedicado** (`.219`/`gosh`), não o compartilhado `.218`/`chat-universitario` do plano antigo.
2. **Domínio:** `gosh.sh.utfpr.edu.br`.
3. **Recurso é o teto disponível** (1.8 GB RAM). Objetivo era compartilhar uma VM de 2 GB com outro bot; conseguiu-se esta VM dedicada e este é o máximo. A stack precisa ser ajustada para caber (limites de memória, WAHA sob controle).
4. **Dados a preservar = somente cursos e termos de busca**, e estes **já estão versionados no repositório** (`apps/courses/fixtures/courses_terms.json` + `seed_courses`). **Não** há migração de banco da EC2 antiga.
5. **Empresas, alunos e vagas recomeçam do zero** — eram apenas testes; o software não estava em produção.
6. **SSH filtrado de fora da UTFPR:** deploy exige campus ou VPN institucional. 80/443 são públicas.

## Estado atual (2026-07-01)

- [x] EC2 antiga (conta `capyvagas`) **parada** (stopped), EBS preservado.
- [x] Recon do host `gosh` feita: VM crua, sem Docker/orquestrador.
- [x] **Gate 1 — Docker instalado:** Docker Engine 29.6.1 + Compose v5.2.0 (repositório oficial), rotação de log (`json-file` 10m×3), `live-restore`, usuário no grupo `docker`.
- [ ] Gate 2/3 — Ajustar `docker-compose.prod.yml` ao recurso + `.env` de produção (domínio `gosh`, `ALLOWED_HOSTS`, `PORTAL_BASE_URL`).
- [ ] Gate 4 — Semear cursos/termos (`loaddata courses_terms.json` ou `seed_courses`).
- [ ] Gate 5 — Subir stack, emitir TLS, parear WhatsApp (QR), smoke-check.
- [ ] Descomissionar EC2 antiga (terminar instância; confirmar antes que não houve edição de termos só em produção).

## Passo a passo

### 1. Preparar código e secrets no host

```bash
# No gosh (via SSH, estando na rede da UTFPR):
git clone https://github.com/ErickBonruque/iterbot.git && cd iterbot
# Gerar/repor secrets/ (nunca versionados) — ver deployment/scripts/setup_secrets.sh
```

### 2. Configurar `.env` de produção

```bash
DOMAIN=gosh.sh.utfpr.edu.br
ALLOWED_HOSTS=gosh.sh.utfpr.edu.br,backend
PORTAL_BASE_URL=https://gosh.sh.utfpr.edu.br
WAHA_URL=http://waha:3000
WHATSAPP_HOOK_URL=http://backend:8000/webhook/
```

### 3. Ajustar a stack ao recurso (1.8 GB RAM) — Gate 3

Definir `mem_limit`/reservations no `docker-compose.prod.yml`, priorizando:
- **WAHA** (Chromium headless) — maior consumidor; limitar e monitorar.
- Postgres e Redis enxutos (`shared_buffers` baixo, `maxmemory` no Redis).
- Contar com os 3.8 GB de swap como folga, sem depender dele em regime.

### 4. Subir e semear

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db
docker compose ... run --rm backend python manage.py migrate
docker compose ... run --rm backend python manage.py loaddata courses_terms.json  # cursos + termos
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 5. TLS + WhatsApp

- Traefik emite Let's Encrypt via HTTP-01 (80/443 públicas — confirmar liberação real ao subir).
- Parear WhatsApp escaneando o QR via túnel: `ssh -L 3000:localhost:3000 <usuario>@200.134.22.219` → `http://localhost:3000/dashboard`.

### 6. Validar e descomissionar

- `bash deployment/scripts/smoke-check.sh gosh.sh.utfpr.edu.br`.
- Mensagens entrando/saindo OK → **terminar** a EC2 antiga (`aws ec2 terminate-instances --profile capyvagas ...`).

## Deploy contínuo (pós-virada)

SSH filtrado de fora ⇒ GitHub Actions não alcança a porta 22. Opções:
- **Self-hosted runner** dentro da rede da UTFPR;
- **Deploy manual** via SSH no campus (`git pull` + `ec2_deploy.sh`);
- **VPN institucional** (confirmar com a COGETI) — habilita SSH de qualquer lugar.

O workflow de deploy AWS (`.github/workflows/deploy.yml`, via SSM) foi **removido** do repositório junto com o descomissionamento da EC2 — até a definição de runner/VPN, o deploy é manual via SSH.
