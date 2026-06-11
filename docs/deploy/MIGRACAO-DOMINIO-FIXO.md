# Migração para Domínio Fixo — `chat-universitario.sh.utfpr.edu.br`

## Decisão

**Migrar o deploy para o servidor da UTFPR (`200.134.22.218`).**

Confirmado pela orientadora: o hosting foi criado especificamente para
hospedar o chat, e o domínio `chat-universitario.sh.utfpr.edu.br` já possui
registro A apontando para esse servidor. A alternativa de manter a EC2 e
repontar o DNS foi descartada (ver apêndice no final).

O servidor poderá ser **compartilhado com outro bot de WhatsApp** (projeto
paralelo) — ver seção "Convivência com outro bot".

### O que já está pronto no repositório

- WAHA é serviço **interno** em produção: sem rota Traefik, sem subdomínio
  `waha.*` (o domínio institucional tem apenas 1 registro DNS). Porta 3000
  bindada em `127.0.0.1` no host — dashboard acessível só via túnel SSH
  (ver `docker-compose.prod.yml`).
- Webhook WAHA → Django **já era interno**
  (`WHATSAPP_HOOK_URL=http://backend:8000/webhook/`, rede Docker) e
  Django → WAHA **já usa** `WAHA_URL=http://waha:3000`. Nenhuma mudança
  de código foi necessária nesses fluxos.
- `ALLOWED_HOSTS` vem do `.env` (não há mudança de código em
  `settings/production.py`); `SECURE_PROXY_SSL_HEADER` já cobre o HTTPS
  atrás do Traefik.
- `smoke-check.sh` atualizado: valida que o WAHA **não** responde
  publicamente.

### Pré-requisitos a confirmar com o TI

1. Permissão de administrador (sudo) na máquina, para instalar Docker.
2. Portas **80/443** recebendo tráfego direto da internet — necessário para
   o Traefik emitir certificado Let's Encrypt (HTTP-01). Se houver
   proxy/firewall institucional terminando TLS na frente, o plano de
   certificados muda (certificado da UTFPR ou desafio DNS-01).
3. Porta **22 (SSH)**: acessível de fora da rede UTFPR ou só campus/VPN?
   Além do acesso administrativo, isso define o CI/CD (ver seção própria).
4. Recursos da máquina: mínimo 2 GB RAM / 20 GB disco para o IterBot;
   recomendado 4 GB+ se for compartilhar com o outro bot.
5. Saída para a internet liberada (WhatsApp, scraping de vagas, e-mail,
   S3 para backups).

---

## Passo a passo da migração

### 1. Verificações iniciais (no servidor, via SSH)

```bash
ssh <usuario-institucional>@200.134.22.218

sudo -v                                  # temos sudo?
free -h && df -h && nproc                # recursos
docker --version && docker compose version  # Docker disponível?
```

### 2. Preparar o servidor

```bash
# Instalar Docker + Compose se necessário (o setup-ec2.sh serve de
# referência, pulando as partes específicas de AWS)
bash deployment/scripts/setup-ec2.sh   # adaptar conforme a distro

git clone https://github.com/ErickBonruque/iterbot.git && cd iterbot
```

### 3. Transferir secrets e configuração da EC2

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

### 4. Migrar o banco de dados

```bash
# Na EC2 (gera backup e envia ao S3):
bash deployment/scripts/backup-postgres.sh

# No servidor novo (após subir o serviço db):
bash deployment/scripts/restore-postgres.sh <arquivo-de-backup>
```

### 5. Subir e validar

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
bash deployment/scripts/smoke-check.sh chat-universitario.sh.utfpr.edu.br
```

### 6. Reconectar a sessão WhatsApp

A sessão WAHA fica no volume `waha_sessions`. No servidor novo será preciso
**parear novamente via QR code** (ou copiar o volume da EC2):

```bash
# Da sua máquina local:
ssh -L 3000:localhost:3000 <usuario>@200.134.22.218
# Abrir http://localhost:3000/dashboard e escanear o QR
```

### 7. Atualizar o CI/CD (após a virada)

O workflow `.github/workflows/deploy.yml` hoje faz deploy/rollback via
**AWS SSM** com o ID da instância EC2 hardcoded — isso não funciona no
servidor da UTFPR. **Não alterar antes da migração** (quebraria o deploy
atual). Depois da virada:

- Trocar os steps de SSM por deploy via **SSH** (ex.: `appleboy/ssh-action`
  ou `ssh` direto), executando `git pull` + `ec2_deploy.sh` no servidor.
- Novos secrets no GitHub: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`
  (gerar par de chaves dedicado; adicionar a pública no
  `~/.ssh/authorized_keys` do servidor — não usar a senha institucional).
- **Atenção:** isso exige a porta 22 do servidor acessível pelos runners do
  GitHub Actions (internet). Se o TI restringir SSH ao campus/VPN, as
  opções são deploy manual via SSH ou um self-hosted runner dentro da rede.
- Os secrets `AWS_*` continuam necessários apenas para o backup no S3.

### 8. Descomissionar a EC2

Somente após o bot validado no servidor novo (mensagens entrando e saindo,
smoke-check verde): parar os containers na EC2 e desligar/terminar a
instância (manter os backups no S3). Atualizar as referências a EC2 nos
docs (`CLAUDE.md`, `docs/deploy/`) quando a virada estiver concluída.

---

## Convivência com outro bot no mesmo servidor

O servidor poderá hospedar também outro bot de WhatsApp (projeto paralelo).
Cada bot roda como um projeto Docker Compose **separado** (cada um com seu
banco, Redis e WAHA) — containers de projetos diferentes não se enxergam.
Regras para não colidir:

- **Portas 80/443**: só um processo pode escutá-las. O Traefik do IterBot
  fica com elas. Se o outro bot **não tiver interface web pública** (só
  conversa com o WhatsApp), não há conflito algum. Se precisar de HTTP/S
  público, ele entra numa rede Docker externa compartilhada e é roteado
  pelo mesmo Traefik — exigindo um segundo registro DNS (pedir ao TI) ou
  roteamento por path.
- **Portas publicadas no host**: combinar a alocação. O WAHA do IterBot usa
  `127.0.0.1:3000`; o do outro bot deve usar outra porta (ex.: 3001).
- **Nomes de container e volumes**: usar prefixos distintos por projeto
  (compose já isola por diretório/projeto, mas `container_name` fixos
  colidem).
- **Recursos**: dois stacks completos (2× Postgres, 2× Redis, 2× WAHA)
  dobram o consumo de RAM/disco — validar capacidade da máquina antes.

---

## Acesso ao dashboard WAHA

```bash
ssh -L 3000:localhost:3000 <usuario>@200.134.22.218
# Abrir http://localhost:3000/dashboard no navegador local
# Login: WAHA_DASHBOARD_USERNAME / WAHA_DASHBOARD_PASSWORD (do .env)
```

---

## Apêndice — Alternativa descartada: manter EC2 e repontar o DNS

Consistia em alocar um Elastic IP na AWS, associá-lo à instância e pedir ao
TI da UTFPR para mudar o registro A do domínio para esse IP. Foi descartada
porque o TI provisionou o servidor `200.134.22.218` especificamente para
hospedar o chat (e o domínio já aponta para ele), além do custo do IPv4
público na AWS (~US$ 3,60/mês) e da dependência de mudança de DNS
institucional.
