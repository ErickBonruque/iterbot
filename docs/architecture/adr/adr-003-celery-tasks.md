# ADR-003: Celery para Tasks Assincronas

## Status

Accepted — implementado em producao.

## Date

2026-04-16 (proposta) / 2026-04-23 (implementado)

## Context

Tarefas de longa duracao (busca de vagas via JobSpy, envio de notificacoes em lote, health checks periodicos) bloqueiam o ciclo de request-response quando executadas sincronamente.

O sistema atual processa tudo de forma sincrona, o que pode causar timeouts em operacoes que demoram mais de 30 segundos.

## Decision

Implementar Celery com broker Redis para processamento de tarefas assincronas.

### Implementacao atual

- Celery 5.x com broker e result backend em Redis (`redis://redis:6379/0`).
- Servicos dedicados no `docker-compose.prod.yml`: `celery_worker` e `celery_beat`.
- Configuracao em `waha_bot/celery.py` com autodiscovery de `apps.<app>.tasks`.

### Tasks ativas

| Task | Localizacao | Trigger |
|------|-------------|---------|
| `process_webhook_message` | `apps/bot/tasks.py` | Disparada pela view de webhook do WAHA para processar mensagens fora do ciclo HTTP |
| `send_confirmation_email` | `apps/bot/tasks.py` | Disparada apos `link_user` no fluxo de autenticacao do estudante |
| `check_waha_health` | `apps/bot/tasks.py` | Celery Beat — a cada 5 minutos |
| `attempt_waha_reconnect` | `apps/bot/tasks.py` | Disparada por `check_waha_health` em caso de falha consecutiva, com backoff exponencial |
| `clean_old_health_checks` | `apps/bot/tasks.py` | Celery Beat — limpeza periodica de registros antigos de `BotHealthCheck` |
| `fetch_daily_jobs` | `apps/jobs/tasks.py` | Celery Beat — busca diaria via python-jobspy |
| `send_weekly_job_review` | `apps/jobs/tasks.py` | Celery Beat — segunda-feira 08:00 (America/Sao_Paulo) |

## Consequences

### Positive
- Operacoes nao bloqueiam o usuario
- Melhor UX com feedback assincrono
- Rate limiting natural via filas
- Escalabilidade horizontal com workers multiplos
- Reaproveitamento do Redis ja existente (cache + broker)

### Negative
- Complexidade adicional de infraestrutura (worker + beat como containers separados)
- Debugging de tarefas assincronas e mais complexo
- Possivel perda de tarefas se Redis falhar (mitigado por idempotency keys no envio de email)

### Neutral
- Redis ja esta em uso para cache (reaproveitamento)
- Pode ser opcional em ambientes de desenvolvimento (worker/beat sao opcionais no compose base)
