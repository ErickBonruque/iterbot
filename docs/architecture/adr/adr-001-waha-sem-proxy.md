# ADR-001: WAHA sem Proxy Traefik

## Status

Accepted

## Date

2026-04-16

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
