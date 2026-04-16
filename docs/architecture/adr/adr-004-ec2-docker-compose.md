# ADR-004: EC2 + Docker Compose para Deploy

## Status

Accepted

## Date

2026-04-16

## Context

Projeto acadêmico requer plataforma de deploy simples e de baixo custo. ECS/Kubernetes adicionam complexidade desnecessária para um monólito Django. RDS para PostgreSQL também é overkill para o volume de dados esperado.

## Decision

EC2 t3.small (us-east-1) + Docker Compose como plataforma de deploy.

### Implementacao

- Instância t3.small com Docker + Docker Compose instalado via user data
- Containers: backend Django (porta 8000), PostgreSQL 15, Redis 7, WAHA (porta 3000), Traefik v3.6 (portas 80/443)
- Deploy via GitHub Actions (`.github/workflows/deploy.yml`)
- Backups do banco para S3 via cron

## Consequences

### Positive

- Baixo custo (~$8/mês)
- Simplicidade operacional
- Controle total da infraestrutura

### Negative

- Responsabilidade por patching de OS
- Failover manual

### Neutral

- Adequado para escala inicial
- Migração para ECS/Lambda é possível no futuro
