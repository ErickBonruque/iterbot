# Troubleshooting

Solucao de problemas comuns.

## Guias

| Arquivo | Descricao |
|---------|-----------|
| [WAHA_COMPLETE_GUIDE.md](WAHA_COMPLETE_GUIDE.md) | Guia completo WAHA |
| [WAHA_FIX_DOCUMENTATION.md](WAHA_FIX_DOCUMENTATION.md) | Correcoes e fixes WAHA |

## Problemas Comuns

1. **WAHA 401 Unauthorized** - Verificar WAHA_API_KEY
2. **Port already in use** - Verificar servicos na porta 80/443
3. **Cannot connect to database** - Verificar health check do PostgreSQL

## Bot responde duplicado ou fora de contexto

Sintoma: o bot envia a mesma resposta duas vezes e, na sequencia, manda uma
mensagem que nao corresponde ao que o usuario digitou (ex.: usuario manda `2`,
recebe o menu de onboarding **e** o pedido de e-mail do login de empresa).

Causa: o mesmo evento do WAHA chega duas vezes ao `/webhook/`. Como cada
processamento avanca a maquina de estados, a segunda passagem responde ao
estado que a primeira acabou de criar. Reentregas acontecem quando:

- o POST do webhook estoura o timeout (backend com 1 worker gunicorn no host
  `gosh`, 1 vCPU) ou devolve erro — o WAHA reenvia;
- ha mais de um hook apontando para o backend (`WHATSAPP_HOOK_URL` global do
  compose **e** webhook salvo na config da sessao pelo dashboard);
- a sessao reconecta e o engine NOWEB entrega o backlog de mensagens offline;
- a task `process_webhook_message` falha depois de ja ter respondido e o retry
  do Celery reexecuta o fluxo inteiro.

Protecoes no codigo (`apps/bot/views.py`, `apps/bot/tasks.py`):

- deduplicacao por id da mensagem no cache (Redis) com TTL de 15 min;
- apenas `message` e `message.any` sao processados — `message.ack` e afins
  respondem 200 sem enfileirar;
- mensagens com mais de 30 min sao descartadas (backlog offline);
- o retry da task so acontece se nenhuma resposta tiver sido enviada.

Diagnostico no host:

```bash
# Quantas entregas por mensagem chegaram ao backend
docker logs iterbot_backend --since 30m | grep -E "webhook_message_enqueued|webhook_duplicate_ignored"

# Hooks configurados na sessao (deve haver apenas um)
curl -s -H "X-Api-Key: $WAHA_API_KEY" http://localhost:3000/api/sessions/default | jq '.config.webhooks'
```

Se `.config.webhooks` listar um hook alem do global do compose, remova-o pelo
dashboard/API — os dois somados dobram cada evento.
