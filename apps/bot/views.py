import json

import structlog
from django.core.cache import cache
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from apps.bot.messages import BOT_MESSAGES

logger = structlog.get_logger(__name__)

# Rate limiting: máximo de requisições por janela de tempo por IP
_WEBHOOK_RATE_LIMIT = 60  # máximo de chamadas por janela
_WEBHOOK_RATE_WINDOW = 60  # janela em segundos


def _is_rate_limited(ip: str) -> bool:
    """Verifica e incrementa o contador de rate limiting para o IP dado.

    Retorna True se o limite foi excedido, False caso contrário.
    Usa o cache do Django (LocMem em dev, Redis em produção).
    """
    cache_key = f"webhook_rl:{ip}"
    count = cache.get(cache_key, 0)
    if count >= _WEBHOOK_RATE_LIMIT:
        return True
    # add() é atômico e define TTL apenas na primeira chamada (quando count == 0)
    if count == 0:
        cache.add(cache_key, 0, timeout=_WEBHOOK_RATE_WINDOW)
    cache.incr(cache_key)
    return False


@csrf_exempt
def webhook(request):
    if request.method != "POST":
        return HttpResponse(BOT_MESSAGES.system.method_not_allowed.text, status=405)

    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "unknown"))
    # X-Forwarded-For pode conter lista; pegar apenas o primeiro endereço
    ip = ip.split(",")[0].strip()

    if _is_rate_limited(ip):
        logger.warning("webhook_rate_limited", ip=ip)
        return HttpResponse("Too Many Requests", status=429)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning("webhook_invalid_json")
        return HttpResponse("Invalid JSON payload", status=400)

    event = data.get("event")
    payload = data.get("payload") or {}

    if not isinstance(event, str) or "message" not in event:
        logger.warning("webhook_invalid_event", waha_event=event)
        return HttpResponse("Invalid event", status=400)

    body = payload.get("body")
    chat_id = payload.get("from")
    from_me = payload.get("fromMe", False)

    if not body:
        logger.warning("webhook_missing_body", waha_event=event)
        return HttpResponse("Invalid payload", status=400)

    if from_me:
        logger.info("webhook_ignored_from_me", chat_id=chat_id)
        return HttpResponse("OK", status=200)

    from apps.bot.tasks import process_webhook_message

    process_webhook_message.delay(chat_id, body)
    logger.info("webhook_message_enqueued", chat_id=chat_id)
    return HttpResponse("OK", status=200)
