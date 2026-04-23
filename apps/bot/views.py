import json

import structlog
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from apps.bot.messages import BOT_MESSAGES

logger = structlog.get_logger(__name__)


@csrf_exempt
def webhook(request):
    if request.method != "POST":
        return HttpResponse(BOT_MESSAGES.system.method_not_allowed.text, status=405)

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
