import hashlib
import json
import time

import structlog
from django.core.cache import cache
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from apps.bot.messages import BOT_MESSAGES

logger = structlog.get_logger(__name__)

# Rate limiting: máximo de requisições por janela de tempo por IP
_WEBHOOK_RATE_LIMIT = 300  # máximo de chamadas por janela
_WEBHOOK_RATE_WINDOW = 60  # janela em segundos

# Eventos que carregam uma mensagem nova do usuário. Aceitar qualquer evento
# com "message" no nome fazia `message.ack`, `message.reaction` e afins caírem
# no fluxo de processamento (e devolverem 400, o que dispara retry no WAHA).
_MESSAGE_EVENTS = frozenset({"message", "message.any"})

# Deduplicação: o WAHA reentrega o mesmo evento quando o POST falha, expira ou
# quando mais de um hook (env global + config da sessão) aponta para cá. Sem
# esta guarda a mesma mensagem é processada duas vezes — o bot responde
# duplicado e, pior, a segunda passagem avança o estado da conversa e responde
# algo que não corresponde ao que o usuário digitou.
_DEDUPE_TTL_SECONDS = 15 * 60

# Mensagens muito antigas chegam em lote quando a sessão WhatsApp reconecta
# (backlog offline do engine NOWEB). Respondê-las fora de contexto confunde
# mais do que ajuda; a janela cobre folgadamente um deploy ou restart normal.
_MAX_MESSAGE_AGE_SECONDS = 30 * 60


def _is_rate_limited(ip: str) -> bool:
    """Verifica e incrementa o contador de rate limiting para o IP dado.

    Retorna True se o limite foi excedido, False caso contrário.
    Usa o cache do Django (LocMem em dev, Redis em produção).
    """
    cache_key = f"webhook_rl:{ip}"
    # add() é atômico e define o TTL apenas na primeira chamada da janela.
    cache.add(cache_key, 0, timeout=_WEBHOOK_RATE_WINDOW)
    try:
        count = cache.incr(cache_key)
    except ValueError:
        # A chave expirou entre o add() e o incr(): recomeça a janela em vez de
        # estourar 500 (que faria o WAHA reenviar o mesmo evento).
        cache.add(cache_key, 1, timeout=_WEBHOOK_RATE_WINDOW)
        return False
    return count > _WEBHOOK_RATE_LIMIT


def _dedupe_key(payload: dict, chat_id: str | None, body: str) -> str:
    """Constrói a chave de deduplicação de uma mensagem recebida.

    Usa o id da mensagem do WhatsApp quando disponível; sem ele, cai para um
    hash de remetente + timestamp + conteúdo, que ainda identifica reentregas
    do mesmo evento.
    """
    message_id = payload.get("id")
    if isinstance(message_id, dict):  # algumas engines devolvem {"id": ..., ...}
        message_id = message_id.get("id") or message_id.get("_serialized")
    if isinstance(message_id, str) and message_id:
        return message_id

    raw = f"{chat_id}|{payload.get('timestamp')}|{body}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_duplicate(dedupe_key: str) -> bool:
    """True se este evento já foi aceito recentemente (reentrega do WAHA)."""
    return not cache.add(f"webhook_seen:{dedupe_key}", 1, timeout=_DEDUPE_TTL_SECONDS)


def _message_age_seconds(payload: dict) -> float | None:
    """Idade da mensagem em segundos, ou None se o payload não trouxer timestamp."""
    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, int | float):
        return None
    # NOWEB envia segundos; outras engines enviam milissegundos.
    if timestamp > 1e11:
        timestamp = timestamp / 1000
    return time.time() - timestamp


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

    if event not in _MESSAGE_EVENTS:
        # message.ack, message.reaction, message.revoked, message.edited...:
        # eventos legítimos que não iniciam conversa. 200 para o WAHA não
        # tratar como falha e reenviar.
        logger.debug("webhook_event_ignored", waha_event=event)
        return HttpResponse("Ignored", status=200)

    body = payload.get("body")
    chat_id = payload.get("from")
    from_me = payload.get("fromMe", False)

    if not body:
        logger.warning("webhook_missing_body", waha_event=event)
        return HttpResponse("Invalid payload", status=400)

    if from_me:
        logger.info("webhook_ignored_from_me", chat_id=chat_id)
        return HttpResponse("OK", status=200)

    age_seconds = _message_age_seconds(payload)
    if age_seconds is not None and age_seconds > _MAX_MESSAGE_AGE_SECONDS:
        logger.warning(
            "webhook_message_too_old",
            chat_id=chat_id,
            age_seconds=round(age_seconds),
        )
        return HttpResponse("OK", status=200)

    dedupe_key = _dedupe_key(payload, chat_id, body)
    if _is_duplicate(dedupe_key):
        logger.info("webhook_duplicate_ignored", chat_id=chat_id, message_id=dedupe_key)
        return HttpResponse("OK", status=200)

    from apps.bot.tasks import process_webhook_message

    process_webhook_message.delay(chat_id, body)
    logger.info("webhook_message_enqueued", chat_id=chat_id, message_id=dedupe_key)
    return HttpResponse("OK", status=200)
