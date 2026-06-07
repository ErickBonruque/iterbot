"""
Phase 52 — OBS-03: Testes de captura automática de erros via BotActionLog.
Task 1: BotService.process_message() — captura centralizada de exceções.
Task 2: BaseHandler.send_msg() — captura de WAHA_SEND failures.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.bot.models import BotActionLog
from apps.bot.services import BotService
from apps.users.models import UserProfile


class BotActionLogCaptureTests(TestCase):
    """OBS-03: Captura automática de erros via BotService.process_message()."""

    def setUp(self):
        self.user = UserProfile.objects.create(phone_number="5541999000001@c.us")
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.waha_client.send_message.return_value = True
        self.service = BotService(waha_client=self.waha_client)

    @patch("apps.bot.services.BotService._handle_main_menu_command")
    @patch("apps.bot.services.BotService._get_conversation_state")
    @patch("apps.bot.services.BotService._log_received")
    def test_capture_exception_creates_error_log(self, mock_log, mock_state, mock_handle):
        """OBS-03: Exceção em _handle_main_menu_command cria BotActionLog(status=ERROR)."""
        mock_handle.side_effect = Exception("handler crashed")
        mock_state.return_value = MagicMock()

        with self.assertRaises(Exception):  # noqa: B017
            self.service.process_message(
                chat_id=self.user.phone_number,
                message="comando_qualquer",
                from_me=False,
            )

        self.assertTrue(
            BotActionLog.objects.filter(status="ERROR", error_type="EXCEPTION").exists(),
            "BotActionLog com status=ERROR e error_type=EXCEPTION deve ser criado",
        )

    @patch("apps.bot.services.BotService._handle_main_menu_command")
    @patch("apps.bot.services.BotService._get_conversation_state")
    @patch("apps.bot.services.BotService._log_received")
    def test_successful_message_creates_success_log(self, mock_log, mock_state, mock_handle):
        """OBS-03: Fluxo bem-sucedido cria BotActionLog com status=SUCCESS."""
        mock_handle.return_value = None  # sem exceção
        mock_state.return_value = MagicMock()

        self.service.process_message(
            chat_id=self.user.phone_number,
            message="comando_qualquer",
            from_me=False,
        )

        self.assertTrue(
            BotActionLog.objects.filter(status="SUCCESS").exists(),
            "BotActionLog com status=SUCCESS deve ser criado quando não há exceção",
        )

    @patch("apps.bot.services.BotService._handle_main_menu_command")
    @patch("apps.bot.services.BotService._get_conversation_state")
    @patch("apps.bot.services.BotService._log_received")
    def test_exception_is_reraised_after_log(self, mock_log, mock_state, mock_handle):
        """OBS-03: Exceção é re-raised após BotActionLog ser criado."""
        mock_handle.side_effect = ValueError("specific error value")
        mock_state.return_value = MagicMock()

        with self.assertRaises(ValueError):
            self.service.process_message(
                chat_id=self.user.phone_number,
                message="teste",
                from_me=False,
            )

        # Confirma que o log foi criado antes do re-raise
        log = BotActionLog.objects.filter(status="ERROR").first()
        self.assertIsNotNone(log, "Log deve ser criado mesmo com re-raise")
        self.assertIn("specific error value", log.error_message)


class BotActionLogWahaSendTests(TestCase):
    """OBS-03: Captura de falhas WAHA_SEND em BaseHandler.send_msg()."""

    def setUp(self):
        self.user = UserProfile.objects.create(phone_number="5541999000002@c.us")

    def test_waha_send_fail_creates_error_log(self):
        """OBS-03: send_message() retorna False → BotActionLog WAHA_SEND ERROR criado."""
        from apps.bot.handlers.menu import MenuHandler

        mock_waha = MagicMock()
        mock_waha.send_message.return_value = False  # retorna False, não levanta exceção
        mock_waha.settings = MagicMock(session_name="test-session")

        handler = MenuHandler(waha_client=mock_waha)
        handler.send_msg(self.user, self.user.phone_number, "Olá!")

        self.assertTrue(
            BotActionLog.objects.filter(
                action_type="WAHA_SEND",
                status="ERROR",
                error_type="WAHA_SEND_FAIL",
            ).exists(),
            "BotActionLog WAHA_SEND com status=ERROR e error_type=WAHA_SEND_FAIL deve ser criado",
        )

    def test_waha_send_exception_creates_error_log(self):
        """OBS-03: send_message() lança Exception → BotActionLog WAHA_SEND ERROR EXCEPTION criado."""
        from apps.bot.handlers.menu import MenuHandler

        mock_waha = MagicMock()
        mock_waha.send_message.side_effect = Exception("connection refused")
        mock_waha.settings = MagicMock(session_name="test-session")

        handler = MenuHandler(waha_client=mock_waha)
        handler.send_msg(self.user, self.user.phone_number, "Olá!")

        self.assertTrue(
            BotActionLog.objects.filter(
                action_type="WAHA_SEND",
                status="ERROR",
                error_type="EXCEPTION",
            ).exists(),
            "BotActionLog WAHA_SEND com status=ERROR e error_type=EXCEPTION deve ser criado",
        )

    def test_waha_send_success_does_not_create_error_log(self):
        """OBS-03: send_message() retorna True → nenhum BotActionLog de WAHA_SEND é criado."""
        from apps.bot.handlers.menu import MenuHandler

        mock_waha = MagicMock()
        mock_waha.send_message.return_value = True
        mock_waha.settings = MagicMock(session_name="test-session")

        handler = MenuHandler(waha_client=mock_waha)
        handler.send_msg(self.user, self.user.phone_number, "Olá!")

        self.assertFalse(
            BotActionLog.objects.filter(
                action_type="WAHA_SEND",
                status="ERROR",
            ).exists(),
            "Nenhum BotActionLog de erro deve ser criado quando send_message() retorna True",
        )
