import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from apps.bot.services import BotService

@csrf_exempt
def webhook(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print('Webhook recebido:', json.dumps(data, indent=2))
            
            event = data.get('event')
            payload = data.get('payload', {})
            
            # Aceitar eventos message, message.any, ou qualquer evento de mensagem
            if event and 'message' in event and payload.get('body'):
                chat_id = payload.get('from')
                message = payload.get('body')
                from_me = payload.get('fromMe', False)
                
                # Ignorar mensagens enviadas pelo próprio bot
                if not from_me:
                    bot = BotService()
                    bot.process_message(chat_id, message, from_me)
                    
            return HttpResponse('OK', status=200)
        except Exception as e:
            print(f'Erro no webhook: {e}')
            import traceback
            traceback.print_exc()
            return HttpResponse('Erro', status=500)
            
    return HttpResponse('Método não permitido', status=405)
