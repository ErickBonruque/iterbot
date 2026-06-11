# Migração para Domínio Fixo — `chat-universitario.sh.utfpr.edu.br`

## Contexto

A UTFPR forneceu o domínio fixo `chat-universitario.sh.utfpr.edu.br`, que
**já possui registro A apontando para `200.134.22.218`** — um servidor da
própria universidade com acesso SSH (senha institucional). Ou seja: o domínio
não aponta para a EC2 atual da AWS.

Isso abre dois caminhos, descritos abaixo. **A decisão depende de confirmar
com a orientadora/TI qual é a intenção ao fornecer o servidor.**

### O que já está pronto no repositório (vale para os dois caminhos)

- WAHA virou serviço **interno** em produção: sem rota Traefik, sem
  subdomínio `waha.*` (o domínio institucional tem apenas 1 registro DNS).
  Porta 3000 bindada em `127.0.0.1` no host — dashboard acessível só via
  túnel SSH (ver `docker-compose.prod.yml`).
- Webhook WAHA → Django **já era interno**
  (`WHATSAPP_HOOK_URL=http://backend:8000/webhook/`, rede Docker) e
  Django → WAHA **já usa** `WAHA_URL=http://waha:3000`. Nenhuma mudança
  de código foi necessária nesses fluxos.
- `ALLOWED_HOSTS` vem do `.env` (não há mudança de código em
  `settings/production.py`); `SECURE_PROXY_SSL_HEADER` já cobre o HTTPS
  atrás do Traefik.
- `smoke-check.sh` atualizado: agora valida que o WAHA **não** responde
  publicamente.

### Perguntas para a orientadora / TI antes de decidir

1. O servidor `200.134.22.218` é para **hospedar o bot** (temos sudo e
   podemos instalar Docker?) ou é apenas um host de acesso?
2. As portas 80/443 do servidor recebem tráfego **direto da internet**
   (necessário para o Traefik emitir certificado Let's Encrypt via
   HTTP-01) ou há proxy/firewall institucional na frente que já termina TLS?
3. O SSH (porta 22) é acessível de fora da rede da UTFPR ou só via
   VPN/rede do campus?
4. O usuário SSH é o login institucional?

---

## Opção A — Migrar o deploy para o servidor da UTFPR

O domínio já funciona, sem custo AWS e sem depender de mudança de DNS.

### A.1 Verificações iniciais (no servidor, via SSH)

```bash
ssh <usuario-institucional>@200.134.22.218

# Temos sudo?
sudo -v

# Recursos da máquina (mínimo recomendado: 2 GB RAM, 20 GB disco)
free -h && df -h && nproc

# Docker disponível?
docker --version && docker compose version
```

### A.2 Preparar o servidor

```bash
# Instalar Docker + Compose se necessário (o setup-ec2.sh serve de referência,
# pulando as partes específicas de AWS)
bash deployment/scripts/setup-ec2.sh   # adaptar conforme a distro

# Clonar o repositório
git clone https://github.com/ErickBonruque/iterbot.git && cd iterbot
```

### A.3 Transferir secrets e configuração da EC2

```bash
# Da sua máquina (ou direto entre servidores):
scp -r ubuntu@<ip-ec2>:~/iterbot/secrets ./secrets
scp ubuntu@<ip-ec2>:~/iterbot/.env ./.env
```

Editar o `.env` no servidor novo:

```bash
DOMAIN=chat-universitario.sh.utfpr.edu.br
ALLOWED_HOSTS=chat-universitario.sh.utfpr.edu.br,backend
PORTAL_BASE_URL=https://chat-universitario.sh.utfpr.edu.br
WAHA_URL=http://waha:3000        # já deve estar assim
```

### A.4 Migrar o banco de dados

```bash
# Na EC2 (gera backup e envia ao S3):
bash deployment/scripts/backup-postgres.sh

# No servidor novo (após subir o serviço db):
bash deployment/scripts/restore-postgres.sh <arquivo-de-backup>
```

### A.5 Subir e validar

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
bash deployment/scripts/smoke-check.sh chat-universitario.sh.utfpr.edu.br
```

### A.6 Reconectar a sessão WhatsApp

A sessão WAHA fica no volume `waha_sessions`. No servidor novo será preciso
**parear novamente via QR code** (ou copiar o volume da EC2):

```bash
# Da sua máquina local:
ssh -L 3000:localhost:3000 <usuario>@200.134.22.218
# Abrir http://localhost:3000/dashboard e escanear o QR
```

### A.7 Descomissionar a EC2

Somente após o bot validado no servidor novo (mensagens entrando e saindo):
parar os containers na EC2 e desligar/terminar a instância (manter os
backups no S3).

### Riscos / pontos de atenção da Opção A

- Se as portas 80/443 não chegarem direto ao servidor, o Let's Encrypt
  HTTP-01 falha — seria preciso usar certificado fornecido pela UTFPR ou
  desafio DNS-01.
- Se o SSH só funcionar dentro da rede UTFPR/VPN, o acesso administrativo
  (deploy, QR code) fica restrito a estar no campus ou via VPN.
- O servidor precisa de saída para a internet (scraping de vagas via
  jobspy, WhatsApp, e-mail, S3 para backups).

---

## Opção B — Manter EC2 e repontar o DNS (plano original)

Mantém a infra atual; depende do TI aceitar mudar o registro A.

### B.1 Alocar Elastic IP e associar à instância

```bash
aws ec2 allocate-address --domain vpc --region us-east-1
aws ec2 associate-address --instance-id <id-da-instancia> \
  --allocation-id <alloc-id> --region us-east-1
```

> Nota de custo: desde 2024 a AWS cobra todo IPv4 público
> (~US$ 0,005/hora ≈ US$ 3,60/mês), incluindo Elastic IP associado.

### B.2 Pedir ao TI da UTFPR

| Tipo | Nome                                 | Valor          |
|------|--------------------------------------|----------------|
| A    | `chat-universitario.sh.utfpr.edu.br` | `<elastic-ip>` |

(Hoje o registro aponta para `200.134.22.218` — o TI precisaria concordar
em repontar, já que provisionou um servidor próprio.)

### B.3 Atualizar `.env` na EC2 e reiniciar

```bash
DOMAIN=chat-universitario.sh.utfpr.edu.br
ALLOWED_HOSTS=chat-universitario.sh.utfpr.edu.br,backend
PORTAL_BASE_URL=https://chat-universitario.sh.utfpr.edu.br
```

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
# Traefik emite o certificado Let's Encrypt para o novo domínio automaticamente
bash deployment/scripts/smoke-check.sh chat-universitario.sh.utfpr.edu.br
```

A sessão WhatsApp **não precisa ser reparada** (mesmo servidor, mesmo volume).

---

## Acesso ao dashboard WAHA (qualquer opção)

```bash
ssh -L 3000:localhost:3000 <usuario>@<host>
# Abrir http://localhost:3000/dashboard no navegador local
# Login: WAHA_DASHBOARD_USERNAME / WAHA_DASHBOARD_PASSWORD (do .env)
```
