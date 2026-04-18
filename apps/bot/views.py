import json

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from apps.bot.messages import BOT_MESSAGES
from apps.bot.services import BotService


@csrf_exempt
def webhook(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            event = data.get("event")
            payload = data.get("payload", {})

            if event and "message" in event and payload.get("body"):
                chat_id = payload.get("from")
                message = payload.get("body")
                from_me = payload.get("fromMe", False)

                if not from_me:
                    bot = BotService()
                    bot.process_message(chat_id, message, from_me)

            return HttpResponse("OK", status=200)
        except Exception:
            return HttpResponse(BOT_MESSAGES.system.webhook_error.text, status=500)

    return HttpResponse(BOT_MESSAGES.system.method_not_allowed.text, status=405)
