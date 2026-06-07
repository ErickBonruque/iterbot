# Architecture

Documentacao arquitetural do projeto.

## Visao Geral

- [OVERVIEW.md](OVERVIEW.md) - Visao geral da arquitetura
- [BOT-FLOWS.md](BOT-FLOWS.md) - Fluxos do bot (autenticação, busca de vagas, review semanal)
- [BUSINESS-RULES.md](BUSINESS-RULES.md) - Regras de negócio (acesso, pipeline DailyJob, portal de empresas)

## ADRs (Architecture Decision Records)

- [adr/README.md](adr/) - Indice de ADRs

### Decisoes Documentadas

| ID | Titulo | Status |
|----|--------|--------|
| ADR-001 | WAHA sem Proxy Traefik | Superseded (producao agora usa Traefik + BasicAuth + TLS) |
| ADR-002 | Campos Criptografados | Accepted |
| ADR-003 | Celery para Tasks | Accepted |
| ADR-004 | EC2 + Docker Compose | Accepted |
