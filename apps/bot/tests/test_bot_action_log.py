"""
Wave 0 stubs para Phase 52 — OBS-03.
Todos os testes devem falhar com NotImplementedError até que Plan 02 seja executado.
"""

from django.test import TestCase

from apps.bot.models import BotActionLog  # noqa: F401
from apps.users.models import UserProfile


class BotActionLogCaptureTests(TestCase):
    """OBS-03: Captura automática de erros via BotService.process_message()."""

    def setUp(self):
        self.user = UserProfile.objects.create(phone_number="5541999000001@c.us")

    def test_capture_exception_creates_error_log(self):
        """OBS-03: Quando handler lança exceção, BotActionLog é criado com status=ERROR."""
        raise NotImplementedError("Wave 0 stub — implementar em Plan 02")

    def test_waha_send_fail_creates_error_log(self):
        """OBS-03: Quando send_message() retorna False, BotActionLog é criado com action_type=WAHA_SEND status=ERROR."""
        raise NotImplementedError("Wave 0 stub — implementar em Plan 02")

    def test_successful_message_creates_success_log(self):
        """OBS-03: Fluxo bem-sucedido cria BotActionLog com status=SUCCESS."""
        raise NotImplementedError("Wave 0 stub — implementar em Plan 02")
