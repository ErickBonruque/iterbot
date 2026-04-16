# ADR-003: Celery para Tasks Assincronas

## Status

Proposed

## Date

2026-04-16

## Context

Tarefas de longa duracao (busca de vagas via JobSpy, envio de notificacoes em lote, health checks periodicos) bloqueiam o ciclo de request-response quando executadas sincronamente.

O sistema atual processa tudo de forma sincrona, o que pode causar timeouts em operacoes que demoram mais de 30 segundos.

## Decision

Implementar Celery com broker Redis para processamento de tarefas assincronas.

### Implementacao Proposta

- Celery 5.x com backend Redis
- Tarefas principais:
  - `fetch_jobs_for_course`: Busca vagas do JobSpy
  - `send_notification_batch`: Envio em lote de notificacoes
  - `periodic_health_check`: Verificacao agendada do bot
- Beat scheduler para tarefas periodicas

## Consequences

### Positive
- Operacoes nao bloqueiam o usuario
- Melhor UX com feedback assincrono
- Rate limiting natural via filas
- Escalabilidade horizontal com workers multiplos

### Negative
- Complexidade adicional de infraestrutura (Redis + Celery)
- Debugging de tarefas assincronas e mais complexo
- Possivel perda de tarefas se Redis falhar

### Neutral
- Redis ja esta em uso para cache (reaproveitamento)
- Prepara base para监控系统 futuro
- Pode ser opcional em ambientes de desenvolvimento
