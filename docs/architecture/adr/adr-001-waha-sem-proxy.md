# ADR-001: WAHA sem Proxy Traefik

## Status

Superseded — substituido pela configuracao atual de producao, descrita na secao "Atualizacao" abaixo.

## Date

2026-04-16 (decisao original)

## Context

WAHA (WhatsApp HTTP API) requer acesso direto para autenticacao. O acesso via proxy Traefik causava erros 401 Unauthorized, impedindo a comunicacao correta com a API do WhatsApp.

O Traefik esta configurado como proxy reverso para todos os servicos, mas WAHA precisa de acesso direto as portas 3000.

## Decision

Acessar WAHA diretamente na porta 3000, bypassing o proxy Traefik.

### Implementacao

- WAHA exposto diretamente na porta 3000 do host
- Comunicacao interna via rede Docker usando nome do servico `waha:3000`
- Dashboard WAHA acessivel em http://localhost:3000/dashboard

## Consequences

### Positive
- Autenticacao WAHA funciona corretamente
- QR Code para conexao WhatsApp funciona
- Dashboard WAHA acessivel diretamente

### Negative
- WAHA nao disponivel via HTTPS de acesso externo
- Requer porta 3000 exposta no firewall (dev only)

### Neutral
- Rede interna Docker continua acessando WAHA normalmente
- Proxy Traefik continua funcionando para backend Django

---

## Atualizacao (estado atual em producao)

Esta decisao foi revisada e substituida durante o hardening de seguranca da Phase 12 / Phase 13.

### Estado atual

- Em **desenvolvimento local**, WAHA continua exposto em `http://localhost:3000/dashboard` para facilitar pareamento por QR Code (ver `docker-compose.yml`).
- Em **producao**, WAHA **nao expoe** a porta 3000 publicamente — o acesso externo ocorre exclusivamente via Traefik em `https://waha.${DOMAIN}` com middlewares `security-headers@file` e `waha-auth@file` (BasicAuth + TLS Let's Encrypt). Ver `docker-compose.prod.yml` e `infra/traefik/dynamic/middlewares.yml`.
- O Security Group da EC2 deixou de aceitar a porta 3000 (ver `deployment/scripts/harden-security-group.sh`); apenas 22/80/443 permanecem abertas.

### Motivo da reversao

- O erro 401 do problema original veio do envio incorreto do header `X-Api-Key` quando o WAHA tem `WAHA_API_KEY` configurado; com o middleware ajustado para repassar o header e a sessao autenticando via dashboard com BasicAuth, o proxy passou a funcionar.
- Manter porta 3000 publica violava o requisito de superficie de ataque minima do Security Group.

### Implicacoes

- Pareamento QR em producao exige login com BasicAuth antes do dashboard WAHA, o que requer credenciais geradas por `setup-htpasswd.sh`.
- Webhook do WAHA segue rota interna Docker (`http://backend:8000/webhook/`), sem passar pelo Traefik.
